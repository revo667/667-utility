import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from core.platform_utils import platform_name
from src.ui.pages import available_pages
from src.ui.rain import RainEffect
from src.ui.style import get_stylesheet
from src.ui.theme import Colors

SITE_URL = "https://www.revo667.com"
SITE_LABEL = "www.revo667.com"


class PlaceholderPage(QWidget):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        title_label.setAlignment(Qt.AlignCenter)

        message_label = QLabel(message)
        message_label.setObjectName("PageSubtitle")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(message_label)


class SidebarFooter(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarFooter")
        self.setTextFormat(Qt.RichText)
        self.setOpenExternalLinks(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(
            f'<a href="{SITE_URL}" '
            f'style="color: {Colors.TEXT_SECONDARY}; text-decoration: none;">'
            f'{SITE_LABEL}</a>'
        )
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.35)
        self.setGraphicsEffect(self._effect)

    def enterEvent(self, event):
        self._effect.setOpacity(0.85)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._effect.setOpacity(0.35)
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"667 Utility — {platform_name()}")
        self.resize(1100, 700)

        root = QWidget()
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)

        sidebar_container = QWidget()
        sidebar_container.setObjectName("SidebarContainer")
        sidebar_container.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")

        self.footer = SidebarFooter()

        sidebar_layout.addWidget(self.sidebar, stretch=1)
        sidebar_layout.addWidget(self.footer)

        self.pages = QStackedWidget()
        self._specs = available_pages()
        self._widgets = {}

        if not self._specs:
            self.pages.addWidget(PlaceholderPage(
                "Desteklenmeyen Platform",
                f"{platform_name()} icin tanimli bir sayfa yok.",
            ))
        else:
            for spec in self._specs:
                self.sidebar.addItem(spec.label)
                widget = self._build_page(spec)
                self._widgets[spec.key] = widget
                self.pages.addWidget(widget)

        layout.addWidget(sidebar_container)
        layout.addWidget(self.pages)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        if self._specs:
            self.sidebar.setCurrentRow(0)

        self.rain_background = RainEffect(root, drop_count=120)
        self.rain_background.setGeometry(root.rect())
        self.rain_background.lower()

        self.setStyleSheet(get_stylesheet())

    def _build_page(self, spec) -> QWidget:
        try:
            return spec.factory()
        except Exception:
            detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
            return PlaceholderPage(
                spec.label,
                f"Bu sayfa yuklenemedi.\n\n{detail}",
            )

    def page(self, key: str):
        return self._widgets.get(key)

    def resizeEvent(self, event):
        if hasattr(self, "rain_background"):
            self.rain_background.setGeometry(self.centralWidget().rect())
        super().resizeEvent(event)
