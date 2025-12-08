import argparse
import logging

from ..api import ApiError, HHApi
from ..main import BaseOperation
from ..main import Namespace as BaseNamespace
from ..utils import print_err, truncate_string

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    pass


class Operation(BaseOperation):
    """Update all resumes"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        resumes = api_client.my_resumes.get()
        for resume in resumes.items:
            try:
                api_client.publish_resume.post(resume.id)

                print("✅ Обновлено", truncate_string(resume.title or "No title provided"))
            except ApiError as ex:
                print_err("❗ Ошибка:", ex)
