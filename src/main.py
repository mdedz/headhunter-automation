from __future__ import annotations

import argparse
import logging
import sys
from importlib import import_module
from os import getenv
from pathlib import Path
from pkgutil import iter_modules
from typing import Literal, Sequence

from src.config import Config

from .api import HHApi
from .color_log import ColorHandler
from .utils import Data, get_config_path

logger = logging.getLogger(__package__)


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
    token = args.data.get("token", {})
    api = HHApi(
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        access_expires_at=token.get("access_expires_at"),
        delay=args.delay,
        user_agent=args.data["user_agent"],
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
            description=self.__doc__,
            formatter_class=self.ArgumentFormatter,
        )
        parser.add_argument(
            "-c",
            "--config-path",
            help="Config file path",
            default="config/config.toml",
        )
        parser.add_argument(
            "-data",
            "--data",
            help="Data file path",
            type=Data,
            default=Data(),
        )
        parser.add_argument(
            "-v",
            "--verbosity",
            help="При использовании от одного и более раз увеличивает количество отладочной информации в выводе",
            action="count",
            default=0,
        )
        parser.add_argument(
            "-d",
            "--delay",
            type=float,
            default=0.334,
            help="Задержка между запросами к API HH",
        )
        parser.add_argument(
            "--user-agent", 
            help="User-Agent для каждого запроса"
        )
        parser.add_argument(
            "--proxy-url", help="Прокси, используемый для запросов к API"
        )
        subparsers = parser.add_subparsers(help="commands")
        package_dir = Path(__file__).resolve().parent / OPERATIONS
        for _, module_name, _ in iter_modules([str(package_dir)]):
            mod = import_module(f"{__package__}.{OPERATIONS}.{module_name}")
            op: BaseOperation = mod.Operation()
            op_parser = subparsers.add_parser(
                module_name.replace("_", "-"),
                description=op.__doc__,
                formatter_class=self.ArgumentFormatter,
            )
            op_parser.set_defaults(run=op.run)
            op.setup_parser(op_parser)
        parser.set_defaults(run=None)
        return parser

    def run(self, argv: Sequence[str] | None) -> None | int:
        parser = self.create_parser()
        args = parser.parse_args(argv, namespace=Namespace())
        #TODO: Test
        # log_level = max(logging.DEBUG, logging.WARNING - args.verbosity * 10)
        logger.setLevel(logging.ERROR)
        handler = ColorHandler()
        
        handler.setFormatter(logging.Formatter("[%(levelname).1s] %(message)s"))
        logger.addHandler(handler)
        if args.run:
            try:
                api_client = get_api_client(args)

                # 0 or None = success
                res = args.run(args, api_client)
                if (token := api_client.get_access_token()) != args.data["token"]:
                    args.data.save(token=token)
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
