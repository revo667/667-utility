"""Arka plan yagmur efekti.

Eskiden 16ms'lik timer pencere gorunmese bile calisiyordu: uygulama arka
plandayken bile saniyede 60 kez tum pencereyi yeniden boyuyordu. Artik
gorunurluge bagli duruyor ve fps/yogunluk ayarlardan geliyor.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from src.ui.settings_store import settings

_COLORS = (
    (255, 255, 255),
    (200, 150, 255),
    (150, 190, 255),
    (220, 130, 255),
)


class Drop:
    """dict yerine slotlu sinif: 100+ damla icin gozle gorulur bellek/erisim farki."""

    __slots__ = ("x", "y", "speed", "length", "alpha", "width", "drift", "r", "g", "b")

    def __init__(self, w: float, h: float, spawn_anywhere: bool = False):
        self.reset(w, h, spawn_anywhere)

    def reset(self, w: float, h: float, spawn_anywhere: bool = False) -> None:
        self.r, self.g, self.b = random.choice(_COLORS)
        self.x = random.uniform(0, max(1.0, w))
        self.y = random.uniform(-h, h) if spawn_anywhere else random.uniform(-60, -10)
        self.speed = random.uniform(3.5, 11.0)
        self.length = random.uniform(14, 48)
        self.alpha = random.randint(30, 85)
        self.width = random.uniform(0.8, 2.0)
        self.drift = random.uniform(-0.3, 0.3)


class RainEffect(QWidget):
    def __init__(self, parent=None, drop_count: int | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._drops: list[Drop] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self.apply_settings(drop_count)

    # ------------------------------------------------------------- ayarlar
    def apply_settings(self, drop_count: int | None = None) -> None:
        """Ayarlar sayfasindan cagrilir - yeniden baslatma gerektirmez."""
        self._enabled = bool(settings.get("rain_enabled"))
        self._count = int(drop_count or settings.get("rain_density"))
        fps = max(15, min(60, int(settings.get("rain_fps"))))
        self._interval = max(16, round(1000 / fps))

        self._seed_drops()
        self.setVisible(self._enabled)
        self._sync_timer()

    def _seed_drops(self) -> None:
        w, h = self._canvas_size()
        current = len(self._drops)
        if current < self._count:
            self._drops.extend(
                Drop(w, h, spawn_anywhere=True) for _ in range(self._count - current)
            )
        elif current > self._count:
            del self._drops[self._count:]

    def _canvas_size(self) -> tuple[float, float]:
        parent = self.parent()
        if parent is not None:
            return float(parent.width() or 800), float(parent.height() or 600)
        return float(self.width() or 800), float(self.height() or 600)

    def _sync_timer(self) -> None:
        should_run = self._enabled and self.isVisible() and not self.isHidden()
        if should_run and not self._timer.isActive():
            self._timer.start(self._interval)
        elif not should_run and self._timer.isActive():
            self._timer.stop()

    # --------------------------------------------------------------- dongu
    def _tick(self) -> None:
        w, h = self._canvas_size()
        for drop in self._drops:
            drop.y += drop.speed
            drop.x += drop.drift
            if drop.y > h + drop.length:
                drop.reset(w, h)
        self.update()

    # -------------------------------------------------------------- olaylar
    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        parent = self.parent()
        if parent is not None:
            self.setGeometry(parent.rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        if not self._enabled:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        for drop in self._drops:
            gradient = QLinearGradient(drop.x, drop.y, drop.x, drop.y + drop.length)
            gradient.setColorAt(0.0, QColor(drop.r, drop.g, drop.b, 0))
            gradient.setColorAt(0.5, QColor(drop.r, drop.g, drop.b, drop.alpha // 4))
            gradient.setColorAt(1.0, QColor(drop.r, drop.g, drop.b, drop.alpha))

            painter.setBrush(QBrush(gradient))
            painter.drawRect(QRectF(
                drop.x - drop.width / 2, drop.y, drop.width, drop.length
            ))
