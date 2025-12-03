import argparse
import logging

from prettytable import PrettyTable

from ..api import HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import truncate_string

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    pass


class Operation(BaseOperation):
    """List of resumes"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        resumes = api_client.my_resumes.get()
        t = PrettyTable(field_names=["ID", "Название", "Статус"], align="l", valign="t")
        t.add_rows(
            [
                [
                    str(x.id),
                    truncate_string(x.title or "Title not found"),
                    x.status.name,
                ]
                for x in resumes.items
            ]
        )
        print(t)
