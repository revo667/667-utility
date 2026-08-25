"""Paketle gelen fontu calisma aninda yukler.

Eskiden font Windows kayit defterine kopyalaniyordu - yonetici hakki
gerektiriyor, macOS/Linux'ta hic calismiyordu ve sisteme kalici olarak
dokunuyordu. QFontDatabase.addApplicationFont() ayni isi uc platformda,
izin istemeden ve sadece bu surec icin yapar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_ASSETS = Path(__file__).resolve().parents[2] / "assets"

_loaded: list[str] = []


def load_bundled_fonts() -> list[str]:
    """assets/ altindaki tum .ttf/.otf dosyalarini yukler, aile adlarini doner."""
    global _loaded
    if _loaded:
        return _loaded

    families: list[str] = []
    if not _ASSETS.is_dir():
        return families

    for path in sorted(_ASSETS.glob("*.tt[fc]")) + sorted(_ASSETS.glob("*.otf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id != -1:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))

    _loaded = families
    return families


def has_family(name: str) -> bool:
    return name in QFontDatabase.families()
