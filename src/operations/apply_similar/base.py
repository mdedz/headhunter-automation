import argparse
import logging
from abc import abstractmethod
from typing import Any, List, TextIO

from api.hh_api.schemas.similar_vacancies import VacancyItem
from src.api.client import HHApi

from ...main import BaseOperation
from ...main import Namespace as BaseNamespace
from ...utils import (
    parse_interval,
)

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    resume_id: str | None
    message_list: TextIO
    force_message: bool
    use_ai: bool
    verify_relevance: bool
    block_irrelevant: bool
    pre_prompt: str
    apply_interval: tuple[float, float]
    page_interval: tuple[float, float]
    order_by: str
    search: str
    schedule: str
    dry_run: bool
    search_field: List[str]
    experience: str
    employment: list[str] | None
    area: list[str] | None
    metro: list[str] | None
    professional_role: list[str] | None
    industry: list[str] | None
    employer_id: list[str] | None
    excluded_employer_id: list[str] | None
    currency: str | None
    salary: int | None
    only_with_salary: bool
    label: list[str] | None
    period: int | None
    date_from: str | None
    date_to: str | None
    top_lat: float | None
    bottom_lat: float | None
    left_lng: float | None
    right_lng: float | None
    sort_point_lat: float | None
    sort_point_lng: float | None
    no_magic: bool
    premium: bool
    clusters: bool

def _bool(v: bool) -> str:
    return str(v).lower()


def _join_list(items: list[Any] | None) -> str:
    return ",".join(f"{v}" for v in items) if items else ""


class OperationBase(BaseOperation):
    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--resume-id", help="Идентефикатор резюме")
        parser.add_argument(
            "-L",
            "--message-list",
            help="Путь до файла, где хранятся сообщения для отклика на вакансии. Каждое сообщение — с новой строки.",
            type=argparse.FileType("r", encoding="utf-8", errors="replace"),
        )
        parser.add_argument(
            "-f",
            "--force",
            help="Всегда отправлять сообщение при отклике",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--verify-relevance",
            help="Verify relevance of vacancy with LLM",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--block-irrelevant",
            help="Block irrelevant vacancies",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--ai",
            help="Использовать AI для генерации сообщений",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--prompt",
            help="Добавочный промпт для генерации сопроводительного письма",
            default="Сгенерируй сопроводительное письмо не более 5-7 предложений от моего имени для вакансии",
        )
        parser.add_argument(
            "--apply-interval",
            help="Интервал перед отправкой откликов в секундах (X, X-Y)",
            default="1-5",
            type=parse_interval,
        )
        parser.add_argument(
            "--page-interval",
            help="Интервал перед получением следующей страницы рекомендованных вакансий в секундах (X, X-Y)",
            default="1-3",
            type=parse_interval,
        )
        parser.add_argument(
            "--order-by",
            help="Сортировка вакансий",
            choices=[
                "publication_time",
                "salary_desc",
                "salary_asc",
                "relevance",
                "distance",
            ],
            default="relevance",
        )
        parser.add_argument(
            "--search",
            help="Строка поиска для фильтрации вакансий, например, 'москва бухгалтер 100500'",
            type=str,
            default=None,
        )

        parser.add_argument(
            "--schedule",
            help="Тип графика. Возможные значения: fullDay, shift, flexible, remote, flyInFlyOut для полного дня, сменного графика, гибкого графика, удаленной работы и вахтового метода",
            type=str,
            default=None,
        )
        parser.add_argument(
            "--dry-run",
            help="Не отправлять отклики, а только выводить параметры запроса",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--experience",
            help="Уровень опыта работы в вакансии. Возможные значения: noExperience, between1And3, between3And6, moreThan6",
            type=str,
            default=None,
        )
        parser.add_argument(
            "--employment", nargs="+", help="Тип занятости (employment)"
        )
        parser.add_argument("--area", nargs="+", help="Регион (area id)")
        parser.add_argument("--metro", nargs="+", help="Станции метро (metro id)")
        parser.add_argument("--professional-role", nargs="+", help="Проф. роль (id)")
        parser.add_argument("--industry", nargs="+", help="Индустрия (industry id)")
        parser.add_argument("--employer-id", nargs="+", help="ID работодателей")
        parser.add_argument(
            "--excluded-employer-id", nargs="+", help="Исключить работодателей"
        )
        parser.add_argument("--currency", help="Код валюты (RUR, USD, EUR)")
        parser.add_argument("--salary", type=int, help="Минимальная зарплата")
        parser.add_argument(
            "--only-with-salary", default=False, action=argparse.BooleanOptionalAction
        )
        parser.add_argument("--label", nargs="+", help="Метки вакансий (label)")
        parser.add_argument("--period", type=int, help="Искать вакансии за N дней")
        parser.add_argument("--date-from", help="Дата публикации с (YYYY-MM-DD)")
        parser.add_argument("--date-to", help="Дата публикации по (YYYY-MM-DD)")
        parser.add_argument("--top-lat", type=float, help="Гео: верхняя широта")
        parser.add_argument("--bottom-lat", type=float, help="Гео: нижняя широта")
        parser.add_argument("--left-lng", type=float, help="Гео: левая долгота")
        parser.add_argument("--right-lng", type=float, help="Гео: правая долгота")
        parser.add_argument(
            "--sort-point-lat",
            type=float,
            help="Координата lat для сортировки по расстоянию",
        )
        parser.add_argument(
            "--sort-point-lng",
            type=float,
            help="Координата lng для сортировки по расстоянию",
        )
        parser.add_argument(
            "--no-magic",
            default=False,
            action=argparse.BooleanOptionalAction,
            help="Отключить авторазбор текста запроса",
        )
        parser.add_argument(
            "--premium",
            default=False,
            action=argparse.BooleanOptionalAction,
            help="Только премиум вакансии",
        )
        parser.add_argument(
            "--search-field", nargs="+", help="Поля поиска (name, company_name и т.п.)"
        )
        parser.add_argument(
            "--clusters",
            action=argparse.BooleanOptionalAction,
            help="Включить кластеры (по умолчанию None)",
        )

    def _get_search_params(self, args: Namespace, page: int, per_page: int) -> dict:
        params = {
            "page": page,
            "per_page": per_page,
            "order_by": args.order_by,
        }

        if args.search:
            params["text"] = args.search
        if args.schedule:
            params["schedule"] = args.schedule
        if args.experience:
            params["experience"] = args.experience
        if args.currency:
            params["currency"] = args.currency
        if args.salary:
            params["salary"] = args.salary
        if args.period:
            params["period"] = args.period
        if args.date_from:
            params["date_from"] = args.date_from
        if args.date_to:
            params["date_to"] = args.date_to
        if args.top_lat:
            params["top_lat"] = args.top_lat
        if args.bottom_lat:
            params["bottom_lat"] = args.bottom_lat
        if args.left_lng:
            params["left_lng"] = args.left_lng
        if args.right_lng:
            params["right_lng"] = args.right_lng
        if args.sort_point_lat:
            params["sort_point_lat"] = args.sort_point_lat
        if args.sort_point_lng:
            params["sort_point_lng"] = args.sort_point_lng
        if args.search_field:
            params["search_field"] = _join_list(args.search_field)
        if args.employment:
            params["employment"] = _join_list(args.employment)
        if args.area:
            params["area"] = _join_list(args.area)
        if args.metro:
            params["metro"] = _join_list(args.metro)
        if args.professional_role:
            params["professional_role"] = _join_list(args.professional_role)
        if args.industry:
            params["industry"] = _join_list(args.industry)
        if args.employer_id:
            params["employer_id"] = _join_list(args.employer_id)
        if args.excluded_employer_id:
            params["excluded_employer_id"] = _join_list(args.excluded_employer_id)
        if args.label:
            params["label"] = _join_list(args.label)
        if args.only_with_salary is not None:
            params["only_with_salary"] = _bool(args.only_with_salary)
        if args.clusters is not None:
            params["clusters"] = _bool(args.clusters)
        if args.no_magic is not None:
            params["no_magic"] = _bool(args.no_magic)
        if args.premium is not None:
            params["premium"] = _bool(args.premium)

        return params


    @abstractmethod
    def run(
        self, args: Namespace, api_client: HHApi
    ) -> None:
        pass

    @staticmethod
    @abstractmethod
    def _get_application_messages(message_list: TextIO | None = None) -> list[str]:
        pass

    @abstractmethod
    def _apply_similar(self) -> None:
        pass

    @abstractmethod
    def _get_vacancies(self, per_page: int = 100) -> list[VacancyItem]:
        pass
