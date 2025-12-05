from __future__ import annotations

import argparse
import logging
import random
import re
import time
from itertools import count
from typing import List, Tuple

from api.hh_api.schemas.negotiations import NegotiationItem, SalaryRange
from api.hh_api.schemas.negotiations_messages import NegotiationsMessagesItem
from mixins import get_resume_id

from ..api import ApiError, HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import parse_interval, random_text

try:
    import readline

    readline.add_history("/cancel ")
    readline.add_history("/ban")
    readline.set_history_length(10_000)
except ImportError:
    pass


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
    dry_run: bool


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

        parser.add_argument(
            "--dry-run",
            "--dry",
            help="Не отправлять сообщения, а только выводить параметры запроса",
            default=False,
            action=argparse.BooleanOptionalAction,
        )

    def run(
        self, args: Namespace, api_client: HHApi
    ) -> None:
        self.api_client = api_client

        self.resume_id = get_resume_id(self.api_client)
        self.reply_min_interval, self.reply_max_interval = args.reply_interval
        self.reply_message = args.reply_message or args.config["reply_message"]
        # assert self.reply_message, "`reply_message` must be defined in settings or args"
        self.max_pages = args.max_pages
        self.dry_run = args.dry_run
        self.only_invitations = args.only_invitations
        logger.debug(f"{self.reply_message = }")
        self._reply_chats()

    def _get_blacklisted(self) -> list[str]:
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
        logger.debug(f"{blacklisted = }")
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
                resume = negotiation.resume
                if resume is None:
                    logger.debug("Skipping negotiations resume is none")
                    continue

                if self.resume_id != resume.id:
                    continue

                state_id = negotiation.state.id

                # skipping discard
                if state_id == "discard":
                    continue

                if self.only_invitations and not state_id.startswith("inv"):
                    continue

                logger.debug(negotiation)

                nid = negotiation.id

                vacancy = negotiation.vacancy
                if vacancy is None:
                    logger.debug("Skipping negotiations without vacancy defined")
                    continue

                employer = vacancy.employer
                if employer is None:
                    logger.debug("Skipping: vacancy.employer = None")
                    continue

                salary: SalaryRange = vacancy.salary_range

                if employer.id in blacklisted:
                    print(
                        "🚫 Пропускаем заблокированного работодателя",
                        employer.alternate_url,
                    )
                    continue

                message_placeholders = {
                    "vacancy_name": vacancy.name,
                    "employer_name": employer.name,
                    **basic_message_placeholders,
                }

                logger.debug(
                    "Вакансия %(vacancy_name)s от %(employer_name)s"
                    % message_placeholders
                )

                page: int = 0
                last_message: NegotiationsMessagesItem | None = None
                message_history: list[str] = []
                while True:
                    messages_res = self.api_client.negotiations_messages.get(
                        nid, page=page
                    )

                    items = messages_res.items

                    last_message = items[-1]
                    message_history.extend(
                        (
                            "<-"
                            if item.author.participant_type == "employer"
                            else "->"
                        )
                        + " "
                        + item.text
                        for item in items
                        if item.text
                    )
                    if page + 1 >= messages_res.pages:
                        break

                    page = messages_res.pages - 1

                logger.debug(last_message)

                is_employer_message = (
                    last_message.author.participant_type == "employer"
                )

                if is_employer_message or not negotiation.viewed_by_opponent:
                    if self.reply_message:
                        send_message = (
                            random_text(self.reply_message) % message_placeholders
                        )
                        logger.debug(send_message)
                    else:
                        print("🏢", message_placeholders["employer_name"])
                        print("💼", message_placeholders["vacancy_name"])
                        print("📅", vacancy.created_at)
                        if salary:
                            salary_from = salary.from_int or "-"
                            salary_to = salary.to_int or "-"
                            salary_currency = salary.currency
                            print(
                                "💵 от", salary_from, "до", salary_to, salary_currency
                            )
                        print("")
                        print("Последние сообщения:")
                        for msg in (
                            message_history[:1] + ["..."] + message_history[-3:]
                            if len(message_history) > 5
                            else message_history
                        ):
                            print(msg)
                        try:
                            print("-" * 10)
                            print()
                            print(
                                "Отмена отклика: /cancel <необязательное сообщение для отказа>"
                            )
                            print("Заблокировать работодателя: /ban")
                            print()
                            send_message = input("Ваше сообщение: ").strip()
                        except EOFError:
                            continue
                        if not send_message:
                            print("🚶 Пропускаем чат")
                            continue

                    if self.dry_run:
                        logger.info(
                            "Dry Run: Отправка сообщения в чат по вакансии %s: %s",
                            vacancy.alternate_url,
                            send_message,
                        )
                        continue

                    time.sleep(
                        random.uniform(
                            self.reply_min_interval,
                            self.reply_max_interval,
                        )
                    )

                    if send_message.startswith("/ban"):
                        employer_id = employer.id
                        if employer_id is None:
                            logger.debug("Employer id is none")
                            continue

                        self.api_client.blacklisted_employers.put(employer_id)
                        blacklisted.append(employer_id)
                        print(
                            "🚫 Работодатель добавлен в черный список",
                            employer.alternate_url,
                        )
                    elif send_message.startswith("/cancel"):
                        _, decline_allowed = send_message.split("/cancel", 1)
                        self.api_client.negotiations.delete(
                            negotiation.id,
                            with_decline_message=decline_allowed.strip(),
                        )
                        print("❌ Отменили заявку", vacancy.alternate_url)
                    else:
                        self.api_client.negotiations.post(
                            nid,
                            message=send_message,
                        )
                        print(
                            "📨 Отправили сообщение для",
                            vacancy.alternate_url,
                        )
            except ApiError as ex:
                logger.error(ex)

        print("📝 Сообщения разосланы!")

    def _get_negotiations(self) -> List[NegotiationItem]:
        rv = []
        for page in range(self.max_pages):
            res = self.api_client.negotiations.get(page=page, status="active")
            rv.extend(res.items)
            if page >= res.pages - 1:
                break
            page += 1

        return rv
