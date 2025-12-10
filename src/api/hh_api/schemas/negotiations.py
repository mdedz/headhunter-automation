from dataclasses import dataclass
from typing import List

from api.hh_api.schemas.objects import SalaryRange


@dataclass
class PhoneCallItem:
    creation_time: str
    duration_seconds: int | None
    id: str
    last_change_time: str | None
    status: str


@dataclass
class PhoneCalls:
    items: List[PhoneCallItem]
    picked_up_phone_by_opponent: bool


@dataclass
class NegotiationState:
    id: str
    name: str


@dataclass
class NegotiationTag:
    id: str


@dataclass
class Employer:
    id: str | None
    alternate_url: str | None
    name: str


@dataclass
class Vacancy:
    id: str
    alternate_url: str
    name: str
    employer: Employer | None
    salary_range: SalaryRange | None
    created_at: str


@dataclass
class Resume:
    id: str
    title: str
    alternate_url: str
    url: str


@dataclass
class NegotiationItem:
    decline_allowed: bool
    has_updates: bool
    hidden: bool
    id: str
    messaging_status: str
    phone_calls: PhoneCalls | None
    source: str | None
    state: NegotiationState
    tags: List[NegotiationTag] | None
    created_at: str
    updated_at: str
    url: str
    viewed_by_opponent: bool
    vacancy: Vacancy | None
    resume: Resume | None


# GET https://api.hh.ru/negotiations
@dataclass
class GetNegotiationsListResponse:
    found: int
    items: List[NegotiationItem]
    page: int
    pages: int
    per_page: int


@dataclass
class ErrorItem:
    type: str
    value: str


# DELETE https://api.hh.ru/negotiations/active/{nid}


@dataclass
class DeleteNegotiationsResponse:
    request_id: str
    description: str
    errors: List[ErrorItem]
    oauth_error: str
