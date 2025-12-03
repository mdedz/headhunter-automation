import argparse
import json
import logging

from ..api import HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    pass


class Operation(BaseOperation):
    """Sends current user"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: Namespace, api_client: HHApi, _) -> None:
        result = api_client.me.get()
        print(
            f"{result.last_name} {result.first_name} {result.middle_name}" 
        )
