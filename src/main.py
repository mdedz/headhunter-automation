from __future__ import annotations

import argparse
import logging
import sys
from importlib import import_module
from os import getenv
from pathlib import Path
from pkgutil import iter_modules
from typing import Literal, Sequence

from src.api import HHApi
from src.argparse import CustomHelpFormatter
from src.color_log import ColorHandler
from src.config import Config
from src.utils import Data

logger = logging.getLogger()


class BaseOperation:
    def setup_parser(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace, *_args, **_kwargs) -> None | int:
        raise NotImplementedError()


OPERATIONS = "operations"


class Namespace(argparse.Namespace):
    data: Data
    config_path: str
    verbosity: int
    delay: float
    user_agent: str
    proxy_url: str


def get_proxies(args: Namespace) -> dict[Literal["http", "https"], str | None]:
    config = Config.load(args.config_path)
    return {
        "http": config.proxy.proxy_url or getenv("HTTP_PROXY"),
        "https": config.proxy.proxy_url or getenv("HTTPS_PROXY"),
    }


def get_api_client(args: Namespace) -> HHApi:
    data = Data(args.data_path)
    token = data.get("token", {})
    api = HHApi(
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        access_expires_at=token.get("access_expires_at"),
        delay=args.delay,
        user_agent=data["user_agent"],
        proxies=get_proxies(args),
    )
    return api


class HHApplicantTool:
    class ArgumentFormatter(
        argparse.ArgumentDefaultsHelpFormatter,
        argparse.RawDescriptionHelpFormatter,
    ):
        pass

    def create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="headhunter-automation",
            description=(
                "HH Applicant Automation Tool. Автоматизация откликов, обновления резюме и работы с API HeadHunter.\n"
            ),
            formatter_class=CustomHelpFormatter,
            add_help=False,
        )
        group = parser.add_argument_group("Global options")
        group.add_argument("-h", "--help", action="help", help="Show this help message and exit")
        group.add_argument("--config-path", type=str, help="Config file path", default="config/config.toml")
        group.add_argument("--data-path", type=str, help="Data file path")
        group.add_argument(
            "-v",
            "--verbosity",
            help="Уровень отладочной информации в выводе [Нет: WARNING, -v: INFO, -vv: DEBUG]",
            action="count",
            default=0,
        )
        group.add_argument("-d", "--delay", type=float, default=0.334, help="Задержка между запросами к API HH")
        group.add_argument("--user-agent", type=str, help="User-Agent для каждого запроса")
        group.add_argument("--proxy-url", type=str, help="Прокси, используемый для запросов к API")

        subparsers = parser.add_subparsers(help="commands", dest="command", metavar="")

        package_dir = Path(__file__).resolve().parent / OPERATIONS
        for _, module_name, _ in iter_modules([str(package_dir)]):
            mod = import_module(f"{__package__}.{OPERATIONS}.{module_name}")
            op: BaseOperation = mod.Operation()

            op_parser = subparsers.add_parser(
                module_name.replace("_", "-"),
                help=(op.__doc__.strip() if op.__doc__ else ""),
                formatter_class=CustomHelpFormatter,
            )
            op_parser.set_defaults(run=op.run)
            op.setup_parser(op_parser)

        return parser

    def run(self, argv: Sequence[str] | None) -> None | int:
        parser = self.create_parser()
        args = parser.parse_args(argv, namespace=Namespace())

        log_level = max(logging.DEBUG, logging.WARNING - args.verbosity * 10)
        logger.setLevel(log_level)
        handler = ColorHandler()

        handler.setFormatter(logging.Formatter("[%(levelname).1s] %(message)s"))
        logger.addHandler(handler)
        if args.run:
            try:
                api_client = get_api_client(args)

                # 0 or None = success
                res = args.run(args, api_client)
                data = Data(args.data_path)
                if (token := api_client.get_access_token()) != data["token"]:
                    data.save(token=token)
                return res
            except KeyboardInterrupt:
                logger.warning("Interrupted by user")
                return 1
            except Exception as e:
                logger.exception(e)
                return 1
        parser.print_help(file=sys.stderr)
        return 2


def main(argv: Sequence[str] | None = None) -> None | int:
    return HHApplicantTool().run(argv)
