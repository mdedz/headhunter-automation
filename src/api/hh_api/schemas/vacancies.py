from dataclasses import dataclass
from typing import List

from api.hh_api.schemas.objects import SalaryRange


@dataclass
class Employer:
    id: str | None
    name: str


@dataclass
class Snippet:
    requirement: str | None
    responsibility: str | None


@dataclass
class Experience:
    id: str | None
    name: str | None


@dataclass
class VacancyItem:
    address: dict | None
    alternate_url: str
    apply_alternate_url: str
    area: dict
    contacts: dict | None
    counters: dict | None
    department: dict | None
    employer: Employer
    has_test: bool
    id: str
    insider_interview: dict | None
    name: str
    professional_roles: list
    published_at: str
    relations: list
    response_letter_required: bool
    response_url: str | None
    salary_range: SalaryRange | None
    snippet: Snippet
    sort_point_distance: float | None
    type: dict
    url: str
    experience: Experience | None
    archived: bool | None


# GET https://api.hh.ru/resumes/{resume_id}/similar_vacancies


@dataclass
class VacanciesResponse:
    items: List[VacancyItem]
    pages: int
