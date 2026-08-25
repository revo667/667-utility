from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from core.platform_utils import platform_name
from src.ui import icons
from src.ui.process import (
    get_system_info,
    installed_app_count,
    prime_cpu_sampling,
)
from src.ui.settings_store import settings
from src.ui.style import repolish
from src.ui.theme import Colors, Spacing


def _tone_for(percent: float) -> str:
    """Doluluk yuzdesine gore ilerleme cubugu rengi."""
    if percent >= 90:
        return "danger"
    if percent >= 75:
        return "warning"
    return "success"


class StatCard(QFrame):
    def __init__(self, title: str, icon_name: str = "dashboard",
                 value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.XS)

        head = QHBoxLayout()
        head.setSpacing(Spacing.SM)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, Colors.TEXT_MUTED, 15))
        glyph.setFixedWidth(17)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("CardTitle")

        head.addWidget(glyph)
        head.addWidget(self.title_label, stretch=1)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setRange(0, 100)
        self.bar.hide()

        layout.addLayout(head)
        layout.addWidget(self.value_label)
        layout.addStretch()
        layout.addWidget(self.bar)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_progress(self, percent: float, tone: str | None = None):
        self.bar.show()
        self.bar.setValue(int(max(0, min(100, percent))))
        if tone and self.bar.property("tone") != tone:
            self.bar.setProperty("tone", tone)
            repolish(self.bar)


class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardView")
        prime_cpu_sampling()
        self._build_ui()
        self._refresh()

        self._interval = int(settings.get("dashboard_refresh_ms"))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self._interval)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        header = QLabel("667 Utility")
        header.setObjectName("PageTitle")

        subtitle = QLabel(f"{platform_name()} sistem ozeti")
        subtitle.setObjectName("PageSubtitle")

        layout.addWidget(header)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.MD)
        grid.setVerticalSpacing(Spacing.MD)

        self.cpu_card = StatCard("CPU Kullanimi", "optimizer")
        self.ram_card = StatCard("RAM Kullanimi", "dashboard")
        self.disk_card = StatCard("Bos Disk", "cleaner")
        self.apps_card = StatCard("Kurulu Uygulama", "installer")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.disk_card, 0, 2)
        grid.addWidget(self.apps_card, 0, 3)
        for column in range(4):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)

        section = QLabel("Sistem Detaylari")
        section.setObjectName("SectionTitle")
        layout.addWidget(section)

        self.details = QFormLayout()
        self.details.setVerticalSpacing(10)
        self.details.setLabelAlignment(Qt.AlignLeft)

        self.os_value = QLabel("—")
        self.host_value = QLabel("—")
        self.cpu_value = QLabel("—")
        self.core_value = QLabel("—")
        self.ram_value = QLabel("—")
        self.disk_value = QLabel("—")
        self.uptime_value = QLabel("—")

        self.details.addRow("Isletim Sistemi", self.os_value)
        self.details.addRow("Bilgisayar", self.host_value)
        self.details.addRow("Islemci", self.cpu_value)
        self.details.addRow("Cekirdek", self.core_value)
        self.details.addRow("Bellek", self.ram_value)
        self.details.addRow("Disk", self.disk_value)
        self.details.addRow("Calisma Suresi", self.uptime_value)

        layout.addLayout(self.details)
        layout.addStretch()

        self._app_count_done = False

    def _refresh(self):
        info = get_system_info()

        self.cpu_card.set_value(f"{info['cpu_usage']:.0f}%")
        self.cpu_card.set_progress(info["cpu_usage"], _tone_for(info["cpu_usage"]))

        self.ram_card.set_value(f"{info['ram_percent']:.0f}%")
        self.ram_card.set_progress(info["ram_percent"], _tone_for(info["ram_percent"]))

        self.disk_card.set_value(f"{info['disk_free']:.0f} GB")
        self.disk_card.set_progress(info["disk_percent"], _tone_for(info["disk_percent"]))

        if not self._app_count_done:
            count = installed_app_count()
            self.apps_card.set_value(str(count) if count else "—")
            self._app_count_done = True

        self.os_value.setText(info["os"])
        self.host_value.setText(info["hostname"] or "—")
        self.cpu_value.setText(info["cpu_name"])
        self.core_value.setText(
            f"{info['cpu_cores']} fiziksel / {info['cpu_threads']} mantiksal"
        )
        self.ram_value.setText(
            f"{info['ram_used']:.1f} GB / {info['ram_total']:.1f} GB"
        )
        self.disk_value.setText(
            f"{info['disk_used']:.0f} GB kullanildi / {info['disk_total']:.0f} GB"
        )
        self.uptime_value.setText(info["uptime"])

    def hideEvent(self, event):
        if hasattr(self, "_timer"):
            self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if hasattr(self, "_timer"):
            # Ayar degismis olabilir - sayfa her acildiginda yeniden oku.
            self._interval = int(settings.get("dashboard_refresh_ms"))
            self._timer.start(self._interval)
        super().showEvent(event)
