from typing import Any

from requests import PreparedRequest, Response
from requests.adapters import CaseInsensitiveDict

__all__ = (
    "ApiError",
    "BadGateway",
    "BadRequest",
    "ClientError",
    "Forbidden",
    "InternalServerError",
    "Redirect",
    "ResourceNotFound",
)


class ApiError(Exception):
    def __init__(self, response: Response, data: dict[str, Any]) -> None:
        self._response = response
        self._raw = data

    @property
    def data(self) -> dict:
        return self._raw

    @property
    def request(self) -> PreparedRequest:
        return self._response.request

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def response_headers(self) -> CaseInsensitiveDict:
        return self._response.headers

    def __str__(self) -> str:
        return str(self._raw)

    @staticmethod
    def is_limit_exceeded(data) -> bool:
        return any(x["value"] == "limit_exceeded" for x in data.get("errors", []))


class Redirect(ApiError):
    pass


class ClientError(ApiError):
    pass


class BadRequest(ClientError):
    pass


class LimitExceeded(ClientError):
    pass


class Forbidden(ClientError):
    pass


class ResourceNotFound(ClientError):
    pass


class InternalServerError(ApiError):
    pass


class BadGateway(InternalServerError):
    pass
