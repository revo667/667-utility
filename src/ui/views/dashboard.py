from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout, QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from core.platform_utils import IS_MACOS, platform_name
from src.ui.process import (
    get_system_info, installed_app_count, prime_cpu_sampling,
)

REFRESH_MS = 2000


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setRange(0, 100)
        self.bar.hide()

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.bar)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_progress(self, percent: float):
        self.bar.show()
        self.bar.setValue(int(max(0, min(100, percent))))


class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardView")
        prime_cpu_sampling()
        self._build_ui()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_MS)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("667 Utility")
        header.setObjectName("PageTitle")

        subtitle = QLabel(f"{platform_name()} sistem ozeti")
        subtitle.setObjectName("PageSubtitle")

        layout.addWidget(header)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self.cpu_card = StatCard("CPU Kullanimi")
        self.ram_card = StatCard("RAM Kullanimi")
        self.disk_card = StatCard("Bos Disk")
        self.apps_card = StatCard("Kurulu Uygulama")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.disk_card, 0, 2)
        grid.addWidget(self.apps_card, 0, 3)
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
        self.cpu_card.set_progress(info["cpu_usage"])

        self.ram_card.set_value(f"{info['ram_percent']:.0f}%")
        self.ram_card.set_progress(info["ram_percent"])

        self.disk_card.set_value(f"{info['disk_free']:.0f} GB")
        self.disk_card.set_progress(info["disk_percent"])

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
            self._timer.start(REFRESH_MS)
        super().showEvent(event)
