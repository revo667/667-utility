"""Kucuk kalici ayar deposu.

QSettings yerine duz JSON: dosyanin nerede oldugunu biliyoruz, elle
duzenlenebiliyor ve platformlar arasi ayni davraniyor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.platform_utils import HOME, IS_MACOS, IS_WINDOWS

APP_NAME = "667Utility"

DEFAULTS: dict[str, Any] = {
    "rain_enabled": True,
    "rain_density": 90,      # damla sayisi
    "rain_fps": 45,          # 60 yerine 45: gorsel fark yok, pil farki var
    "dashboard_refresh_ms": 2000,
    "confirm_destructive": True,
    "last_page": "dashboard",
}


def config_dir() -> Path:
    if IS_WINDOWS:
        import os
        base = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
    elif IS_MACOS:
        base = HOME / "Library" / "Application Support"
    else:
        base = HOME / ".config"
    return base / APP_NAME


def config_path() -> Path:
    return config_dir() / "settings.json"


class Settings:
    """Tek instance uzerinden okunur/yazilir. Yazma hatasi uygulamayi durdurmaz."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        path = config_path()
        if not path.is_file():
            return
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            # Bilinmeyen anahtarlari yok say - eski surumden kalan cop tasinmasin.
            self._data.update({k: v for k, v in stored.items() if k in DEFAULTS})

    def save(self) -> bool:
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            config_path().write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, fallback))

    def set(self, key: str, value: Any, *, persist: bool = True) -> None:
        self._data[key] = value
        if persist:
            self.save()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)


#: Uygulama genelinde tek ornek.
settings = Settings()
