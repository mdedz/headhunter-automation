import argparse
import logging
from typing import Any

from ..api import ApiError, HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import print_err

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    pass


class Operation(BaseOperation):
    """Gets new access_token."""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, _, api_client: HHApi, *args: Any) -> None:
        try:
            api_client.refresh_access_token()
            print("✅ Токен обновлен!")
        except ApiError as ex:
            print_err("❗ Ошибка:", ex)
            return
