
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.ui.fonts import load_bundled_fonts
from src.ui.main_window import MainWindow
from src.ui.theme import Type

APP_NAME = "667 Utility"
ORG_NAME = "revo667"


def _pick_ui_font() -> QFont | None:
    from PySide6.QtGui import QFontDatabase

    families = QFontDatabase.families()
    for candidate in ("Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI"):
        if candidate in families:
            font = QFont(candidate)
            font.setPointSize(10)
            return font
    return None


def run_app() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)

    # Paketle gelen fontu yukle - sisteme kurulum gerektirmez.
    load_bundled_fonts()

    font = _pick_ui_font()
    if font is not None:
        app.setFont(font)

    # Kimlik kapisi: Universe, trading journal ve bu uygulama tek hesabi paylasir.
    from src.ui.views.login_gate import require_account

    if require_account() is None:
        return

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["run_app", "Type"]
