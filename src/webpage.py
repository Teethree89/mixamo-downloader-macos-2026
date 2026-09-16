# Third-party modules
from PySide6 import QtCore, QtWebEngineCore


class CustomWebPage(QtWebEngineCore.QWebEnginePage):
    """Mixamo WebEngine page with useful macOS diagnostics."""

    # Kept for compatibility with older UI code; current token retrieval uses a
    # JavaScript callback and never writes the token to the console.
    retrieved_token = QtCore.Signal(str)

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        # Do not echo authentication material. Everything else is useful when
        # Adobe/Mixamo changes something that Qt WebEngine dislikes.
        lowered = message.lower()
        if "access token" not in lowered and "authorization" not in lowered:
            print(f"[Mixamo JS] {message} ({source_id}:{line_number})")

    def createWindow(self, window_type):
        # Adobe authentication can request a popup/new tab. Keep it inside the
        # same embedded browser so the login flow remains visible and shares the
        # same persistent profile/cookies.
        return self

    def certificateError(self, error):
        print(f"[Mixamo TLS] {error.description()}")
        return False
