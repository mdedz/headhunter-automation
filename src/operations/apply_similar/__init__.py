import logging
import random
import time
from typing import TextIO

from api.hh_api.schemas.me import MeResponse
from api.hh_api.schemas.similar_vacancies import VacancyItem
from mixins import get_resume_id
from operations.vacancy.actions import block_vacancy

from src import ai
from src.ai.base import LLMError, ModelConfig, Prompts
from src.config import Config, LLMOptions, LLMPrompts
from src.operations.apply_similar import base
from typing import List
from ...api import HHApi, ApiError
from ...api.errors import LimitExceeded
from ...utils import (
    BlockedVacanciesDB,
    random_text,
    truncate_string,
)

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
        
        self.cover_letter_chat = self._get_chat(
            self.config.llm.cover_letters.prompts, 
            self.config.llm.cover_letters.options
            ) if self.args.force_message else None
        
        self.verify_relevance_chat = self._get_chat(
            self.config.llm.verify_relevance.prompts, 
            self.config.llm.verify_relevance.options
            ) if self.args.verify_relevance else None

        self.apply_min_interval, self.apply_max_interval = args.apply_interval
        self.page_min_interval, self.page_max_interval = args.page_interval

        self._apply_similar()

    def _get_chat(self, cfg_prompts: LLMPrompts, options: LLMOptions):
        cfg = ModelConfig(
            options.model_name,
            options.api_key,
            options.temperature,
            options.max_tokens,
            options.top_p,
            )
        
        system_prompt = cfg_prompts.system + "\n" + self.config.candidate.info 
        
        prompts = Prompts(
            system_prompt
        )
        
        return ai.LLMFactory.create(options.provider, cfg, prompts)

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
        
        if self.args.verify_relevance and (not self._verify_relevance(vacancy)): 
            print(
                "Skipping vacancy cause it is not relevant to candidate: %s %s", 
                vacancy.name,
                vacancy.apply_alternate_url
            )
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
        
    def _verify_relevance(self, vacancy: VacancyItem) -> bool:
        """
        True: Is relevant to candidate
        False: Is not relevant to candidate
        """
        if not (self.verify_relevance_chat and self.args.verify_relevance): 
            return True
        
        vacancy_info = self._get_vacancy_info_for_llm(vacancy)
        resp = self.verify_relevance_chat.send_message(vacancy_info).strip()
        
        logger.debug(f"Verify relevance resp is: {resp} for vacancy {vacancy.alternate_url}")
        if resp.isnumeric():
            r = bool(int(resp) == 1)
            if not r and self.args.block_irrelevant: 
                logger.info("Blocking vacancy with name: %s", vacancy.name)
                block_vacancy(vacancy.id)
            return r
        
        else: return True
        
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
            if self.args.use_ai and self.cover_letter_chat:
                try:                    
                    msg = self._get_msg_from_llm(vacancy)
                except LLMError as ex:
                    logger.error(ex)
                    return
            else:
                me = self.api_client.me.get()
                application_msgs = self._get_application_messages() 

                msg = self._get_random_predefined_msg(application_msgs, me, vacancy)

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
        
    def _get_msg_from_llm(self, vacancy: VacancyItem):
        if not self.cover_letter_chat: raise Exception("Cover letter chat is not declared")
        
        vacancy_info = self._get_vacancy_info_for_llm(vacancy)
        logger.debug("AI prompt:\n%s", vacancy_info)
        
        msg = self.cover_letter_chat.send_message(vacancy_info, verify_tag_end=True)
        msg += "\n" + self.config.llm.cover_letters.messages.footer_msg + "\n"
        logger.debug(f"LLM cover letter is: {msg}")
        return msg
        
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
    def _get_vacancy_info_for_llm(vacancy: VacancyItem) -> str:
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