import argparse
import logging
import datetime
from datetime import timedelta
from typing import List

from api.hh_api.schemas.blacklisted_employers import PutBlacklistedEmployersResponse
from api.hh_api.schemas.negotiations import (
    Employer,
    GetNegotiationsListResponse,
    NegotiationItem,
    NegotiationState,
    Vacancy,
)

from api import ClientError, HHApi
from constants import INVALID_ISO8601_FORMAT
from main import BaseOperation
from main import Namespace as BaseNamespace
from utils import print_err, truncate_string
from tqdm import tqdm

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    older_than: int
    blacklist_discard: bool
    all: bool


class Operation(BaseOperation):
    """Declines old replies, hides discards with optional block of employer."""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--older-than",
            type=int,
            default=30,
            help="Удалить отклики старше опр. кол-ва дней. По умолчанию: %(default)d",
        )

        parser.add_argument(
            "--all",
            type=bool,
            default=False,
            action=argparse.BooleanOptionalAction,
            help="Удалить все отклики в тч с приглашениями",
        )
        parser.add_argument(
            "--blacklist-discard",
            help="Если установлен, то заблокирует работодателя в случае отказа, чтобы его вакансии не отображались в возможных",
            type=bool,
            default=False,
            action=argparse.BooleanOptionalAction,
        )

    def _get_active_negotiations(self, api_client: HHApi) -> List[NegotiationItem]:
        """
        Fetch all non-archived active negotiations.

        Pages through HH API until all items are collected.
        Returns:
            List of NegotiationItem
        """
        # Statuses can be
        # id: all, name: Все
        # id: active, name: Активные
        # id: invitations, name: Активные приглашения
        # id: response, name: Активные отклики
        # id: discard, name: Отказ
        # id: archived, name: Архивированные
        # id: non_archived, name: Все, кроме архивированных
        # id: deleted, name: Скрытые
        # id: interview, name: Собеседование
        # id: hired, name: Выход на работу
        rv: List[NegotiationItem] = []
        page = 0
        per_page = 100
        while True:
            r: GetNegotiationsListResponse = api_client.negotiations.get(page=page, per_page=per_page, status="active")

            rv.extend(r.items)
            page += 1
            if page >= r.pages:
                break
        return rv

    def _should_delete(self, args: Namespace, item: NegotiationItem) -> bool:
        state: NegotiationState = item.state
        is_discard: bool = state.id == "discard"

        return bool(
            args.all
            or is_discard
            or (
                state.id == "response"
                and (datetime.datetime.now(datetime.timezone.utc) - timedelta(days=args.older_than))
                > datetime.datetime.strptime(item.updated_at, INVALID_ISO8601_FORMAT)
            )
        )

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        """
        Execute negotiations cleanup operation.

        This method removes or declines active negotiations based on the
        provided command-line arguments. It can delete all negotiations,
        delete only discarded ones, or delete responses older than a
        configurable number of days. Optionally, it may also blacklist
        employers when discarding their vacancies.

        Args:
            args (Namespace):
                Parsed command-line arguments:

                --older-than <int>
                    Delete response-type negotiations older than the specified
                    number of days. Default: 30.

                --all
                    Delete all active negotiations, including invitations.
                    If set, overrides other filters.

                --blacklist-discard
                    If enabled, employers of discarded negotiations are added
                    to the blacklist so their vacancies no longer appear as
                    recommended.

            api_client (HHApi)
        """
        logger.info("Clear negotiations is requested")
        negotiations: List[NegotiationItem] = self._get_active_negotiations(api_client)

        for item in tqdm(negotiations, desc="Очистка откликов", unit="шт"):
            logger.debug(f"First item: {item.url}")
            if self._should_delete(args, item):
                logger.info("Deleting negotiation")

                decline_allowed: bool = item.decline_allowed or False
                r_delete: bool = api_client.negotiations.delete(
                    item.id,
                    with_decline_message=decline_allowed,
                )
                assert r_delete

                vacancy: Vacancy | None = item.vacancy
                if vacancy is None:
                    logger.info("Skipping negotiations without vacancy defined")
                    continue

                state: NegotiationState = item.state
                is_discard: bool = state.id == "discard"

                print(
                    "❌ Удален",
                    state.name.lower(),
                    vacancy.alternate_url,
                    "(",
                    truncate_string(vacancy.name),
                    ")",
                )
                if args.blacklist_discard and is_discard:
                    employer: Employer | None = vacancy.employer
                    if not employer or not employer:
                        # Employer is deleted or hidden
                        continue
                    logger.info("Blacklisting employer with url %s", employer.alternate_url)
                    api_client.blacklisted_employers.put(str(employer.id))

                    print(
                        "🚫 Заблокирован",
                        employer.alternate_url,
                        "(",
                        truncate_string(employer.name),
                        ")",
                    )

        print("🧹 Чистка откликов завершена!")
