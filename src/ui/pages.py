from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from core.platform_utils import IS_LINUX, IS_MACOS, IS_WINDOWS

WINDOWS = "win32"
MACOS = "darwin"
LINUX = "linux"
ALL_PLATFORMS = frozenset({WINDOWS, MACOS, LINUX})


def current_platform() -> str:
    if IS_WINDOWS:
        return WINDOWS
    if IS_MACOS:
        return MACOS
    if IS_LINUX:
        return LINUX
    return "unknown"


@dataclass(frozen=True)
class PageSpec:
    key: str
    label: str
    factory: Callable[[], QWidget]
    icon: str = "dashboard"
    section: str = "ARACLAR"
    platforms: frozenset[str] = ALL_PLATFORMS

    def is_available(self) -> bool:
        return current_platform() in self.platforms




def _dashboard() -> QWidget:
    from src.ui.views.dashboard import DashboardView
    return DashboardView()


def _optimizer() -> QWidget:
    from src.ui.views.optimizer import OptimizerPage
    return OptimizerPage()


def _installer() -> QWidget:
    from src.ui.views.installer import InstallerView
    return InstallerView()


def _uninstaller() -> QWidget:
    from src.ui.views.uninstaller import UninstallerView
    return UninstallerView()


def _mac_cleaner() -> QWidget:
    from src.ui.views.mac_cleaner import MacCleanerPage
    return MacCleanerPage()


def _mac_installer() -> QWidget:
    from src.ui.views.mac_installer import MacInstallerPage
    return MacInstallerPage()


def _mac_uninstaller() -> QWidget:
    from src.ui.views.mac_uninstaller import MacUninstallerPage
    return MacUninstallerPage()


def _mac_snapshots() -> QWidget:
    from src.ui.views.mac_snapshots import MacSnapshotsPage
    return MacSnapshotsPage()


def _settings() -> QWidget:
    from src.ui.views.settings import SettingsPage
    return SettingsPage()


PAGES: tuple[PageSpec, ...] = (
    PageSpec("dashboard", "Dashboard", _dashboard, "dashboard", "GENEL"),

    PageSpec("optimizer", "Optimizer", _optimizer, "optimizer", "ARACLAR",
             frozenset({WINDOWS})),
    PageSpec("installer", "Installer", _installer, "installer", "ARACLAR",
             frozenset({WINDOWS, LINUX})),
    PageSpec("uninstaller", "Uninstaller", _uninstaller, "uninstaller", "ARACLAR",
             frozenset({WINDOWS})),

    PageSpec("mac_installer", "Installer", _mac_installer, "installer", "ARACLAR",
             frozenset({MACOS})),
    PageSpec("mac_uninstaller", "Uninstaller", _mac_uninstaller, "uninstaller", "ARACLAR",
             frozenset({MACOS})),
    PageSpec("mac_cleaner", "Cleaner", _mac_cleaner, "cleaner", "ARACLAR",
             frozenset({MACOS})),
    PageSpec("mac_snapshots", "Snapshots", _mac_snapshots, "snapshots", "ARACLAR",
             frozenset({MACOS})),

    PageSpec("settings", "Ayarlar", _settings, "settings", "SISTEM"),
)


def available_pages() -> list[PageSpec]:
    return [spec for spec in PAGES if spec.is_available()]


def page_by_key(key: str) -> PageSpec | None:
    return next((spec for spec in PAGES if spec.key == key), None)
