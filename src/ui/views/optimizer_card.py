"""Tek bir tweak'i temsil eden kart."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.ui.style import repolish
from src.ui.theme import Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton


class OptimizerWork(QThread):
    """Tweak'i arka planda calistirir.

    Sinyal adi bilerek 'done': QThread'in kendi 'finished' sinyali var, ayni
    isimle yeni bir Signal tanimlamak onu golgeliyor ve is bitis takibini bozuyordu.
    """

    done = Signal(bool, str)

    def __init__(self, callback: Callable, parent=None):
        super().__init__(parent)
        self._callback = callback

    def run(self):
        try:
            result = self._callback()
            # Geri alma fonksiyonlarinin bir kismi None donuyor - None'i basari say.
            self.done.emit(True if result is None else bool(result), "")
        except Exception as exc:
            self.done.emit(False, str(exc))


class OptimizerCard(QFrame):
    #: Kart durumu degistiginde sayfa toplam sayaci guncelleyebilsin diye.
    state_changed = Signal(bool)

    def __init__(self, title: str, description: str, status: str = "safe",
                 callback: Callable | None = None,
                 undo_callback: Callable | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("OptimizerCard")

        self.title = title
        self.callback = callback
        self.undo_callback = undo_callback
        self.status = status
        self.is_applied = False
        self._worker: OptimizerWork | None = None

        self._build_ui(title, description, status)

    def _build_ui(self, title: str, description: str, status: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.MD)

        stripe = QFrame()
        stripe.setObjectName("RiskStripe")
        stripe.setProperty("risk", status)
        stripe.setFixedWidth(3)
        stripe.setMinimumHeight(38)

        text = QVBoxLayout()
        text.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("ItemTitle")

        desc_label = QLabel(description)
        desc_label.setObjectName("ItemMeta")
        desc_label.setWordWrap(True)

        text.addWidget(title_label)
        text.addWidget(desc_label)

        self.action_btn = ModernButton(
            "Uygula", "primary" if status == "safe" else "danger"
        )
        self.action_btn.setFixedWidth(120)
        self.action_btn.clicked.connect(self.trigger)

        layout.addWidget(stripe)
        layout.addLayout(text, stretch=1)
        layout.addWidget(self.action_btn)

    # ------------------------------------------------------------- eylemler
    def trigger(self) -> None:
        """Kartin ana eylemi: uygulanmadiysa uygula, uygulandiysa geri al."""
        callback = self.undo_callback if self.is_applied else self.callback
        if callback is None or (self._worker and self._worker.isRunning()):
            return

        self.action_btn.setEnabled(False)
        self.action_btn.setText("Calisiyor...")

        self._worker = OptimizerWork(callback, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, error: str) -> None:
        self.action_btn.setEnabled(True)

        if success:
            self.is_applied = not self.is_applied
            self.state_changed.emit(self.is_applied)
            notify(
                self,
                f"{self.title} {'uygulandi' if self.is_applied else 'geri alindi'}.",
                "success",
            )
        elif error:
            notify(self, f"{self.title}: {error}", "danger")
        else:
            notify(self, f"{self.title} uygulanamadi.", "warning")

        self._sync_button()

    def _sync_button(self) -> None:
        if self.is_applied:
            self.action_btn.setText("Geri Al")
            self.action_btn.set_variant("ghost")
            self.action_btn.setEnabled(self.undo_callback is not None)
            if self.undo_callback is None:
                self.action_btn.setText("Uygulandi")
        else:
            self.action_btn.setText("Uygula")
            self.action_btn.set_variant("primary" if self.status == "safe" else "danger")
        repolish(self)
