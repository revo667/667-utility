"""Vektor ikon seti.

Neden SVG string: ikon dosyasi tasimak istemiyoruz, PNG olceklenince bulaniyor,
Nerd Font glyph'leri ise fontun kurulu olmasina bagli. Inline SVG her platformda
ayni gorunur ve rengi calisma aninda degistirilebilir.

Ikonlar 24x24 grid, 1.75px stroke - Lucide ile ayni gorsel dil.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from src.ui.theme import Colors

_STROKE = (
    'fill="none" stroke="{c}" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round"'
)

#: Her ikon sadece path/shape govdesi - sarmalayici _wrap() tarafindan eklenir.
_PATHS: dict[str, str] = {
    "dashboard": (
        '<rect x="3" y="3" width="7.5" height="7.5" rx="2"/>'
        '<rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/>'
        '<rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/>'
        '<rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/>'
    ),
    "optimizer": (
        '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>'
    ),
    "installer": (
        '<path d="M12 3v12"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/>'
        '<path d="M4 17.5v1.5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5"/>'
    ),
    "uninstaller": (
        '<path d="M4 6.5h16"/><path d="M9.5 6.5V4.75A1.75 1.75 0 0 1 11.25 3h1.5A1.75 1.75 0 0 1 14.5 4.75V6.5"/>'
        '<path d="M6.5 6.5 7.4 19a2 2 0 0 0 2 1.9h5.2a2 2 0 0 0 2-1.9l.9-12.5"/>'
        '<path d="M10.5 10.5v6"/><path d="M13.5 10.5v6"/>'
    ),
    "cleaner": (
        '<path d="M13.5 2.5 21 10l-8.5 8.5"/>'
        '<path d="M13.5 2.5 6 10l8.5 8.5"/>'
        '<path d="M3 21h18"/>'
    ),
    "snapshots": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'
        '<path d="M3.5 12a8.5 8.5 0 0 1 .6-3.1"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.6 1.6 0 0 0 .32 1.77l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.77-.32 '
        '1.6 1.6 0 0 0-1 1.47V21a2 2 0 1 1-4 0v-.11a1.6 1.6 0 0 0-1.05-1.47 1.6 1.6 0 0 0-1.77.32l-.06.06a2 2 0 '
        '1 1-2.83-2.83l.06-.06a1.6 1.6 0 0 0 .32-1.77 1.6 1.6 0 0 0-1.47-1H3a2 2 0 1 1 0-4h.11a1.6 1.6 0 0 0 '
        '1.47-1.05 1.6 1.6 0 0 0-.32-1.77l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.6 1.6 0 0 0 1.77.32H9a1.6 1.6 0 '
        '0 0 1-1.47V3a2 2 0 1 1 4 0v.11a1.6 1.6 0 0 0 1 1.47 1.6 1.6 0 0 0 1.77-.32l.06-.06a2 2 0 1 1 2.83 '
        '2.83l-.06.06a1.6 1.6 0 0 0-.32 1.77V9a1.6 1.6 0 0 0 1.47 1H21a2 2 0 1 1 0 4h-.11a1.6 1.6 0 0 0-1.47 1z"/>'
    ),
    "shield": (
        '<path d="M12 21s7-3.2 7-9V5.6L12 3 5 5.6V12c0 5.8 7 9 7 9z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "search": (
        '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.9-4.9"/>'
    ),
    "refresh": (
        '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1"/><path d="M20.5 4v5h-5"/>'
    ),
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "alert": (
        '<path d="M12 8v5"/><circle cx="12" cy="16.5" r="0.9" fill="{c}" stroke="none"/>'
        '<circle cx="12" cy="12" r="9"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/>'
        '<circle cx="12" cy="7.8" r="0.9" fill="{c}" stroke="none"/>'
    ),
    "close": '<path d="m6 6 12 12"/><path d="m18 6-12 12"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="4.5" y="4.5" width="15" height="15" rx="2.5"/>',
}


def _wrap(name: str, color: str) -> bytes:
    body = _PATHS[name].replace("{c}", color)
    stroke = _STROKE.format(c=color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" {stroke}>'
        f"{body}</svg>"
    )
    return svg.encode("utf-8")


@lru_cache(maxsize=256)
def pixmap(name: str, color: str = Colors.TEXT_SECONDARY, size: int = 18,
           ratio: float = 2.0) -> QPixmap:
    """Ikonu istenen renk ve boyutta verir. Retina icin ratio ile buyutulur."""
    if name not in _PATHS:
        return QPixmap()

    px = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    px.fill(Qt.transparent)

    renderer = QSvgRenderer(QByteArray(_wrap(name, color)))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    px.setDevicePixelRatio(ratio)
    return px


@lru_cache(maxsize=256)
def icon(name: str, color: str = Colors.TEXT_SECONDARY, size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))


def available() -> tuple[str, ...]:
    return tuple(_PATHS)
