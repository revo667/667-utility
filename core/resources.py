"""Paketlenmis ve gelistirme calismasinda ayni yolu veren tek kaynak.

Sorun: PyInstaller uygulamayi calistirirken dosyalari gecici bir klasore acar
ve `__file__` oraya isaret eder. `Path(__file__).parent.parent / "assets"`
gibi hesaplar sessizce yanlis yol uretir - font yuklenmez, .reg dosyalari
bulunamaz, hicbir hata da gorunmez.

Cozum: tabani tek yerden hesapla.
  - PyInstaller altinda    -> sys._MEIPASS
  - .app icinde (onedir)   -> yurutulebilirin yanindaki Resources
  - normal calisma         -> proje koku
"""

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
    """resource_path("assets", "regs") -> dogru mutlak yol."""
    return base_path().joinpath(*parts)


#: Sik kullanilanlar - tek tek hesaplamak yerine.
ASSETS_DIR = resource_path("assets")
REGS_DIR = resource_path("assets", "regs")
BAT_DIR = resource_path("assets", "bat")
APPS_JSON = resource_path("src", "apps.json")
