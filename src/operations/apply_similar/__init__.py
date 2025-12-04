import logging
import random
import time

from api import ApiError, HHApi
from api.errors import LimitExceeded
from api.hh_api.schemas.similar_vacancies import VacancyItem
from mixins import get_resume_id
from operations.apply_similar.utils import get_chat
from operations.apply_similar.utils.negotiations import NegotiationsLLM, NegotiationsLocal
from operations.apply_similar.utils.vacancy_relevance import VacancyRelevanceLLM
from utils import BlockedVacanciesDB, truncate_string
from src.config import Config
from src.operations.apply_similar import base
from typing import List

logger = logging.getLogger(__package__)

class Operation(base.OperationBase):
    """Reply to all relevant vacancies.

    The description of filters u can find here: <https://api.hh.ru/openapi/redoc#tag/Poisk-vakansij-dlya-soiskatelya/operation/get-vacancies-similar-to-resume>
    """
    
    def run(
        self, args: base.Namespace, api_client: HHApi
    ) -> None:
        self.args: base.Namespace = args
        self.config = Config.load(args.config_path)
        
        self.api_client = api_client
        self.resume_id = args.resume_id or get_resume_id(api_client)
        self.application_messages = self._get_application_messages(args.message_list)
        
        if self.args.use_ai:
            negotiations_chat = get_chat(
                self.config.llm.cover_letters.prompts, 
                self.config.llm.cover_letters.options,
                self.config.candidate
                )
            
            self.negotiations_llm = NegotiationsLLM(negotiations_chat)
        else:
            self.negotiations_chat = NegotiationsLocal()
            
        if self.args.verify_relevance: 
            vacancy_relevance_chat = get_chat(
                self.config.llm.verify_relevance.prompts, 
                self.config.llm.verify_relevance.options,
                self.config.candidate
                )
            self.vacancy_relevance_llm = VacancyRelevanceLLM(vacancy_relevance_chat)

        self.apply_min_interval, self.apply_max_interval = args.apply_interval
        self.page_min_interval, self.page_max_interval = args.page_interval

        self._apply_similar()


    def _apply_similar(self) -> None:
        vacancies = self._get_vacancies()

        for vacancy in vacancies:
            if self.args.block_irrelevant: 
                db = BlockedVacanciesDB()
                if db.is_in_list(vacancy.id): 
                    print("Skipping vacancy cause it is in blocked list: %s", vacancy.name)
                    continue
                
            self._apply_vacancy(vacancy)

        print("📝 Отклики на вакансии разосланы!")

    def _apply_vacancy(self, vacancy: VacancyItem) -> bool:
        """
        True: Successfully applied to vacancy
        False: Did not apply to vacancy 
        """
        if vacancy.has_test:
            logger.debug(
                "Пропускаем вакансию с тестом: %s",
                vacancy.alternate_url,
            )
            return False

        if vacancy.archived:
            logger.warning(
                "Пропускаем вакансию в архиве: %s",
                vacancy.alternate_url,
            )
            return False
        
        relations = vacancy.relations
        employer_id = vacancy.employer.id

        if relations:
            logger.debug(
                "Пропускаем вакансию с откликом: %s",
                vacancy.alternate_url,
            )
            return False
        
        if self.args.verify_relevance:
            relevance_result = self.vacancy_relevance_llm.verify(vacancy)
            if not relevance_result: 
                print(
                    "Skipping vacancy cause it is not relevant to candidate: %s %s", 
                    vacancy.name,
                    vacancy.apply_alternate_url
                )
                
                db = BlockedVacanciesDB()
                db.add(vacancy.id)
                
                return False
        
        try:
            self._send_apply(vacancy)
            return True
        except LimitExceeded:
            print("⚠️ Достигли лимита рассылки")
            return False
        except ApiError as ex:
            logger.error(ex)
            return False

    def _send_apply(self, vacancy: VacancyItem):
        """
        Generates cover letter for vacancy(if needed) and send the apply 
        """
        params = {
            "resume_id": self.resume_id,
            "vacancy_id": vacancy.id,
            "message": "",
        }

        if self.args.force_message or vacancy.response_letter_required:
            if self.args.use_ai:
                vacancy_full = self.api_client.vacancy.get(vacancy.id)

                msg = self.negotiations_llm.get_msg(
                    vacancy_full,
                    self.config.llm.cover_letters.messages.footer_msg
                )
                
                if not msg: return
            else:
                me_info = self.api_client.me.get()
                
                msg = self.negotiations_chat.get_msg(me_info, vacancy)
                
            params["message"] = msg

        if self.args.dry_run:
            logger.info(
                "Dry Run: Отправка отклика на вакансию %s с параметрами: %s",
                vacancy.alternate_url,
                params,
            )
            return

        interval = random.uniform(
            self.apply_min_interval, self.apply_max_interval
        )
        time.sleep(interval)

        res = self.api_client.negotiations.post(params)
        
        print(
            "📨 Отправили отклик",
            vacancy.alternate_url,
            "(",
            truncate_string(vacancy.name),
            ")",
        )


    def _get_vacancies(self, per_page: int = 100) -> List[VacancyItem]:
        rv = []
        # API gives only 2 000 items
        for page in range(20):
            params = self._get_search_params(self.args, page, per_page)
            vacancies = self.api_client.similar_vacancies.get(
                self.resume_id,
                params
                )
            
            rv.extend(vacancies.items)
            if page >= vacancies.pages - 1:
                break

            # Timeout before fetching next page
            if page > 0:
                interval = random.uniform(
                    self.page_min_interval, self.page_max_interval
                )
                time.sleep(interval)

        return rv
