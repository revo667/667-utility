from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.platform_utils import HOME, IS_MACOS, human_size

APPLICATION_DIRS = (Path("/Applications"), HOME / "Applications")

PROTECTED: frozenset[Path] = frozenset({
    Path("/"), Path("/System"), Path("/Library"), Path("/Applications"),
    Path("/Users"), Path("/private"), Path("/usr"), Path("/bin"), Path("/etc"),
    HOME,
    HOME / "Library",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Downloads",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Music",
    HOME / "Applications",
    HOME / ".Trash",
    HOME / ".ssh",
    HOME / "Library" / "Caches",
    HOME / "Library" / "Logs",
    HOME / "Library" / "Containers",
    HOME / "Library" / "Preferences",
    HOME / "Library" / "Application Support",
    HOME / "Library" / "Keychains",
    HOME / "Library" / "Mobile Documents",
})


@dataclass(frozen=True)
class JunkRule:
    key: str
    label: str
    description: str
    risk: str
    globs: tuple[str, ...]
    enabled_by_default: bool = True


RULES: tuple[JunkRule, ...] = (
    JunkRule(
        key="dev_caches",
        label="Gelistirici Onbellekleri",
        description="pip, npm, uv, Homebrew, cargo onbellekleri. Silinince yeniden indirilir.",
        risk="safe",
        globs=(
            "Library/Caches/pip", "Library/Caches/uv", "Library/Caches/Homebrew",
            "Library/Caches/go-build", "Library/Caches/typescript",
            ".npm/_cacache", ".cache/uv", ".cache/pip", ".cargo/registry/cache",
            ".gradle/caches", ".m2/repository/.cache",
        ),
    ),
    JunkRule(
        key="xcode",
        label="Xcode Artiklari",
        description="DerivedData, arsivler, simulator onbellekleri. Onlarca GB olabilir.",
        risk="warning",
        globs=(
            "Library/Developer/Xcode/DerivedData/*",
            "Library/Developer/Xcode/Archives/*",
            "Library/Developer/Xcode/iOS DeviceSupport/*",
            "Library/Developer/CoreSimulator/Caches/*",
        ),
    ),
    JunkRule(
        key="user_caches",
        label="Uygulama Onbellekleri",
        description="~/Library/Caches icerigi. Uygulamalar gerektiginde yeniden olusturur.",
        risk="safe",
        globs=("Library/Caches/*",),
    ),
    JunkRule(
        key="container_caches",
        label="Sandbox Onbellekleri",
        description="App Store uygulamalarinin container ici onbellekleri.",
        risk="safe",
        globs=("Library/Containers/*/Data/Library/Caches/*",),
    ),
    JunkRule(
        key="logs",
        label="Log Dosyalari",
        description="Uygulama loglari ve tani raporlari.",
        risk="safe",
        globs=(
            "Library/Logs/*",
            "Library/Application Support/CrashReporter/*",
        ),
    ),
    JunkRule(
        key="saved_state",
        label="Kaydedilmis Pencere Durumlari",
        description="Uygulamalarin pencere konumu hafizasi. Silinirse sifirdan acilirlar.",
        risk="safe",
        globs=("Library/Saved Application State/*",),
    ),
    JunkRule(
        key="trash",
        label="Cop Kutusu",
        description="~/.Trash icerigi. Bu geri donusu olmayan bir islem.",
        risk="warning",
        globs=(".Trash/*",),
        enabled_by_default=False,
    ),
    JunkRule(
        key="ios_backups",
        label="iOS Yedekleri",
        description="iPhone/iPad yedekleri. Baska kopyan yoksa DOKUNMA.",
        risk="danger",
        globs=("Library/Application Support/MobileSync/Backup/*",),
        enabled_by_default=False,
    ),
)


@dataclass(frozen=True)
class JunkItem:
    path: Path
    size: int
    rule_key: str


@dataclass
class ScanResult:
    rule: JunkRule
    items: list[JunkItem] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.items)

    @property
    def pretty_size(self) -> str:
        return human_size(self.total_size)


def is_safe_target(path: Path) -> bool:
    try:
        p = path.absolute()
    except OSError:
        return False

    if p in PROTECTED:
        return False

    try:
        rel = p.relative_to(HOME)
    except ValueError:
        return False

    return len(rel.parts) >= 2


def path_size(path: Path) -> int:
    try:
        if path.is_symlink():
            return 0
        stat = path.stat()
    except OSError:
        return 0

    if not path.is_dir():
        return stat.st_size

    total = 0
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def scan_rule(rule: JunkRule, seen: set[Path] | None = None) -> ScanResult:
    seen = seen if seen is not None else set()
    result = ScanResult(rule=rule)

    for pattern in rule.globs:
        try:
            matches = HOME.glob(pattern)
        except (OSError, ValueError):
            continue
        for match in matches:
            if match in seen or not is_safe_target(match):
                continue
            size = path_size(match)
            if size <= 0:
                continue
            seen.add(match)
            result.items.append(JunkItem(path=match, size=size, rule_key=rule.key))

    result.items.sort(key=lambda item: item.size, reverse=True)
    return result


def scan_all(rules=RULES, progress_cb=None) -> list[ScanResult]:
    if not IS_MACOS:
        return []

    seen: set[Path] = set()
    results: list[ScanResult] = []
    total = len(rules)
    for index, rule in enumerate(rules, start=1):
        if progress_cb:
            progress_cb(index, total, rule.label)
        results.append(scan_rule(rule, seen))
    return results


def _unique_trash_target(trash: Path, name: str) -> Path:
    candidate = trash / name
    if not candidate.exists() and not candidate.is_symlink():
        return candidate

    stamp = time.strftime("%Y%m%d-%H%M%S")
    counter = 0
    while True:
        tag = stamp if counter == 0 else f"{stamp}-{counter}"
        candidate = trash / f"{name}-{tag}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        counter += 1


def move_to_trash(path: Path) -> Path:
    trash = HOME / ".Trash"
    trash.mkdir(exist_ok=True)
    target = _unique_trash_target(trash, path.name)
    shutil.move(str(path), str(target))
    return target


def clean(
    items: list[JunkItem],
    *,
    dry_run: bool = True,
    permanent: bool = False,
) -> tuple[int, list[str]]:
    freed = 0
    errors: list[str] = []

    for item in items:
        if not is_safe_target(item.path):
            errors.append(f"Guvenlik reddi: {item.path}")
            continue
        if not item.path.exists() and not item.path.is_symlink():
            continue
        if dry_run:
            freed += item.size
            continue

        try:
            if permanent:
                if item.path.is_symlink() or item.path.is_file():
                    item.path.unlink()
                else:
                    shutil.rmtree(item.path)
            else:
                move_to_trash(item.path)
            freed += item.size
        except OSError as exc:
            errors.append(f"{item.path.name}: atlandi ({exc.strerror or exc})")

    return freed, errors


@dataclass(frozen=True)
class MacApp:
    name: str
    path: Path
    bundle_id: str
    version: str
    size: int


def _read_bundle_info(bundle: Path) -> tuple[str, str]:
    info = bundle / "Contents" / "Info.plist"
    if not info.is_file():
        return "", ""

    data = None
    try:
        with open(info, "rb") as handle:
            data = plistlib.load(handle)
    except Exception:
        data = None

    if data is None:
        try:
            proc = subprocess.run(
                ["plutil", "-convert", "xml1", "-o", "-", str(info)],
                capture_output=True, timeout=10, check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                data = plistlib.loads(proc.stdout)
        except Exception:
            data = None

    if not isinstance(data, dict):
        return "", ""

    bundle_id = data.get("CFBundleIdentifier", "")
    version = (
        data.get("CFBundleShortVersionString")
        or data.get("CFBundleVersion")
        or ""
    )
    return str(bundle_id), str(version)


def list_applications() -> list[MacApp]:
    if not IS_MACOS:
        return []

    apps: list[MacApp] = []
    for directory in APPLICATION_DIRS:
        if not directory.is_dir():
            continue
        try:
            entries = sorted(directory.glob("*.app"))
        except OSError:
            continue

        for bundle in entries:
            bundle_id, version = _read_bundle_info(bundle)

            apps.append(MacApp(
                name=bundle.stem,
                path=bundle,
                bundle_id=bundle_id,
                version=version,
                size=path_size(bundle),
            ))

    apps.sort(key=lambda app: app.name.lower())
    return apps


def find_leftovers(app: MacApp) -> list[JunkItem]:
    if not app.bundle_id:
        return []

    patterns = (
        f"Library/Application Support/{app.bundle_id}",
        f"Library/Application Support/{app.name}",
        f"Library/Caches/{app.bundle_id}",
        f"Library/Preferences/{app.bundle_id}.plist",
        f"Library/Containers/{app.bundle_id}",
        f"Library/HTTPStorages/{app.bundle_id}",
        f"Library/Saved Application State/{app.bundle_id}.savedState",
        f"Library/Logs/{app.name}",
        f"Library/WebKit/{app.bundle_id}",
    )

    found: list[JunkItem] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for match in HOME.glob(pattern):
            if match in seen or not is_safe_target(match):
                continue
            seen.add(match)
            found.append(JunkItem(path=match, size=path_size(match), rule_key="leftovers"))

    found.sort(key=lambda item: item.size, reverse=True)
    return found
