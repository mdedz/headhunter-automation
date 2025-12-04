from dataclasses import dataclass
import logging
import random
from typing import List, TextIO
from ai.base import BaseLLM, LLMError
from api.hh_api.schemas.me import MeResponse
from api.hh_api.schemas.similar_vacancies import VacancyItem
from utils import random_text

logger = logging.getLogger(__package__)

def _serialize_for_llm(vacancy: VacancyItem) -> str:
    vacancy_info = {
        "vacancy_name": vacancy.name,
        "employer_name": vacancy.employer.name,
        "vacancy_url": vacancy.alternate_url,
        "requirements": vacancy.snippet.requirement,
        "responsibilities": vacancy.snippet.responsibility,
    }

    return (
        f"Вакансия: {vacancy_info['vacancy_name']}\n"
        f"Компания: {vacancy_info['employer_name']}\n"
        f"Требования: {vacancy_info['requirements']}\n"
        f"Обязанности: {vacancy_info['responsibilities']}\n"
    )
    
@dataclass
class NegotiationsLLM:
    chat: BaseLLM
    
    def get_msg(self, vacancy: VacancyItem, footer_msg: str = ""):
        try:                    
            return self._get_msg(vacancy, footer_msg)
        except LLMError as ex:
            logger.error(ex)
            return
        
    def _get_msg(self, vacancy: VacancyItem, footer_msg: str = "") -> str:
        vacancy_info = _serialize_for_llm(vacancy)
        logger.debug("AI prompt:\n%s", vacancy_info)
        
        msg = self.chat.send_message(vacancy_info, verify_tag_end=True)
        
        msg += "\n" + footer_msg + "\n"
        logger.debug(f"LLM cover letter is: {msg}")
        return msg
        

class NegotiationsLocal:
    def get_msg(self, 
                me_info: MeResponse, 
                vacancy: VacancyItem, 
        ):
        application_msgs = self._get_application_messages() 

        return self._get_random_predefined_msg(application_msgs, me_info, vacancy)
    
    @staticmethod
    def _get_application_messages(message_list: TextIO | None = None) -> list[str]:
        if message_list:
            application_messages = list(filter(None, map(str.strip, message_list)))
        else:
            application_messages = [
                "{Меня заинтересовала|Мне понравилась} ваша вакансия %(vacancy_name)s",
                "{Прошу рассмотреть|Предлагаю рассмотреть} {мою кандидатуру|мое резюме} на вакансию %(vacancy_name)s",
            ]
        return application_messages

    @staticmethod
    def _get_random_predefined_msg(msg_template: List[str], user_info: MeResponse, vacancy: VacancyItem):
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

        logger.debug(
            "Вакансия %(vacancy_name)s от %(employer_name)s"
            % message_placeholders
        )
        
        msg = (
            random_text(random.choice(msg_template))
            % message_placeholders
        )
        return msg
    