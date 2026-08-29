"""Ayarlar sayfasi.

Yagmur efekti guzel ama ucretsiz degil: her karede tum pencere yeniden
boyaniyor. Kullanicinin bunu kapatabilmesi gerek - ozellikle pilde.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.platform_utils import platform_name
from src.ui import icons
from src.ui.settings_store import config_path, settings
from src.ui.theme import Colors, Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton
from src.ui.views.update_card import UpdateCard


class SettingRow(QFrame):
    """Baslik + aciklama solda, kontrol sagda. Tekrar eden duzeni tek yerde tutar."""

    def __init__(self, title: str, description: str, control: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        row = QHBoxLayout(self)
        row.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        row.setSpacing(Spacing.LG)

        text = QVBoxLayout()
        text.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("ItemTitle")

        desc_label = QLabel(description)
        desc_label.setObjectName("ItemMeta")
        desc_label.setWordWrap(True)

        text.addWidget(title_label)
        text.addWidget(desc_label)

        row.addLayout(text, stretch=1)
        row.addWidget(control, alignment=Qt.AlignRight | Qt.AlignVCenter)


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Ayarlar")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Gorunum ve davranis tercihleri aninda uygulanir.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(Spacing.SM)

        # Satirlar kucuk pencerede alt bilgiyi ekran disina itiyordu; kaydir.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        rows = QVBoxLayout(content)
        rows.setContentsMargins(0, 0, Spacing.SM, 0)
        rows.setSpacing(Spacing.MD)

        # ------------------------------------------------------ gorunum
        section = QLabel("GORUNUM")
        section.setObjectName("SidebarSection")
        rows.addWidget(section)

        self.rain_toggle = QCheckBox()
        self.rain_toggle.setChecked(bool(settings.get("rain_enabled")))
        self.rain_toggle.toggled.connect(self._on_rain_toggled)
        rows.addWidget(SettingRow(
            "Yagmur efekti",
            "Arka plandaki animasyon. Kapatmak pil omrunu uzatir.",
            self.rain_toggle,
        ))

        self.density_spin = QSpinBox()
        self.density_spin.setRange(20, 300)
        self.density_spin.setSingleStep(10)
        self.density_spin.setValue(int(settings.get("rain_density")))
        self.density_spin.setFixedWidth(90)
        self.density_spin.valueChanged.connect(self._on_density_changed)
        rows.addWidget(SettingRow(
            "Damla yogunlugu",
            "Ayni anda ekranda olan damla sayisi.",
            self.density_spin,
        ))

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(15, 60)
        self.fps_spin.setSingleStep(5)
        self.fps_spin.setValue(int(settings.get("rain_fps")))
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.setFixedWidth(90)
        self.fps_spin.valueChanged.connect(self._on_fps_changed)
        rows.addWidget(SettingRow(
            "Animasyon hizi",
            "45 fps ile 60 fps arasinda gozle gorulur fark yok, guc farki var.",
            self.fps_spin,
        ))

        # ------------------------------------------------------ davranis
        behaviour = QLabel("DAVRANIS")
        behaviour.setObjectName("SidebarSection")
        rows.addWidget(behaviour)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(1000, 10000)
        self.refresh_spin.setSingleStep(500)
        self.refresh_spin.setValue(int(settings.get("dashboard_refresh_ms")))
        self.refresh_spin.setSuffix(" ms")
        self.refresh_spin.setFixedWidth(110)
        self.refresh_spin.valueChanged.connect(
            lambda v: settings.set("dashboard_refresh_ms", int(v))
        )
        rows.addWidget(SettingRow(
            "Dashboard yenileme araligi",
            "Sistem bilgilerinin guncellenme sikligi. Yeni deger sayfa yeniden acilinca gecerli olur.",
            self.refresh_spin,
        ))

        self.confirm_toggle = QCheckBox()
        self.confirm_toggle.setChecked(bool(settings.get("confirm_destructive")))
        self.confirm_toggle.toggled.connect(
            lambda v: settings.set("confirm_destructive", bool(v))
        )
        rows.addWidget(SettingRow(
            "Yikici islemlerde onay iste",
            "Silme ve kaldirma islemleri once onay sorar. Kapatmani onermem.",
            self.confirm_toggle,
        ))

        # ---------------------------------------------------- guncelleme
        update_section = QLabel("GUNCELLEME")
        update_section.setObjectName("SidebarSection")
        rows.addWidget(update_section)

        self.update_card = UpdateCard()
        rows.addWidget(self.update_card)

        self.channel_combo = QComboBox()
        # Veri (userData) ayar dosyasina yazilan deger; etiket sadece gorunum.
        self.channel_combo.addItem("Kararli", "stable")
        self.channel_combo.addItem("Gece surumu", "nightly")
        self.channel_combo.setCurrentIndex(
            max(0, self.channel_combo.findData(settings.get("update_channel")))
        )
        self.channel_combo.setFixedWidth(140)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        rows.addWidget(SettingRow(
            "Guncelleme kanali",
            "Kararli yalnizca etiketlenmis surumleri alir. Gece surumu son "
            "yapiyi alir - daha yeni, daha az denenmis.",
            self.channel_combo,
        ))

        self.startup_check_toggle = QCheckBox()
        self.startup_check_toggle.setChecked(bool(settings.get("update_check_on_start")))
        self.startup_check_toggle.toggled.connect(
            lambda v: settings.set("update_check_on_start", bool(v))
        )
        rows.addWidget(SettingRow(
            "Acilista guncelleme ara",
            "Uygulama acildiktan birkac saniye sonra sessizce denetler.",
            self.startup_check_toggle,
        ))

        rows.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # ------------------------------------------------------ alt bilgi
        info = QLabel(f"Platform: {platform_name()}   ·   Ayar dosyasi: {config_path()}")
        info.setObjectName("Caption")
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)

        bottom = QHBoxLayout()
        bottom.addWidget(info, stretch=1)

        reset = ModernButton("Varsayilanlara Don", "ghost", "refresh")
        reset.clicked.connect(self._reset)
        bottom.addWidget(reset)
        layout.addLayout(bottom)

    # ---------------------------------------------------------- yardimcilar
    def _apply_to_window(self) -> None:
        window = self.window()
        if hasattr(window, "refresh_appearance"):
            window.refresh_appearance()

    @Slot(bool)
    def _on_rain_toggled(self, value: bool):
        settings.set("rain_enabled", bool(value))
        self._apply_to_window()

    @Slot(int)
    def _on_density_changed(self, value: int):
        settings.set("rain_density", int(value))
        self._apply_to_window()

    @Slot(int)
    def _on_fps_changed(self, value: int):
        settings.set("rain_fps", int(value))
        self._apply_to_window()

    @Slot(int)
    def _on_channel_changed(self, _index: int):
        settings.set("update_channel", str(self.channel_combo.currentData()))

    @Slot()
    def _reset(self):
        settings.reset()
        self.rain_toggle.setChecked(bool(settings.get("rain_enabled")))
        self.density_spin.setValue(int(settings.get("rain_density")))
        self.fps_spin.setValue(int(settings.get("rain_fps")))
        self.refresh_spin.setValue(int(settings.get("dashboard_refresh_ms")))
        self.confirm_toggle.setChecked(bool(settings.get("confirm_destructive")))
        self.channel_combo.setCurrentIndex(
            max(0, self.channel_combo.findData(settings.get("update_channel")))
        )
        self.startup_check_toggle.setChecked(bool(settings.get("update_check_on_start")))
        self._apply_to_window()
        notify(self, "Ayarlar varsayilana donduruldu.", "success")


__all__ = ["SettingsPage", "SettingRow", "icons", "Colors"]
