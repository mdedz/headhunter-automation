from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ResumeExperience:
    start: str
    end: Optional[str]
    company: str | None
    position: str
    description: Optional[str]

@dataclass
class EducationCourse:
    id: Optional[str]
    name: str
    organization: Optional[str]
    result: Optional[str]
    year: int


@dataclass
class ElementaryEducation:
    id: Optional[str]
    name: str
    year: int

@dataclass
class EducationLevel:
    id: str
    name: str
    
@dataclass
class ResumeEducation:
    primary: Optional[List[EducationCourse]]
    additional: Optional[List[EducationCourse]]
    attestation: Optional[List[EducationCourse]]
    elementary: Optional[List[ElementaryEducation]]
    level: EducationLevel

@dataclass
class ProfessionalRoles:
    id: str
    name: str
    
@dataclass
class LanguageLevel:
    id: str
    name: str
    
@dataclass
class Language:
    id: str
    name: str
    level: LanguageLevel

@dataclass
class TotalExperience:
    months: int | None

@dataclass
class ResumeInfoResponse:
    title: str
    professional_roles: List[ProfessionalRoles] | None
    skill_set: List[str]
    experience: List[ResumeExperience]
    education: ResumeEducation
    language: List[Language]
    total_experience: TotalExperience | None 