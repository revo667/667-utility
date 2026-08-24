"""macOS izin (TCC) yonetimi.

Onemli gercek: macOS'ta bir uygulama kendine izin VEREMEZ. Sadece iki sey yapabilir:
  1. Korumali bir klasore dokunup sistemin izin dialogunu tetiklemek,
  2. Kullaniciyi System Settings > Privacy & Security ekranina goturmek.

Bu modul ikisini de yapar. Sihir yok, sadece durust bir yonlendirme.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.platform_utils import HOME, IS_MACOS

# Full Disk Access olmadan okunamayan kanonik dosya. FDA testi icin sondaj noktasi.
_FDA_PROBE = HOME / "Library" / "Application Support" / "com.apple.TCC" / "TCC.db"

# TCC tarafindan korunan, ilk erisimde dialog tetikleyen klasorler
PROTECTED_USER_DIRS = {
    "desktop": HOME / "Desktop",
    "documents": HOME / "Documents",
    "downloads": HOME / "Downloads",
}

_SETTINGS_URLS = {
    "full_disk": "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
    "files_folders": "x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders",
    "privacy": "x-apple.systempreferences:com.apple.preference.security?Privacy",
}


@dataclass(frozen=True)
class AccessReport:
    full_disk_access: bool
    home_readable: bool
    applications_readable: bool
    blocked_dirs: tuple[str, ...]

    @property
    def is_sufficient(self) -> bool:
        """Temel temizlik icin yeterli mi? FDA sart degil, ~/Library yeterli."""
        return self.home_readable and not self.blocked_dirs

    def summary(self) -> str:
        if not IS_MACOS:
            return "macOS disi sistem - izin kontrolu atlandi."
        if self.full_disk_access:
            return "Full Disk Access verilmis. Tum tarama alanlari acik."
        if self.is_sufficient:
            return "Temel erisim var. Bazi sistem alanlari icin Full Disk Access gerekebilir."
        blocked = ", ".join(self.blocked_dirs)
        return f"Erisim engellendi: {blocked}. Ayarlardan izin vermen gerekiyor."


def can_read(path: Path) -> bool:
    """Klasoru gercekten listeleyebiliyor muyuz? os.access() TCC'yi yakalayamaz, deneyip gormek gerekir."""
    try:
        with os.scandir(path) as it:
            next(iter(it), None)
        return True
    except PermissionError:
        return False
    except FileNotFoundError:
        return True  # yoksa engel de yok
    except OSError:
        return False


def has_full_disk_access() -> bool:
    if not IS_MACOS:
        return False
    try:
        with open(_FDA_PROBE, "rb") as fh:
            fh.read(1)
        return True
    except (PermissionError, OSError):
        return False


def check_access(applications_dir: Path = Path("/Applications")) -> AccessReport:
    """Uygulama acilisinda bir kere cagir, sonucu UI'da goster."""
    if not IS_MACOS:
        return AccessReport(False, True, True, ())

    blocked = tuple(
        name for name, path in PROTECTED_USER_DIRS.items()
        if path.exists() and not can_read(path)
    )
    return AccessReport(
        full_disk_access=has_full_disk_access(),
        home_readable=can_read(HOME / "Library"),
        applications_readable=can_read(applications_dir),
        blocked_dirs=blocked,
    )


def prompt_native_dialogs() -> None:
    """Korumali klasorlere dokunarak macOS'un kendi izin dialogunu tetikler.

    Kullanici 'Allow' derse izin kalici olarak verilir. 'Don't Allow' derse
    tekrar sormaz - o durumda open_privacy_settings() ile Ayarlar'a yonlendir.
    """
    if not IS_MACOS:
        return
    for path in PROTECTED_USER_DIRS.values():
        try:
            with os.scandir(path) as it:
                next(iter(it), None)
        except (PermissionError, OSError):
            continue


def open_privacy_settings(pane: str = "full_disk") -> bool:
    """System Settings > Privacy & Security ekranini acar."""
    if not IS_MACOS:
        return False
    url = _SETTINGS_URLS.get(pane, _SETTINGS_URLS["privacy"])
    try:
        subprocess.run(["open", url], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
