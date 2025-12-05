import argparse
import logging
import sys
from typing import Any
from urllib.parse import parse_qs, urlsplit

from ..utils import print_err

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineCore import QWebEngineUrlSchemeHandler
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication, QMainWindow

    QT_IMPORTED = True
except ImportError:
    QT_IMPORTED = False
    class QUrl:
        pass

    class QApplication:
        pass

    class QMainWindow:
        pass

    class QWebEngineUrlSchemeHandler:
        pass

    class QWebEngineView:
        pass


from ..api import HHApi
from ..main import BaseOperation, Namespace

logger = logging.getLogger(__package__)


class HHAndroidUrlSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, parent: "WebViewWindow") -> None:
        super().__init__()
        self.parent = parent

    def requestStarted(self, info: Any) -> None:
        url = info.requestUrl().toString()
        if url.startswith("hhandroid://"):
            self.parent.handle_redirect_uri(url)


class WebViewWindow(QMainWindow):
    def __init__(self, api_client: HHApi) -> None:
        super().__init__()
        self.api_client = api_client

        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)
        self.setWindowTitle("Авторизация на HH.RU")
        self.hhandroid_handler = HHAndroidUrlSchemeHandler(self)

        profile = self.web_view.page().profile()
        profile.installUrlSchemeHandler(b"hhandroid", self.hhandroid_handler)

        self.resize(480, 800)
        self.web_view.setUrl(QUrl(api_client.oauth_client.authorize_url))

    def handle_redirect_uri(self, redirect_uri: str) -> None:
        logger.debug(f"handle redirect uri: {redirect_uri}")
        sp = urlsplit(redirect_uri)
        code = parse_qs(sp.query).get("code", [None])[0]
        if code:
            token = self.api_client.oauth_client.authenticate(code)
            self.api_client.handle_access_token(token)
            print("🔓 Авторизация прошла успешно!")
            self.close()

class Operation(BaseOperation):
    """Authorize on website"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: Namespace, api_client: HHApi, *_) -> None:
        if not QT_IMPORTED:
            print_err(
                "No pyqt"
            )
            sys.exit(1)

        app = QApplication(sys.argv)
        window = WebViewWindow(api_client=api_client)
        window.show()

        app.exec()
