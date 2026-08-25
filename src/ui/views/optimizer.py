"""Windows optimizasyon sayfasi.

Not: kullanilmayan bir OptimizerView stub'i vardi (sadece 'Optimizer' yazan
bos bir QWidget), kaldirildi.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.optimizations import Optimizations
from src.ui.settings_store import settings
from src.ui.theme import Spacing
from src.ui.views.modern_button import ModernButton
from src.ui.views.optimizer_card import OptimizerCard

#: (baslik, aciklama, risk, uygula, geri al)
OPTIMIZATIONS = (
    (
        "Gecici Dosyalari Temizle",
        "%TEMP%, Windows\\Temp, Prefetch ve Windows Update onbellegini bosaltir.",
        "safe", Optimizations.clear_temp, None,
    ),
    (
        "SysMain (Superfetch) Kapat",
        "SSD'lerde disk kullanimini dusurur. 8 GB+ RAM'li sistemler icin onerilir.",
        "safe", Optimizations.disable_sysmain, Optimizations.enable_sysmain,
    ),
    (
        "Registry Tweak'leri",
        "CPU, GPU ve sistem yanit suresi icin tum .reg dosyalarini uygular.",
        "warning", Optimizations.apply_all_reg, None,
    ),
    (
        "Giris Gecikmesini Dusur",
        "Boot ayarlarini optimize ederek input lag'i azaltir.",
        "safe", Optimizations.lower_input_delay, None,
    ),
    (
        "Yuksek Performans Guc Plani",
        "CPU'yu tam hizda tutar. Dizustunde pil tuketimini artirir.",
        "safe", Optimizations.set_high_performance, Optimizations.set_balanced_power,
    ),
    (
        "Telemetri Servislerini Kapat",
        "Windows veri toplamayi durdurur. Nadiren Windows Update'i etkileyebilir.",
        "safe", Optimizations.disable_telemetry, Optimizations.enable_telemetry,
    ),
    (
        "Xbox Servisleri ve Game Bar",
        "Arka plan kaynaklarini serbest birakir. Overlay ve kayit ozelligi devre disi kalir.",
        "safe", Optimizations.disable_xbox_services, Optimizations.enable_xbox_services,
    ),
    (
        "Arama Indekslemeyi Kapat",
        "CPU/disk kullanimini dusurur. Dosya aramasi yavaslar.",
        "warning", Optimizations.disable_search_index, Optimizations.enable_search_index,
    ),
    (
        "Servis Azaltici",
        "Oyun disi servisleri durdurur. Yazici ve uzak masaustu kullaniyorsan uygulama.",
        "warning", Optimizations.reduce_services, Optimizations.restore_services,
    ),
    (
        "Arka Plan Uygulamalarini Kapat",
        "UWP uygulamalarinin arka planda calismasini engeller.",
        "safe", Optimizations.disable_background_apps, Optimizations.enable_background_apps,
    ),
)


class OptimizerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OptimizerPage")
        self.cards: list[OptimizerCard] = []
        self._build_ui()

    def applied_count(self) -> int:
        return sum(1 for card in self.cards if card.is_applied)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        title = QLabel("System Optimizer")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Performans ve yanit suresi icin sistem ayarlarini degistir.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.counter = QLabel("")
        self.counter.setObjectName("ItemMeta")
        layout.addWidget(self.counter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        cards_layout = QVBoxLayout(content)
        cards_layout.setSpacing(Spacing.SM)
        cards_layout.setContentsMargins(0, 0, Spacing.SM, 0)

        for title_text, desc, status, callback, undo in OPTIMIZATIONS:
            card = OptimizerCard(title_text, desc, status, callback, undo)
            card.state_changed.connect(self._update_counter)
            self.cards.append(card)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        bottom = QHBoxLayout()
        bottom.setSpacing(Spacing.SM)
        bottom.addStretch()

        reset = ModernButton("Varsayilanlara Don", "ghost", "refresh")
        reset.clicked.connect(self._revert_all)

        apply_all = ModernButton("Guvenli Olanlari Uygula", "primary", "optimizer")
        apply_all.clicked.connect(self._apply_all_safe)

        bottom.addWidget(reset)
        bottom.addWidget(apply_all)
        layout.addLayout(bottom)

        self._update_counter()

    # ------------------------------------------------------------- eylemler
    @Slot()
    def _update_counter(self):
        applied = self.applied_count()
        self.counter.setText(
            f"{applied} / {len(self.cards)} tweak uygulandi" if applied
            else f"{len(self.cards)} tweak hazir"
        )

    @Slot()
    def _apply_all_safe(self):
        targets = [
            c for c in self.cards
            if not c.is_applied and c.callback and c.status == "safe"
        ]
        if not targets:
            return

        if settings.get("confirm_destructive"):
            answer = QMessageBox.question(
                self, "Toplu Uygulama",
                f"{len(targets)} guvenli tweak uygulanacak.\n\n"
                "'warning' ve 'danger' isaretli olanlar atlanir - onlari tek tek "
                "uygulaman gerekiyor.\n\nDevam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        for card in targets:
            card.trigger()

    @Slot()
    def _revert_all(self):
        targets = [c for c in self.cards if c.is_applied and c.undo_callback]
        for card in targets:
            card.trigger()
