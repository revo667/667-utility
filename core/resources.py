from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller ile paketlenmis halde mi calisiyoruz?"""
    return getattr(sys, "frozen", False)


def base_path() -> Path:
    if is_frozen():
        # onefile modunda _MEIPASS gecici acilim klasoru,
        # onedir modunda yurutulebilirin bulundugu klasor.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent

    # core/resources.py -> proje koku
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return base_path().joinpath(*parts)


#: Sik kullanilanlar
ASSETS_DIR = resource_path("assets")
REGS_DIR = resource_path("assets", "regs")
BAT_DIR = resource_path("assets", "bat")
APPS_JSON = resource_path("src", "apps.json")
