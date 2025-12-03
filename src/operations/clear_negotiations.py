# Этот модуль можно использовать как образец для других
import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from api.hh_api.schemas.negotiations import DeleteNegotiationsResponse, GetNegotiationsListResponse, NegotiationItem

from ..api import HHApi, ClientError
from ..constants import INVALID_ISO8601_FORMAT
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import print_err, truncate_string

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
        rv: List[NegotiationItem] = []
        page = 0
        per_page = 100
        while True:
            r: GetNegotiationsListResponse = api_client.negotiations.get(
                page=page,
                per_page=per_page,
                status="active"
            )
            rv.extend(r.items)
            page += 1
            if page >= r.pages:
                break
        return rv

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        negotiations = self._get_active_negotiations(api_client)
        print("Всего активных:", len(negotiations))
        
        for item in negotiations:
            state = item.state
            is_discard = state.id == "discard"
            
            if not item.hidden and (
                args.all
                or is_discard
                or (
                    state.id == "response"
                    and (datetime.utcnow() - timedelta(days=args.older_than)).replace(tzinfo=timezone.utc)
                    > datetime.strptime(item.updated_at, INVALID_ISO8601_FORMAT)
                )
            ):
                decline_allowed = item.decline_allowed or False
                r_delete: DeleteNegotiationsResponse = api_client.negotiations.delete(
                    item.id,
                    with_decline_message=decline_allowed,
                )
                assert {} == r_delete
                
                vacancy = item.vacancy
                if vacancy is None:
                    logger.debug("Skipping negotiations without vacancy defined")
                    continue
                
                print(
                    "❌ Удалили",
                    state.name.lower(),
                    vacancy.alternate_url,
                    "(",
                    truncate_string(vacancy.name),
                    ")",
                )
                if is_discard and args.blacklist_discard:
                    employer = vacancy.employer
                    if not employer or not employer:
                        # Работодатель удален или скрыт
                        continue
                    try:
                        r_put = api_client.blacklisted_employers.put(str(employer.id))
                        assert not r_put
                        print(
                            "🚫 Заблокировали",
                            employer.alternate_url,
                            "(",
                            truncate_string(employer.name),
                            ")",
                        )
                    except ClientError as ex:
                        print_err("❗ Ошибка:", ex)
                        
        print("🧹 Чистка заявок завершена!")
