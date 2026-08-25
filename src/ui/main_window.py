"""Uygulama kabugu: baslik cubugu, sidebar, sayfa yigini."""

from __future__ import annotations

import traceback

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.platform_utils import IS_MACOS, platform_name
from src.ui import icons
from src.ui.pages import PageSpec, available_pages
from src.ui.rain import RainEffect
from src.ui.settings_store import settings
from src.ui.style import get_stylesheet
from src.ui.theme import Colors, Motion, Spacing
from src.ui.views.modern_button import IconButton

SITE_URL = "https://www.revo667.com"
SITE_LABEL = "revo667.com"

SIDEBAR_WIDTH = 232
_ROLE_SPEC = Qt.UserRole + 1


class PlaceholderPage(QWidget):
    """Sayfa yuklenemedigi zaman uygulamayi cokertmek yerine bunu gosteririz."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout.setSpacing(Spacing.MD)
        layout.setAlignment(Qt.AlignCenter)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("alert", Colors.TEXT_MUTED, 40))
        glyph.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignCenter)

        message_label = QLabel(message)
        message_label.setObjectName("PageSubtitle")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)

        layout.addWidget(glyph)
        layout.addWidget(title_label)
        layout.addWidget(message_label)


class TitleBar(QWidget):
    """Frameless pencerede surukleme ve pencere kontrolleri.

    macOS'ta sistem trafik isiklari korunur (yerlesik his bozulmasin),
    Windows/Linux'ta kendi butonlarimizi cizeriz.
    """

    def __init__(self, window: QMainWindow, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(42)
        self._window = window
        self._drag_offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, 0, Spacing.SM, 0)
        layout.setSpacing(Spacing.SM)

        self._caption = QLabel(f"667 UTILITY  ·  {platform_name().upper()}")
        self._caption.setObjectName("TitleBarText")

        layout.addWidget(self._caption)
        layout.addStretch()

        if not IS_MACOS:
            minimize = IconButton("minimize", tooltip="Simge durumuna kucult")
            minimize.setObjectName("WindowButton")
            minimize.clicked.connect(window.showMinimized)

            maximize = IconButton("maximize", tooltip="Buyut / geri al")
            maximize.setObjectName("WindowButton")
            maximize.clicked.connect(self._toggle_maximize)

            close = IconButton("close", tooltip="Kapat")
            close.setObjectName("WindowButton")
            close.setProperty("variant", "close")
            close.clicked.connect(window.close)

            layout.addWidget(minimize)
            layout.addWidget(maximize)
            layout.addWidget(close)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    # -- pencereyi baslik cubugundan surukleme
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            if self._window.isMaximized():
                self._window.showNormal()
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


class Sidebar(QWidget):
    """Bolum basliklarina gore gruplanmis, ikonlu gezinme."""

    def __init__(self, specs: list[PageSpec], parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarContainer")
        self.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_brand())

        self.list = QListWidget()
        self.list.setObjectName("Sidebar")
        self.list.setIconSize(QSize(18, 18))
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._populate(specs)

        layout.addWidget(self.list, stretch=1)
        layout.addWidget(self._build_footer())

    def _build_brand(self) -> QWidget:
        brand = QWidget()
        row = QHBoxLayout(brand)
        row.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.MD)
        row.setSpacing(Spacing.MD)

        mark = QLabel()
        mark.setPixmap(icons.pixmap("shield", Colors.ACCENT, 26))
        mark.setFixedWidth(28)

        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel("667 Utility")
        name.setObjectName("BrandName")
        meta = QLabel(platform_name())
        meta.setObjectName("BrandMeta")
        text.addWidget(name)
        text.addWidget(meta)

        row.addWidget(mark)
        row.addLayout(text, stretch=1)
        return brand

    def _populate(self, specs: list[PageSpec]) -> None:
        current_section = None
        for spec in specs:
            if spec.section != current_section:
                current_section = spec.section
                header = QListWidgetItem(spec.section)
                header.setFlags(Qt.NoItemFlags)          # tiklanamaz baslik
                header.setSizeHint(QSize(0, 30))
                font = header.font()
                font.setPointSizeF(max(8.0, font.pointSizeF() - 1.5))
                font.setBold(True)
                header.setFont(font)
                header.setForeground(Qt.GlobalColor.gray)
                self.list.addItem(header)

            item = QListWidgetItem(icons.icon(spec.icon, Colors.TEXT_SECONDARY), spec.label)
            item.setData(_ROLE_SPEC, spec.key)
            item.setSizeHint(QSize(0, 40))
            self.list.addItem(item)

    def _build_footer(self) -> QWidget:
        footer = QLabel()
        footer.setObjectName("SidebarFooter")
        footer.setTextFormat(Qt.RichText)
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignCenter)
        footer.setCursor(Qt.PointingHandCursor)
        footer.setText(
            f'<a href="{SITE_URL}" style="color:{Colors.TEXT_MUTED};'
            f'text-decoration:none;">{SITE_LABEL}</a>'
        )
        return footer

    def select_key(self, key: str) -> bool:
        for index in range(self.list.count()):
            if self.list.item(index).data(_ROLE_SPEC) == key:
                self.list.setCurrentRow(index)
                return True
        return False

    def first_selectable(self) -> int:
        for index in range(self.list.count()):
            if self.list.item(index).data(_ROLE_SPEC):
                return index
        return -1


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"667 Utility — {platform_name()}")
        self.resize(1180, 760)
        self.setMinimumSize(920, 600)

        # Frameless + kendi baslik cubugumuz. macOS'ta sistem butonlari kalsin
        # diye orada frameless kullanmiyoruz.
        if not IS_MACOS:
            self.setWindowFlag(Qt.FramelessWindowHint, True)

        root = QWidget()
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._specs = available_pages()
        self._widgets: dict[str, QWidget] = {}

        self.sidebar = Sidebar(self._specs, self)
        body.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("ContentArea")
        self._index_by_key: dict[str, int] = {}

        if not self._specs:
            self.pages.addWidget(PlaceholderPage(
                "Desteklenmeyen Platform",
                f"{platform_name()} icin tanimli bir sayfa yok.",
            ))
        else:
            for spec in self._specs:
                widget = self._build_page(spec)
                self._widgets[spec.key] = widget
                self._index_by_key[spec.key] = self.pages.addWidget(widget)

        body.addWidget(self.pages, stretch=1)
        outer.addLayout(body, stretch=1)

        self.sidebar.list.currentItemChanged.connect(self._on_nav_changed)

        # Yagmur en arkada; sayfalar ustunde kalsin diye lower().
        self.rain_background = RainEffect(root)
        self.rain_background.setGeometry(root.rect())
        self.rain_background.lower()

        self.setStyleSheet(get_stylesheet())
        self._restore_last_page()

    # ------------------------------------------------------------- sayfalar
    def _build_page(self, spec: PageSpec) -> QWidget:
        try:
            return spec.factory()
        except Exception:
            detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
            return PlaceholderPage(spec.label, f"Bu sayfa yuklenemedi.\n\n{detail}")

    def _restore_last_page(self) -> None:
        last = settings.get("last_page")
        if not (last and self.sidebar.select_key(last)):
            first = self.sidebar.first_selectable()
            if first >= 0:
                self.sidebar.list.setCurrentRow(first)

    def _on_nav_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            return
        key = current.data(_ROLE_SPEC)
        if not key or key not in self._index_by_key:
            return

        self.pages.setCurrentIndex(self._index_by_key[key])
        self._fade_in(self.pages.currentWidget())
        settings.set("last_page", key)

    @staticmethod
    def _fade_in(widget: QWidget | None) -> None:
        """Sayfa gecisinde kisa bir opaklik animasyonu - sicramayi yumusatir."""
        if widget is None:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(Motion.NORMAL)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        # Animasyon bitince efekti kaldir: kalici QGraphicsEffect her boyamada
        # ek maliyet demek (ozellikle dashboard gibi surekli guncellenen sayfada).
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def page(self, key: str) -> QWidget | None:
        return self._widgets.get(key)

    # -------------------------------------------------------------- olaylar
    def refresh_appearance(self) -> None:
        """Ayarlar degistiginde cagrilir."""
        self.rain_background.apply_settings()
        if self.rain_background.isVisible():
            self.rain_background.lower()

    def resizeEvent(self, event):
        central = self.centralWidget()
        if central is not None and hasattr(self, "rain_background"):
            self.rain_background.setGeometry(central.rect())
        super().resizeEvent(event)
