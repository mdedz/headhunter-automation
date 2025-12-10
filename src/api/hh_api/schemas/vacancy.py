from dataclasses import dataclass
from typing import List


@dataclass
class Employer:
    id: str | None
    name: str


@dataclass
class KeySkills:
    name: str


@dataclass
class Experience:
    id: str
    name: str


@dataclass
class VacancyFull:
    name: str
    key_skills: List[KeySkills]
    description: str
    experience: Experience
    employer: Employer
