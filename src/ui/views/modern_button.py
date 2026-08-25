"""Uygulama genelindeki buton.

Gorunum artik burada degil, style.py'de - bu sinif sadece 'variant'
property'sini set eder ve QSS geri kalanini halleder.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from src.ui import icons
from src.ui.style import repolish
from src.ui.theme import Colors

_ICON_TINT = {
    "primary": "#FFFFFF",
    "ghost": Colors.TEXT_SECONDARY,
    "danger": Colors.DANGER,
    "subtle": Colors.TEXT_MUTED,
}


class ModernButton(QPushButton):
    def __init__(self, text: str = "", variant: str = "primary",
                 icon_name: str | None = None, parent=None):
        super().__init__(text, parent)
        self._variant = variant
        self._icon_name = icon_name
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("variant", variant)
        self._apply_icon()

    # ------------------------------------------------------------- variant
    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, variant: str) -> None:
        if variant == self._variant:
            return
        self._variant = variant
        self.setProperty("variant", variant)
        self._apply_icon()
        repolish(self)

    # ---------------------------------------------------------------- icon
    def set_icon_name(self, name: str | None) -> None:
        self._icon_name = name
        self._apply_icon()

    def _apply_icon(self) -> None:
        if not self._icon_name:
            return
        tint = _ICON_TINT.get(self._variant, Colors.TEXT_SECONDARY)
        self.setIcon(icons.icon(self._icon_name, tint, 16))


class IconButton(ModernButton):
    """Sadece ikon tasiyan kare buton - pencere kontrolleri ve satir eylemleri."""

    def __init__(self, icon_name: str, variant: str = "subtle",
                 tooltip: str = "", size: int = 16, parent=None):
        super().__init__("", variant, icon_name, parent)
        self.setFixedSize(34, 34)
        if tooltip:
            self.setToolTip(tooltip)
        self.setIcon(icons.icon(icon_name, _ICON_TINT.get(variant, Colors.TEXT_MUTED), size))
