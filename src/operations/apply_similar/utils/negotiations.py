import logging
import random
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ai.base import BaseLLM, LLMError
from api.hh_api.schemas.me import MeResponse
from api.hh_api.schemas.vacancies import VacancyItem
from api.hh_api.schemas.vacancy import VacancyFull
from config import DefaultCoverLetter
from utils import random_text

logger = logging.getLogger(__package__)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.extract()

    return soup.get_text(separator=" ", strip=True)


def _serialize_for_llm(vacancy: VacancyFull) -> str:
    key_skills = " ".join([x.name for x in vacancy.key_skills])
    description = html_to_text(vacancy.description)
    vacancy_info = {
        "vacancy_name": vacancy.name,
        "employer_name": vacancy.employer.name,
        "key_skills": key_skills,
        "description": description,
        "experience": vacancy.experience.name,
    }

    return (
        f"Вакансия: {vacancy_info['vacancy_name']}\n"
        f"Компания: {vacancy_info['employer_name']}\n"
        f"Навыки: {vacancy_info['key_skills']}\n"
        f"Описание: {vacancy_info['description']}\n"
        f"Опыт: {vacancy_info['experience']}\n"
    )


@dataclass
class NegotiationsLLM:
    chat: BaseLLM

    def get_msg(self, vacancy_full: VacancyFull, footer_msg: str = ""):
        try:
            return self._get_msg(vacancy_full, footer_msg)
        except LLMError as ex:
            logger.error(ex)
            return

    def _get_msg(self, vacancy_full: VacancyFull, footer_msg: str = "") -> str:
        vacancy_info = _serialize_for_llm(vacancy_full)
        logger.debug(f"AI prompt:\n {vacancy_info}")

        msg = self.chat.send_message(vacancy_info, verify_tag_end=True)

        msg += "\n\n" + footer_msg + "\n"
        logger.debug(f"LLM cover letter is: {msg}")
        return msg


@dataclass
class NegotiationsLocal:
    messages_list: DefaultCoverLetter

    def get_msg(self, user_info: MeResponse, vacancy: VacancyItem):
        msg_template = self._get_msg()

        basic_message_placeholders = {
            "first_name": user_info.first_name,
            "last_name": user_info.last_name,
            "email": user_info.email,
            "phone": user_info.phone,
        }

        message_placeholders = {
            "vacancy_name": vacancy.name,
            "employer_name": vacancy.employer.name,
            **basic_message_placeholders,
        }

        logger.debug("Вакансия %(vacancy_name)s от %(employer_name)s" % message_placeholders)

        msg = random_text(random.choice(msg_template)) % message_placeholders
        return msg

    def _get_msg(self) -> list[str]:
        logger.warning(f"local negotiations Msg {self.messages_list.messages}")
        application_messages = list(filter(None, map(str.strip, self.messages_list.messages)))

        return application_messages
