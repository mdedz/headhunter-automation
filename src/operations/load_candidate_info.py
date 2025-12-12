import argparse
import logging

from ai import LLMFactory, Prompts
from ai.base import ModelConfig
from ai.utils import get_chat, get_prompts
from api.hh_api.schemas.my_resumes import GetResumesResponse
from api.hh_api.schemas.resume_info import ResumeInfoResponse
from config import Config

from ..api import ApiError, HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import print_err, truncate_string

logger = logging.getLogger(__package__)

def _ask_for_resume_index(resumes_len: int) -> int | None:
    """
    Returns None if user wants to build on all resumes 
    Otherwise returns index of resume in GetResumesResponse
    """
    
    resume_index = input("Выберите id резюме или Enter без значения, если хотите строить промпт на всех: ")
    if resume_index == "":
        return
    
    if not resume_index.isnumeric(): 
        print_err("Введите корректный числовой резюме id ")
        
    resume_index = int(resume_index)
    if int(resume_index) < 0 or int(resume_index) >= resumes_len:
        print_err("Вы ввели некорректный резюме id")
    
    return resume_index

def _confirm_config_change() -> bool:
    while True:
        choice = input("Вы уверены, что хотите изменить конфиг? (y/n): ").strip().lower()
        if choice in ("y", "yes", "д", "да"):
            return True
        elif choice in ("n", "no", "н", "нет"):
            return False
        else:
            print("Пожалуйста, введите 'y' или 'n'.")

    
class Namespace(BaseNamespace):
    pass


class Operation(BaseOperation):
    """Populate candidate_info from your resumes"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        self.api_client = api_client
        
        resumes: GetResumesResponse = api_client.my_resumes.get()
        for i, resume in enumerate(resumes.items):
            print(f"{i}: Резюме: {resume.title}")
            
        resume_index = _ask_for_resume_index(len(resumes.items))
        resume_id = resumes.items[resume_index].id if resume_index is not None else None 
        
        logger.debug(f"Chosen resume id is {resume_id}")
        prompt = self.build_prompt(resumes, resume_id)
        candidate_info = self.build_candidate_info(prompt)
        self.update_config(candidate_info)
        
    def update_config(self, candidate_info: str):
        cfg = Config.load()
        if _confirm_config_change():
            cfg.update("candidate.info", candidate_info)
            cfg.save()
        
    def build_candidate_info(self, resume_serialized: str):
        cfg = Config.load()

        prompts = get_prompts(cfg.llm.resume_builder.prompts, cfg.candidate)
        resume_builder_chat = get_chat(prompts, cfg.llm.resume_builder.options)
        
        return resume_builder_chat.send_message(resume_serialized, True)    
        
    def build_prompt(self, resumes: GetResumesResponse, resume_id_to_serialize: str | None = None) -> str:
        resume_ids_to_serialize = [resume_id_to_serialize] if resume_id_to_serialize else [resume.id for resume in resumes.items]
        
        serialized_list: list[str] = []
        for resume_id in resume_ids_to_serialize:
            resume_info = self.api_client.resume_info.get(resume_id)
            
            serialized = self.serialize_resume_info(resume_info)
            serialized_list.append(serialized)
            
        serialized_text = "\n".join(serialized_list)
        logger.debug(f"Built prompt for AI to construct candidate info is {serialized_text}")
        return serialized_text
                
    @staticmethod
    def serialize_resume_info(resume: ResumeInfoResponse) -> str:
        parts = []

        parts.append(f"Title: {resume.title}")

        if resume.professional_roles:
            roles = ", ".join([r.name for r in resume.professional_roles])
            parts.append(f"Professional roles: {roles}")

        if resume.skill_set:
            parts.append("Skill set: " + ", ".join(resume.skill_set))

        if resume.total_experience and resume.total_experience.months:
            months = resume.total_experience.months
            years = months // 12
            rest = months % 12
            if years > 0:
                parts.append(f"Total experience: {years} years {rest} months")
            else:
                parts.append(f"Total experience: {months} months")

        if resume.experience:
            exp_lines = []
            for e in resume.experience:
                company = e.company or "—"
                desc = e.description or ""
                exp_lines.append(
                    f"- {e.position} at {company} ({e.start} — {e.end or 'now'})\n  {desc}"
                )
            parts.append("Experience:\n" + "\n".join(exp_lines))

        if resume.education:
            edu_lines = []

            if resume.education.primary:
                for p in resume.education.primary:
                    edu_lines.append(
                        f"- {p.organization or p.name}, {p.result or '—'}, {p.year or '—'}"
                    )

            if resume.education.additional:
                for a in resume.education.additional:
                    edu_lines.append(
                        f"- Course: {a.name}, {a.organization or '—'}, {a.year}"
                    )

            if resume.education.attestation:
                for a in resume.education.attestation:
                    edu_lines.append(
                        f"- Attestation: {a.name}, {a.organization or '—'}, {a.year}"
                    )

            parts.append("Education:\n" + "\n".join(edu_lines))

        if resume.language:
            lang_lines = [
                f"- {l.name}: {l.level.name}"
                for l in resume.language
            ]
            parts.append("Languages:\n" + "\n".join(lang_lines))

        return "\n".join(parts)
