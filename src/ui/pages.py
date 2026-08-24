from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QWidget

WINDOWS = "win32"
MACOS = "darwin"
LINUX = "linux"
ALL_PLATFORMS = frozenset({WINDOWS, MACOS, LINUX})


def current_platform() -> str:
    if sys.platform == "win32":
        return WINDOWS
    if sys.platform == "darwin":
        return MACOS
    if sys.platform.startswith("linux"):
        return LINUX
    return sys.platform


@dataclass(frozen=True)
class PageSpec:
    key: str
    label: str
    factory: Callable[[], QWidget]
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


PAGES: tuple[PageSpec, ...] = (
    PageSpec(
        key="dashboard",
        label="Dashboard",
        factory=_dashboard,
        platforms=ALL_PLATFORMS,
    ),
    PageSpec(
        key="optimizer",
        label="Optimizer",
        factory=_optimizer,
        platforms=frozenset({WINDOWS}),
    ),
    PageSpec(
        key="installer",
        label="Installer",
        factory=_installer,
        platforms=frozenset({WINDOWS, LINUX}),
    ),
    PageSpec(
        key="uninstaller",
        label="Uninstaller",
        factory=_uninstaller,
        platforms=frozenset({WINDOWS}),
    ),
    PageSpec(
        key="mac_installer",
        label="Installer",
        factory=_mac_installer,
        platforms=frozenset({MACOS}),
    ),
    PageSpec(
        key="mac_uninstaller",
        label="Uninstaller",
        factory=_mac_uninstaller,
        platforms=frozenset({MACOS}),
    ),
    PageSpec(
        key="mac_cleaner",
        label="Cleaner",
        factory=_mac_cleaner,
        platforms=frozenset({MACOS}),
    ),
)


def available_pages() -> list[PageSpec]:
    return [spec for spec in PAGES if spec.is_available()]
