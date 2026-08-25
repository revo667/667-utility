from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from core.platform_utils import IS_MACOS

BREW_CANDIDATES = (
    "/opt/homebrew/bin/brew",
    "/usr/local/bin/brew",
    "/home/linuxbrew/.linuxbrew/bin/brew",
)

INSTALL_COMMAND = (
    '/bin/bash -c "$(curl -fsSL '
    'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
)

SEARCH_TIMEOUT = 60
INSTALL_TIMEOUT = 1800
LIST_TIMEOUT = 60


@dataclass(frozen=True)
class Package:
    token: str
    kind: str

    @property
    def is_cask(self) -> bool:
        return self.kind == "cask"

    @property
    def label(self) -> str:
        suffix = "uygulama" if self.is_cask else "komut satiri"
        return f"{self.token}  ({suffix})"


@lru_cache(maxsize=1)
def brew_path() -> str | None:
    found = shutil.which("brew")
    if found:
        return found
    for candidate in BREW_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_available() -> bool:
    return IS_MACOS and brew_path() is not None


def install_instructions() -> str:
    return (
        "Homebrew kurulu degil. Terminal'de su komutu calistir:\n\n"
        f"{INSTALL_COMMAND}\n\n"
        "Kurulum bittikten sonra bu sayfayi yenile."
    )


def _run(args: list[str], timeout: int) -> tuple[int, str]:
    brew = brew_path()
    if not brew:
        return -1, "brew bulunamadi."

    env = dict(os.environ)
    env.setdefault("HOMEBREW_NO_AUTO_UPDATE", "1")
    env.setdefault("HOMEBREW_NO_ENV_HINTS", "1")
    env.setdefault("NONINTERACTIVE", "1")

    try:
        proc = subprocess.run(
            [brew, *args],
            capture_output=True, text=True, timeout=timeout,
            check=False, env=env, encoding="utf-8", errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output.strip()
    except FileNotFoundError:
        return -1, "brew bulunamadi."
    except subprocess.TimeoutExpired:
        return -2, "Islem zaman asimina ugradi."
    except OSError as exc:
        return -3, str(exc)


def _parse_tokens(output: str) -> list[str]:
    tokens = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("==>") or line.startswith("Warning"):
            continue
        if line.startswith("If you meant") or line.endswith(":"):
            continue
        tokens.extend(part for part in line.split() if part)
    return tokens


def search(query: str, limit: int = 40) -> tuple[bool, list[Package], str]:
    query = (query or "").strip()
    if not query:
        return False, [], "Bos arama yapilamaz."
    if not is_available():
        return False, [], install_instructions()

    results: list[Package] = []
    seen: set[str] = set()
    errors: list[str] = []

    for kind, flag in (("cask", "--cask"), ("formula", "--formula")):
        code, output = _run(["search", flag, query], SEARCH_TIMEOUT)
        if code != 0:
            errors.append(output)
            continue
        for token in _parse_tokens(output):
            if token in seen:
                continue
            seen.add(token)
            results.append(Package(token=token, kind=kind))

    if not results:
        return False, [], errors[0] if errors else "Sonuc bulunamadi."

    results.sort(key=lambda p: (not p.token.lower().startswith(query.lower()), p.token))
    return True, results[:limit], ""


def describe(package: Package) -> str:
    flag = "--cask" if package.is_cask else "--formula"
    code, output = _run(["info", flag, package.token], SEARCH_TIMEOUT)
    if code != 0:
        return ""
    for line in output.splitlines():
        line = line.strip()
        if line and not line.startswith("==>") and not line.startswith(package.token):
            return line
    return ""


def install(package: Package) -> tuple[bool, str]:
    if not is_available():
        return False, install_instructions()

    args = ["install"]
    if package.is_cask:
        args.append("--cask")
    args.append(package.token)

    code, output = _run(args, INSTALL_TIMEOUT)
    if code == 0:
        return True, f"{package.token} kuruldu."
    return False, output or f"Kurulum basarisiz (kod {code})."


def installed_casks() -> set[str]:
    if not is_available():
        return set()
    code, output = _run(["list", "--cask", "-1"], LIST_TIMEOUT)
    if code != 0:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def installed_formulae() -> set[str]:
    if not is_available():
        return set()
    code, output = _run(["list", "--formula", "-1"], LIST_TIMEOUT)
    if code != 0:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}
