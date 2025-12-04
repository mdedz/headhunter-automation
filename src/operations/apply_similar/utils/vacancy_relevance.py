from dataclasses import dataclass
import logging
from ai.base import BaseLLM, LLMError
from api.hh_api.schemas.similar_vacancies import VacancyItem
from operations.vacancy.actions import serialize_for_llm

logger = logging.getLogger(__package__)


@dataclass
class VacancyRelevanceLLM:
    chat: BaseLLM
    
    def verify(self, vacancy: VacancyItem):
        try:                    
            return self._get_cover_letter(vacancy)
        except LLMError as ex:
            logger.error(ex)
            return
        
    def _get_cover_letter(self, vacancy: VacancyItem, footer_msg: str = "") -> str:
        vacancy_info = serialize_for_llm(vacancy)
        logger.debug("AI prompt:\n%s", vacancy_info)
        
        msg = self.chat.send_message(vacancy_info, verify_tag_end=True)
        
        logger.debug(f"LLM cover letter is: {msg}")
        return msg

