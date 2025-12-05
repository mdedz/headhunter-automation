from dataclasses import dataclass
from typing import List

# GET https://api.hh.ru/resumes/mine

@dataclass
class Status:
    id: str
    name: str


@dataclass
class ResumeItem:
    id: str
    title: str | None
    status: Status


@dataclass
class GetResumesResponse:
    items: List[ResumeItem]
