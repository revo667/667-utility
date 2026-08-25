"""Kayan bildirim.

QMessageBox her seferinde akisi kesiyordu. Bilgi amacli mesajlar icin
kendini kapatan, tiklanabilir bir toast daha az rahatsiz edici.
Onay gerektiren islemler icin QMessageBox kalmali - toast onay soramaz.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from src.ui import icons
from src.ui.theme import Colors, Motion, Spacing

_TONE_ICON = {
    "success": "check",
    "warning": "alert",
    "danger": "alert",
    "info": "info",
}

_TONE_COLOR = {
    "success": Colors.SUCCESS,
    "warning": Colors.WARNING,
    "danger": Colors.DANGER,
    "info": Colors.INFO,
}


class Toast(QWidget):
    """Tek bir bildirim baloncugu. Dogrudan olusturma - Toast.show_message() kullan."""

    def __init__(self, parent: QWidget, message: str, tone: str = "info",
                 duration: int = Motion.TOAST_LIFE):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("tone", tone)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.LG, Spacing.SM)
        layout.setSpacing(Spacing.MD)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(
            _TONE_ICON.get(tone, "info"), _TONE_COLOR.get(tone, Colors.INFO), 18
        ))
        glyph.setFixedWidth(20)

        self._label = QLabel(message)
        self._label.setObjectName("ToastText")
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(360)

        layout.addWidget(glyph)
        layout.addWidget(self._label, stretch=1)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._slide = QPropertyAnimation(self, b"pos", self)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._duration = duration

    # ----------------------------------------------------------- yasam dongusu
    def present(self, target: QPoint) -> None:
        self.adjustSize()
        start = QPoint(target.x(), target.y() + 14)
        self.move(start)
        self.show()
        self.raise_()

        self._fade.stop()
        self._fade.setDuration(Motion.NORMAL)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.start()

        self._slide.stop()
        self._slide.setDuration(Motion.NORMAL)
        self._slide.setStartValue(start)
        self._slide.setEndValue(target)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.start()

        self._timer.start(self._duration)

    def dismiss(self) -> None:
        self._timer.stop()
        self._fade.stop()
        self._fade.setDuration(Motion.FAST)
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._finish)
        self._fade.start()

    def _finish(self) -> None:
        manager = _managers.get(self.parent())
        if manager:
            manager.remove(self)
        self.deleteLater()

    def mousePressEvent(self, event):
        self.dismiss()
        super().mousePressEvent(event)

    # ------------------------------------------------------------ kolay giris
    @staticmethod
    def show_message(parent: QWidget, message: str, tone: str = "info",
                     duration: int = Motion.TOAST_LIFE) -> None:
        """Herhangi bir widget'tan cagrilabilir - en ustteki pencereye yerlesir."""
        host = parent.window() if parent else None
        if host is None:
            return
        manager = _managers.setdefault(host, _ToastStack(host))
        manager.push(message, tone, duration)


class _ToastStack:
    """Ayni anda birden fazla toast varsa ust uste binmesinler diye."""

    MAX_VISIBLE = 4

    def __init__(self, host: QWidget):
        self._host = host
        self._items: list[Toast] = []

    def push(self, message: str, tone: str, duration: int) -> None:
        while len(self._items) >= self.MAX_VISIBLE:
            self._items[0].dismiss()
            break

        toast = Toast(self._host, message, tone, duration)
        self._items.append(toast)
        toast.present(self._position_for(len(self._items) - 1, toast))
        self._reflow()

    def remove(self, toast: Toast) -> None:
        if toast in self._items:
            self._items.remove(toast)
        self._reflow()

    def _position_for(self, index: int, toast: Toast) -> QPoint:
        toast.adjustSize()
        margin = Spacing.LG
        x = self._host.width() - toast.width() - margin
        y = self._host.height() - margin - (toast.height() + Spacing.SM) * (index + 1)
        return QPoint(max(margin, x), max(margin, y))

    def _reflow(self) -> None:
        for index, toast in enumerate(self._items):
            target = self._position_for(index, toast)
            anim = QPropertyAnimation(toast, b"pos", toast)
            anim.setDuration(Motion.FAST)
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)


#: Pencere basina tek yigin.
_managers: dict[QWidget, _ToastStack] = {}


def notify(parent: QWidget, message: str, tone: str = "info") -> None:
    """Kisayol: notify(self, "Temizlik bitti", "success")"""
    Toast.show_message(parent, message, tone)
