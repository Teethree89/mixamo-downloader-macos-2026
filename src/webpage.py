# Third-party modules
from PySide6 import QtCore, QtWebEngineCore


class CustomWebPage(QtWebEngineCore.QWebEnginePage):
    """Custom QWebEnginePage that captures the Mixamo access token."""

    retrieved_token = QtCore.Signal(str)

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if "ACCESS TOKEN" in message:
            access_token = message.split(":")[-1].strip()
            self.retrieved_token.emit(access_token)
        super().javaScriptConsoleMessage(level, message, line_number, source_id)
