from __future__ import annotations

import dataclasses
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from functools import cached_property
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import requests
from requests import Response, Session

from api.hh_api.routes import (
    AllVacancies,
    BlacklistedEmployers,
    Me,
    MyResumes,
    Negotiations,
    NegotiationsMessages,
    PublishResume,
    ResumeInfo,
    SimilarVacancies,
    Vacancy,
)
from constants import ANDROID_CLIENT_ID, ANDROID_CLIENT_SECRET
from schemas import AccessToken

from . import errors

__all__ = ("HHApi", "OAuthClient")

logger = logging.getLogger(__package__)


ALLOWED_METHODS = ("GET", "POST", "PUT", "DELETE")


# Thread-safe
@dataclass
class BaseClient:
    base_url: str
    _: dataclasses.KW_ONLY
    user_agent: str | None = None
    proxies: dict | None = None
    session: Session | None = None
    previous_request_time: float = 0.0
    delay: float = 0.334

    def __post_init__(self) -> None:
        self.lock = Lock()
        if not self.session:
            self.session = session = requests.session()
            session.headers.update(
                {
                    "user-agent": self.user_agent or self.default_user_agent(),
                    "x-hh-app-active": "true",
                    **self.additional_headers(),
                }
            )

    def default_user_agent(self) -> str:
        devices = "23053RN02A, 23053RN02Y, 23053RN02I, 23053RN02L, 23077RABDC".split(", ")
        device = random.choice(devices)
        minor = random.randint(100, 150)
        patch = random.randint(10000, 15000)
        android = random.randint(11, 15)
        return f"ru.hh.android/7.{minor}.{patch}, Device: {device}, Android OS: {android} (UUID: {uuid.uuid4()})"

    def additional_headers(
        self,
    ) -> dict[str, str]:
        return {}

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        delay: float | None = None,
        **kwargs: Any,
    ) -> dict:
        assert method in ALLOWED_METHODS

        logger.info(f"params: {params}")
        params = dict(params or {})
        params.update(kwargs)
        url = self.resolve_url(endpoint)
        with self.lock:
            if (delay := (self.delay if delay is None else delay) - time.monotonic() + self.previous_request_time) > 0:
                logger.debug("wait %fs before request", delay)
                time.sleep(delay)
            has_body = method in ["POST", "PUT"]
            payload = {"data" if has_body else "params": params}
            response = self.session.request(  # pyright: ignore[reportOptionalMemberAccess]
                method,
                url,
                **payload,  # pyright: ignore[reportArgumentType]
                proxies=self.proxies,
                allow_redirects=False,
            )
            try:
                try:
                    rv = response.json()
                except json.decoder.JSONDecodeError:
                    rv = {}
            finally:
                logger.debug(
                    "%d %-6s %s",
                    response.status_code,
                    method,
                    url + ("?" + urlencode(params) if not has_body and params else ""),
                )
                self.previous_request_time = time.monotonic()
        self.raise_for_status(response, rv)
        assert 300 > response.status_code >= 200
        return rv

    def get(self, *args, **kwargs) -> dict[str, str]:
        return self.request("GET", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request("POST", *args, **kwargs)

    def put(self, *args, **kwargs):
        return self.request("PUT", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.request("DELETE", *args, **kwargs)

    def resolve_url(self, url: str) -> str:
        return url if "://" in url else f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

    @staticmethod
    def raise_for_status(response: Response, data: dict) -> None:
        match response.status_code:
            case 301 | 302:
                raise errors.Redirect(response, data)
            case 400:
                if errors.ApiError.is_limit_exceeded(data):
                    raise errors.LimitExceeded(response=response, data=data)
                raise errors.BadRequest(response, data)
            case 403:
                raise errors.Forbidden(response, data)
            case 404:
                raise errors.ResourceNotFound(response, data)
            case status if 500 > status >= 400:
                raise errors.ClientError(response, data)
            case 502:
                raise errors.BadGateway(response, data)
            case status if status >= 500:
                raise errors.InternalServerError(response, data)


@dataclass
class OAuthClient(BaseClient):
    client_id: str
    client_secret: str
    _: dataclasses.KW_ONLY
    base_url: str = "https://hh.ru/oauth"
    state: str = ""
    scope: str = ""
    redirect_uri: str = ""

    @property
    def authorize_url(self) -> str:
        params = dict(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            response_type="code",
            scope=self.scope,
            state=self.state,
        )
        params_qs = urlencode({k: v for k, v in params.items() if v})
        return self.resolve_url(f"/authorize?{params_qs}")

    def request_access_token(self, endpoint: str, params: dict[str, Any] | None = None, **kw: Any) -> AccessToken:
        tok = self.post(endpoint, params, **kw)
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "access_expires_at": int(time.time()) + tok.pop("expires_in", 0),
            "token_type": "bearer",
        }

    def authenticate(self, code: str) -> AccessToken:
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        return self.request_access_token("/token", params)

    def refresh_access_token(self, refresh_token: str) -> AccessToken:
        return self.request_access_token("/token", grant_type="refresh_token", refresh_token=refresh_token)


@dataclass
class ApiClient(BaseClient):
    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_at: int = 0
    client_id: str = ANDROID_CLIENT_ID
    client_secret: str = ANDROID_CLIENT_SECRET
    _: dataclasses.KW_ONLY
    base_url: str = "https://api.hh.ru/"

    def __post_init__(self):
        super().__post_init__()

    @property
    def is_access_expired(self) -> bool:
        return time.time() > self.access_expires_at

    @cached_property
    def oauth_client(self) -> OAuthClient:
        return OAuthClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            session=self.session,
        )

    def additional_headers(
        self,
    ) -> dict[str, str]:
        return {"authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        delay: float | None = None,
        **kwargs: Any,
    ) -> dict:
        def do_request():
            return BaseClient.request(self, method, endpoint, params, delay, **kwargs)

        try:
            return do_request()
        except errors.Forbidden as ex:
            if not self.is_access_expired or not self.refresh_token:
                raise ex
            logger.info("try refresh access_token")
            self.refresh_access_token()
            return do_request()

    def handle_access_token(self, token: AccessToken) -> None:
        for field in ["access_token", "refresh_token", "access_expires_at"]:
            if field in token and hasattr(self, field):
                setattr(self, field, token[field])

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise ValueError("Refresh token required.")
        token = self.oauth_client.refresh_access_token(self.refresh_token)
        self.handle_access_token(token)

    def get_access_token(self) -> AccessToken:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_expires_at": self.access_expires_at,
            "token_type": "bearer",
        }


class HHApi(ApiClient):
    blacklisted_employers: BlacklistedEmployers
    negotiations: Negotiations
    my_resumes: MyResumes
    resume_info: ResumeInfo
    publish_resume: PublishResume
    me: Me
    similar_vacancies: SimilarVacancies
    all_vacancies: AllVacancies
    negotiations_messages: NegotiationsMessages
    vacancy: Vacancy

    def __post_init__(self) -> None:
        super().__post_init__()

        self.blacklisted_employers = BlacklistedEmployers(self)
        self.negotiations = Negotiations(self)
        self.my_resumes = MyResumes(self)
        self.publish_resume = PublishResume(self)
        self.me = Me(self)
        self.similar_vacancies = SimilarVacancies(self)
        self.all_vacancies = AllVacancies(self)
        self.negotiations_messages = NegotiationsMessages(self)
        self.vacancy = Vacancy(self)
        self.resume_info = ResumeInfo(self)
