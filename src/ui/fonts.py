
from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from core.resources import ASSETS_DIR

_ASSETS = ASSETS_DIR

_loaded: list[str] = []


def load_bundled_fonts() -> list[str]:

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
