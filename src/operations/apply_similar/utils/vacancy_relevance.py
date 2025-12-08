import logging
from dataclasses import dataclass

from ai.base import BaseLLM, LLMError
from api.hh_api.schemas.similar_vacancies import VacancyItem

logger = logging.getLogger(__package__)

def _serialize_for_llm(vacancy: VacancyItem) -> str:
    return (
        f"Требования: {vacancy.snippet.requirement}\n"
        f"Обязанности: {vacancy.snippet.responsibility}\n"
    )

@dataclass
class VacancyRelevanceLLM:
    chat: BaseLLM

    def verify(self, vacancy: VacancyItem):
        try:
            return self._verify(vacancy)
        except LLMError as ex:
            logger.error(ex)
            return True

    def _verify(self, vacancy: VacancyItem, footer_msg: str = "") -> bool:
        vacancy_info = _serialize_for_llm(vacancy)
        logger.debug("AI prompt:\n%s", vacancy_info)

        msg = self.chat.send_message(vacancy_info)
        if msg.isdigit():
            return int(msg) == 1

        return True

