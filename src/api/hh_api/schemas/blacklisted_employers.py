from dataclasses import dataclass
from typing import List, Optional


# GET https://api.hh.ru/employers/blacklisted
@dataclass
class LogoUrls:
    url_90: Optional[str] = None
    url_240: Optional[str] = None
    original: Optional[str] = None


@dataclass
class EmployerItem:
    alternate_url: Optional[str]
    id: str
    logo_urls: LogoUrls
    name: str
    open_vacancies: int
    url: str
    vacancies_url: Optional[str]


@dataclass
class GetBlacklistedEmployersResponse:
    found: int
    items: List[EmployerItem]
    limit_reached: bool
    page: int
    pages: int
    per_page: int


@dataclass
class PutBlacklistedEmployersError:
    type: str
    value: str

# PUT https://api.hh.ru/vacancies/blacklisted/{vacancy_id}

@dataclass
class PutBlacklistedEmployersResponse:
    request_id: str
    description: Optional[str]
    errors: List[PutBlacklistedEmployersError]
