import argparse
import logging
import random
import re
import time
from itertools import count
from typing import List, Tuple
from prompt_toolkit import prompt

from api.hh_api.schemas.negotiations import Employer, NegotiationItem, SalaryRange, Vacancy
from api.hh_api.schemas.negotiations_messages import NegotiationsMessagesItem
from mixins import get_resume_id
from operations.reply_employers.utils import NegotiationCommandType, get_message_history, parse_input, print_negotiation_header, process_ai, process_ban, process_cancel, process_send_msg, should_reply_to_negotiation

from src.api import ApiError, HHApi
from src.main import BaseOperation
from src.main import Namespace as BaseNamespace
from src.utils import parse_interval, random_text
from src.config import Config


GOOGLE_DOCS_RE = re.compile(
    r"\b(?:https?:\/\/)?(?:docs|forms|sheets|slides|drive)\.google\.com\/(?:document|spreadsheets|presentation|forms|file)\/(?:d|u)\/[a-zA-Z0-9_\-]+(?:\/[a-zA-Z0-9_\-]+)?\/?(?:[?#].*)?\b|\b(?:https?:\/\/)?(?:goo\.gl|forms\.gle)\/[a-zA-Z0-9]+\b",
    re.I,
)

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    reply_message: str
    reply_interval: Tuple[float, float]
    max_pages: int
    only_invitations: bool


class Operation(BaseOperation):
    """Replies to all employers."""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--resume-id", help="Идентификатор резюме")
        parser.add_argument(
            "-i",
            "--reply-interval",
            help="Интервал перед отправкой сообщения в секундах (X, X-Y)",
            default="5-10",
            type=parse_interval,
        )
        parser.add_argument(
            "-m",
            "--reply-message",
            "--reply",
            help="Отправить сообщение во все чаты, где ожидают ответа либо не прочитали ответ. Если не передать сообщение, то нужно будет вводить его в интерактивном режиме.",
        )
        parser.add_argument(
            "-p",
            "--max-pages",
            type=int,
            default=25,
            help="Максимальное количество страниц для проверки",
        )
        parser.add_argument(
            "-oi",
            "--only-invitations",
            help="Отвечать только на приглашения",
            default=False,
            action=argparse.BooleanOptionalAction,
        )

    def run(
        self, args: Namespace, api_client: HHApi
    ) -> None:
        self.api_client: HHApi = api_client

        self.resume_id = get_resume_id(self.api_client)
        self.reply_min_interval, self.reply_max_interval = args.reply_interval

        #TODO: add to config reply message value        
        self.reply_message = args.reply_message or ""
        # assert self.reply_message, "`reply_message` must be defined in settings or args"
        self.max_pages = args.max_pages
        self.only_invitations = args.only_invitations
        logger.debug(f"{self.reply_message = }")
        self._reply_chats()

    def _get_blacklisted(self) -> list[str]:
        """Return list of blacklisted employers ids"""
        rv = []
        # In this api method pages count from 0
        for page in count(0):
            r = self.api_client.blacklisted_employers.get(page=page)
            rv += [item.id for item in r.items]
            if page + 1 >= r.pages:
                break
        return rv

    def _reply_chats(self) -> None:
        blacklisted = self._get_blacklisted()
        logger.debug(f"blacklisted: {blacklisted}")
        me = self.me = self.api_client.get("/me")

        basic_message_placeholders = {
            "first_name": me.get("first_name", ""),
            "last_name": me.get("last_name", ""),
            "email": me.get("email", ""),
            "phone": me.get("phone", ""),
        }

        for negotiation in self._get_negotiations():
            try:
                # Skipping other resumes
                if not should_reply_to_negotiation(self.only_invitations, self.resume_id, negotiation, blacklisted): 
                    continue
                
                vacancy: Vacancy | None = negotiation.vacancy
                assert vacancy is not None
                salary: SalaryRange | None = vacancy.salary_range
                employer: Employer | None = vacancy.employer
                assert employer is not None
                
                message_placeholders = {
                    "vacancy_name": vacancy.name,
                    "employer_name": employer.name,
                    **basic_message_placeholders,
                }

                logger.debug(
                    "Вакансия %(vacancy_name)s от %(employer_name)s"
                    % message_placeholders
                )

                nid = negotiation.id
                message_history, last_message = get_message_history(self.api_client, nid)
                logger.debug("Last msg is %s", last_message)

                is_employer_message = (
                    last_message.author.participant_type == "employer"
                )

                if is_employer_message or not negotiation.viewed_by_opponent:
                    if self.reply_message:
                        msg_to_send = (
                            random_text(self.reply_message) % message_placeholders
                        )
                        logger.debug("Msg to send: %s", msg_to_send)
                        process_send_msg(self.api_client, msg_to_send, vacancy, nid)
                    else:
                        print_negotiation_header(message_history, message_placeholders, vacancy, salary)
                        self._parse_input(employer, vacancy, negotiation, blacklisted, message_history)
                        
                    time.sleep(
                        random.uniform(
                            self.reply_min_interval,
                            self.reply_max_interval,
                        )
                    )

            except ApiError as ex:
                logger.error(ex)

        print("📝 Сообщения разосланы!")

    def _parse_input(
        self, 
        employer: Employer, 
        vacancy: Vacancy, 
        negotiation: NegotiationItem, 
        blacklisted: List[str],
        message_history: List[str]
        ) -> bool:
        def_input_text = ""
        while 1:
            try:
                msg_to_send = prompt("Ваше сообщение: ", default=def_input_text).strip()
            except EOFError:
                return False
            
            if not msg_to_send:
                print("🚶 Пропускаем чат")
                return False
            
            cmd = parse_input(msg_to_send)
            match cmd.type:
                case NegotiationCommandType.BAN:
                    return process_ban(self.api_client, employer, blacklisted)
                case NegotiationCommandType.CANCEL:
                    return process_cancel(self.api_client, cmd.data['decline_allowed'], vacancy, negotiation.id)
                case NegotiationCommandType.AI:
                    msg: str = "Сообщения в чате:\n " "\n".join(message_history) + "\n" + "Ввод пользователя:\n" + cmd.data['msg']
                    def_input_text = process_ai(msg)
                    continue
                case NegotiationCommandType.MESSAGE:
                    return process_send_msg(self.api_client, msg_to_send, vacancy, negotiation.id)
        return False
    
    def _get_negotiations(self) -> List[NegotiationItem]:
        rv = []
        for page in range(self.max_pages):
            res = self.api_client.negotiations.get(page=page, status="active")
            rv.extend(res.items)
            if page >= res.pages - 1:
                break
            page += 1

        return rv
