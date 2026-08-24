from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from core.platform_utils import IS_MACOS

_TERMINAL_HOSTS = {
    "Terminal": "Terminal",
    "iTerm2": "iTerm",
    "Code": "Visual Studio Code",
    "Code Helper": "Visual Studio Code",
    "Electron": "Visual Studio Code",
    "pycharm": "PyCharm",
    "WezTerm": "WezTerm",
    "Alacritty": "Alacritty",
    "kitty": "kitty",
    "Ghostty": "Ghostty",
    "Warp": "Warp",
    "Hyper": "Hyper",
}


@dataclass(frozen=True)
class ResponsibleProcess:
    is_bundled: bool
    bundle_path: Path | None
    host_name: str
    host_path: Path | None
    chain: tuple[str, ...]

    @property
    def grant_target(self) -> str:
        if self.is_bundled and self.bundle_path:
            return self.bundle_path.name
        return self.host_name

    def instructions(self) -> str:
        if not IS_MACOS:
            return "macOS disi sistem."

        if self.is_bundled and self.bundle_path:
            return (
                f"System Settings > Privacy & Security > Full Disk Access\n"
                f"'+' butonuna bas ve su paketi ekle:\n{self.bundle_path}"
            )

        target = self.host_path or self.host_name
        return (
            "Bu uygulama bir .app paketi olarak calismiyor, bu yuzden listede "
            "kendi adiyla gorunmez.\n\n"
            "macOS izni onu baslatan uygulamaya atar. Su an sorumlu uygulama:\n"
            f"{self.grant_target}\n\n"
            "System Settings > Privacy & Security > Full Disk Access altinda "
            f"'{self.grant_target}' girdisini ac, sonra uygulamayi TAMAMEN kapatip "
            "yeniden baslat (pencere kapatmak yetmez).\n\n"
            f"Yol: {target}"
        )


def _bundle_root() -> Path | None:
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent
    main = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if main:
        for parent in main.parents:
            if parent.suffix == ".app":
                return parent
    return None


def _parent_chain(limit: int = 12) -> list:
    try:
        import psutil
    except ImportError:
        return []

    chain = []
    try:
        process = psutil.Process(os.getpid())
    except Exception:
        return []

    for _ in range(limit):
        try:
            process = process.parent()
        except Exception:
            break
        if process is None:
            break
        chain.append(process)
    return chain


def identify_responsible() -> ResponsibleProcess:
    bundle = _bundle_root()
    if bundle is not None:
        return ResponsibleProcess(
            is_bundled=True,
            bundle_path=bundle,
            host_name=bundle.stem,
            host_path=bundle,
            chain=(bundle.name,),
        )

    chain_names = []
    host_name = "Terminal"
    host_path = None

    for process in _parent_chain():
        try:
            name = process.name()
            exe = process.exe()
        except Exception:
            continue

        chain_names.append(name)

        app_root = None
        for parent in Path(exe).parents:
            if parent.suffix == ".app":
                app_root = parent
                break

        if app_root is not None:
            host_path = app_root
            host_name = _TERMINAL_HOSTS.get(app_root.stem, app_root.stem)
            break

        mapped = _TERMINAL_HOSTS.get(name)
        if mapped:
            host_name = mapped
            host_path = Path(exe)
            break

    return ResponsibleProcess(
        is_bundled=False,
        bundle_path=None,
        host_name=host_name,
        host_path=host_path,
        chain=tuple(chain_names),
    )
