from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.mac_cleaner import JunkItem, is_safe_target, move_to_trash, path_size
from core.platform_utils import HOME, IS_MACOS, human_size

APPLICATION_DIRS = (Path("/Applications"), HOME / "Applications")

SYSTEM_ROOTS = (
    Path("/System"),
    Path("/System/Applications"),
    Path("/System/Library"),
    Path("/Library/CoreServices"),
)

PROTECTED_NAMES = frozenset({
    "Safari", "Finder", "System Settings", "System Preferences",
    "Terminal", "Utilities", "App Store", "Time Machine",
    "Disk Utility", "Keychain Access", "Migration Assistant",
})


@dataclass(frozen=True)
class MacAppEntry:
    name: str
    path: Path
    bundle_id: str
    version: str
    size: int
    cask_token: str | None = None

    @property
    def pretty_size(self) -> str:
        return human_size(self.size)

    @property
    def is_apple(self) -> bool:
        return self.bundle_id.startswith("com.apple.")

    @property
    def is_app_store(self) -> bool:
        return (self.path / "Contents" / "_MASReceipt").is_dir()

    @property
    def is_system_path(self) -> bool:
        resolved = self.path.absolute()
        return any(
            resolved == root or root in resolved.parents for root in SYSTEM_ROOTS
        )

    @property
    def is_running_self(self) -> bool:
        try:
            current = Path(sys.executable).resolve()
        except OSError:
            return False
        return self.path in current.parents or self.path == current

    @property
    def is_protected(self) -> bool:
        return (
            self.is_apple
            or self.is_system_path
            or self.is_running_self
            or self.name in PROTECTED_NAMES
        )

    @property
    def protection_reason(self) -> str:
        if self.is_running_self:
            return "Bu uygulamanin kendisi."
        if self.is_system_path:
            return "Sistem birimi uzerinde, kaldirilamaz."
        if self.is_apple:
            return "Apple sistem uygulamasi."
        if self.name in PROTECTED_NAMES:
            return "Korunan uygulama listesinde."
        return ""


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


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


def list_installed_apps(with_size: bool = True, cask_tokens: set[str] | None = None) -> list[MacAppEntry]:
    if not IS_MACOS:
        return []

    cask_tokens = cask_tokens or set()
    normalized_casks = {_normalize(token): token for token in cask_tokens}

    entries: list[MacAppEntry] = []
    for directory in APPLICATION_DIRS:
        if not directory.is_dir():
            continue
        try:
            bundles = sorted(directory.glob("*.app"))
        except OSError:
            continue

        for bundle in bundles:
            bundle_id, version = _read_bundle_info(bundle)
            token = normalized_casks.get(_normalize(bundle.stem))
            entries.append(MacAppEntry(
                name=bundle.stem,
                path=bundle,
                bundle_id=bundle_id,
                version=version,
                size=path_size(bundle) if with_size else 0,
                cask_token=token,
            ))

    entries.sort(key=lambda entry: entry.name.lower())
    return entries


def find_leftovers(entry: MacAppEntry) -> list[JunkItem]:
    patterns: list[str] = []

    if entry.bundle_id:
        patterns.extend([
            f"Library/Application Support/{entry.bundle_id}",
            f"Library/Caches/{entry.bundle_id}",
            f"Library/Preferences/{entry.bundle_id}.plist",
            f"Library/Preferences/ByHost/{entry.bundle_id}.*.plist",
            f"Library/Containers/{entry.bundle_id}",
            f"Library/Group Containers/*.{entry.bundle_id}",
            f"Library/HTTPStorages/{entry.bundle_id}",
            f"Library/HTTPStorages/{entry.bundle_id}.binarycookies",
            f"Library/Saved Application State/{entry.bundle_id}.savedState",
            f"Library/WebKit/{entry.bundle_id}",
            f"Library/Cookies/{entry.bundle_id}.binarycookies",
        ])

    patterns.extend([
        f"Library/Application Support/{entry.name}",
        f"Library/Caches/{entry.name}",
        f"Library/Logs/{entry.name}",
    ])

    found: list[JunkItem] = []
    seen: set[Path] = set()
    for pattern in patterns:
        try:
            matches = HOME.glob(pattern)
        except (OSError, ValueError):
            continue
        for match in matches:
            if match in seen or not is_safe_target(match):
                continue
            seen.add(match)
            found.append(JunkItem(
                path=match, size=path_size(match), rule_key="leftovers",
            ))

    found.sort(key=lambda item: item.size, reverse=True)
    return found


def _trash_with_finder(path: Path, timeout: int = 180) -> tuple[bool, str]:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped}"'
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Finder yanit vermedi."
    except OSError as exc:
        return False, str(exc)

    if proc.returncode == 0:
        return True, "Finder ile cop kutusuna tasindi."

    detail = (proc.stderr or proc.stdout or "").strip()
    if "-128" in detail:
        return False, "Islem kullanici tarafindan iptal edildi."
    if "-1743" in detail or "not allowed" in detail.lower():
        return False, (
            "Finder'i kontrol etme izni yok. System Settings > Privacy & Security "
            "> Automation altindan bu uygulamaya Finder izni ver."
        )
    return False, detail[:300] or "Finder kaldirmayi reddetti."


@dataclass
class UninstallPlan:
    entry: MacAppEntry
    leftovers: list[JunkItem] = field(default_factory=list)
    use_brew: bool = False

    @property
    def total_size(self) -> int:
        return self.entry.size + sum(item.size for item in self.leftovers)

    @property
    def pretty_total(self) -> str:
        return human_size(self.total_size)

    def describe(self) -> str:
        lines = [f"{self.entry.name} ({self.entry.pretty_size})"]
        if self.use_brew:
            lines.append(f"Homebrew ile kaldirilacak: {self.entry.cask_token}")
        else:
            lines.append(f"Cop kutusuna tasinacak: {self.entry.path}")
        if self.leftovers:
            lines.append(f"{len(self.leftovers)} artik dosya/klasor:")
            for item in self.leftovers[:12]:
                lines.append(f"  {item.path.name}  ({human_size(item.size)})")
            if len(self.leftovers) > 12:
                lines.append(f"  ... ve {len(self.leftovers) - 12} tane daha")
        lines.append(f"\nToplam: {self.pretty_total}")
        return "\n".join(lines)


def build_plan(entry: MacAppEntry, include_leftovers: bool = True) -> UninstallPlan:
    leftovers = find_leftovers(entry) if include_leftovers else []
    return UninstallPlan(
        entry=entry,
        leftovers=leftovers,
        use_brew=bool(entry.cask_token),
    )


def execute(plan: UninstallPlan, dry_run: bool = True) -> tuple[bool, int, list[str]]:
    entry = plan.entry
    messages: list[str] = []

    if entry.is_protected:
        return False, 0, [f"{entry.name}: {entry.protection_reason}"]

    if not entry.path.exists():
        return False, 0, [f"{entry.name}: uygulama bulunamadi."]

    if dry_run:
        return True, plan.total_size, [f"[dry-run] {plan.describe()}"]

    freed = 0
    success = True

    if plan.use_brew and entry.cask_token:
        from core.mac_installer import _run

        code, output = _run(["uninstall", "--cask", entry.cask_token], 900)
        if code == 0:
            freed += entry.size
            messages.append(f"{entry.cask_token} Homebrew ile kaldirildi.")
        else:
            success = False
            messages.append(f"brew uninstall basarisiz: {output[:200]}")
    else:
        moved = False
        try:
            move_to_trash(entry.path)
            moved = True
            freed += entry.size
            messages.append(f"{entry.name} cop kutusuna tasindi.")
        except (PermissionError, OSError):
            moved = False

        if not moved:
            ok, detail = _trash_with_finder(entry.path)
            if ok:
                freed += entry.size
                messages.append(f"{entry.name}: {detail}")
            else:
                success = False
                messages.append(f"{entry.name}: {detail}")
                if entry.is_app_store:
                    messages.append(
                        "Bu uygulama App Store uzerinden kurulmus. "
                        "Launchpad'de simgeyi basili tutup kaldirmak daha guvenli."
                    )

    for item in plan.leftovers:
        if not is_safe_target(item.path):
            messages.append(f"Guvenlik reddi: {item.path.name}")
            continue
        if not item.path.exists() and not item.path.is_symlink():
            continue
        try:
            move_to_trash(item.path)
            freed += item.size
        except OSError:
            messages.append(f"{item.path.name}: atlandi")

    return success, freed, messages
