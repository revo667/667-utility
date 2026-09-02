"""macOS temizlik motoru.

Kurallar (RULES) bildirimsel: her biri bir kategori altinda, bir kok dizine
gore glob desenleri tasir. Tarama paralel ve iptal edilebilir; silme her zaman
is_safe_target() suzgecinden gecer.
"""

from __future__ import annotations

import hashlib
import os
import plistlib
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from core.platform_utils import HOME, IS_MACOS, human_size

APPLICATION_DIRS = (Path("/Applications"), HOME / "Applications")
SYSTEM_APPLICATION_DIRS = (Path("/System/Applications"), Path("/System/Library/CoreServices"))

MB = 1024 * 1024
GB = 1024 * MB

#: Asla dokunulmayacak dizinler - bunlarin *icerigi* silinebilir, kendileri asla.
PROTECTED: frozenset[Path] = frozenset({
    Path("/"), Path("/System"), Path("/Library"), Path("/Applications"),
    Path("/Users"), Path("/private"), Path("/usr"), Path("/bin"), Path("/etc"),
    Path("/var"), Path("/tmp"), Path("/opt"), Path("/Volumes"),
    Path("/Library/Caches"), Path("/Library/Logs"), Path("/Library/Updates"),
    Path("/private/var"), Path("/private/var/log"), Path("/private/var/tmp"),
    Path("/private/var/folders"), Path("/Users/Shared"),
    HOME,
    HOME / "Library",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Downloads",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Music",
    HOME / "Public",
    HOME / "Applications",
    HOME / ".Trash",
    HOME / ".ssh",
    HOME / ".config",
    HOME / "Library" / "Caches",
    HOME / "Library" / "Logs",
    HOME / "Library" / "Containers",
    HOME / "Library" / "Group Containers",
    HOME / "Library" / "Preferences",
    HOME / "Library" / "Application Support",
    HOME / "Library" / "Keychains",
    HOME / "Library" / "Mobile Documents",
    HOME / "Library" / "Developer",
    HOME / "Library" / "WebKit",
    HOME / "Library" / "HTTPStorages",
    HOME / "Library" / "Saved Application State",
})

#: (kok, o koke gore minimum derinlik). Bu agaclarin disinda hicbir sey silinmez.
SAFE_ROOTS: tuple[tuple[Path, int], ...] = (
    (HOME, 2),
    (Path("/Library/Caches"), 1),
    (Path("/Library/Logs"), 1),
    (Path("/Library/Updates"), 1),
    (Path("/private/var/log"), 1),
    (Path("/private/var/folders"), 4),
    (Path("/private/var/tmp"), 1),
    (Path("/Users/Shared"), 1),
)

#: Tarama sirasinda hic girilmeyecek dizin adlari (derin tarama yururken).
WALK_SKIP_NAMES = frozenset({
    ".Trash", "Library", "Applications", ".git", ".hg", ".svn",
    "Photos Library.photoslibrary", "Pictures", ".Spotlight-V100",
    ".fseventsd", ".DocumentRevisions-V100",
})

#: Kopya taramasinda atlanan agaclar. Buralarda ayni dosyanin birden fazla kopyasi
#: kasitlidir - birini silmek projeyi bozar.
DUP_SKIP_NAMES = frozenset({
    "node_modules", ".venv", "venv", "site-packages", "Pods", "vendor",
    ".git", "target", ".next", ".nuxt", "DerivedData", ".gradle", ".cargo",
})


# --------------------------------------------------------------------- kural
@dataclass(frozen=True)
class JunkRule:
    key: str
    label: str
    description: str
    risk: str                       # safe | warning | danger
    globs: tuple[str, ...] = ()
    category: str = "Sistem"
    root: str = "home"              # home | root
    enabled_by_default: bool = True
    min_age_days: int = 0           # sadece bundan eski ogeler
    suffixes: tuple[str, ...] = ()  # bos ise uzanti filtresi yok
    deep: bool = False              # sadece "derin tarama" modunda calisir
    custom: str = ""                # _CUSTOM_FINDERS anahtari

    @property
    def base(self) -> Path:
        return HOME if self.root == "home" else Path("/")


RULES: tuple[JunkRule, ...] = (
    # ------------------------------------------------------------- Sistem
    JunkRule(
        key="user_caches",
        label="Uygulama Onbellekleri",
        description="~/Library/Caches icerigi. Uygulamalar gerektiginde yeniden olusturur.",
        risk="safe", category="Sistem",
        globs=("Library/Caches/*",),
    ),
    JunkRule(
        key="container_caches",
        label="Sandbox Onbellekleri",
        description="App Store uygulamalarinin container ici onbellekleri.",
        risk="safe", category="Sistem",
        globs=(
            "Library/Containers/*/Data/Library/Caches/*",
            "Library/Group Containers/*/Library/Caches/*",
        ),
    ),
    JunkRule(
        key="logs",
        label="Log ve Cokme Raporlari",
        description="Uygulama loglari, tani raporlari, cokme kayitlari.",
        risk="safe", category="Sistem",
        globs=(
            "Library/Logs/*",
            "Library/Application Support/CrashReporter/*",
            "Library/Containers/*/Data/Library/Logs/*",
        ),
    ),
    JunkRule(
        key="saved_state",
        label="Kaydedilmis Pencere Durumlari",
        description="Uygulamalarin pencere konumu hafizasi. Silinirse sifirdan acilirlar.",
        risk="safe", category="Sistem",
        globs=("Library/Saved Application State/*",),
    ),
    JunkRule(
        key="webkit_storage",
        label="WebKit Depolama",
        description="Gomulu web goruntuleyicilerin onbellegi (WebKit / WebCache).",
        risk="safe", category="Sistem",
        globs=(
            "Library/WebKit/*",
            "Library/Caches/com.apple.WebKit.*",
            "Library/Containers/*/Data/Library/WebKit/*/WebsiteData/*",
        ),
    ),
    JunkRule(
        key="quicklook",
        label="QuickLook Onizleme Onbellegi",
        description="Boslukla onizleme kucuk resimleri. Otomatik yeniden uretilir.",
        risk="safe", category="Sistem", root="root",
        globs=(
            "private/var/folders/*/*/C/com.apple.QuickLook.thumbnailcache",
            "private/var/folders/*/*/C/com.apple.iconservices*",
        ),
    ),
    JunkRule(
        key="update_leftovers",
        label="Guncelleme Artiklari",
        description="Indirilmis kurulum paketleri ve App Store onbellegi.",
        risk="warning", category="Sistem",
        globs=(
            "Library/Caches/com.apple.appstore/*",
            "Library/Caches/com.apple.SoftwareUpdate/*",
            "Library/Caches/com.apple.dt.Xcode/Downloads/*",
        ),
    ),
    JunkRule(
        key="system_caches",
        label="Sistem Onbellekleri (/Library)",
        description="Tum kullanicilar icin ortak onbellek. Yonetici izni gerekebilir.",
        risk="warning", category="Sistem", root="root",
        globs=("Library/Caches/*", "Library/Logs/DiagnosticReports/*"),
        enabled_by_default=False,
    ),
    JunkRule(
        key="temp_folders",
        label="Gecici Dosyalar (/private/var)",
        description="Acik uygulamalarin gecici alani. Uygulamalari kapatip calistir.",
        risk="warning", category="Sistem", root="root",
        globs=("private/var/tmp/*", "private/var/folders/*/*/T/*"),
        min_age_days=3,
        enabled_by_default=False,
    ),

    # ------------------------------------------------------- Gelistirici
    JunkRule(
        key="dev_caches",
        label="Paket Yoneticisi Onbellekleri",
        description="pip, npm, yarn, pnpm, bun, uv, Homebrew, cargo, go, gradle, maven.",
        risk="safe", category="Gelistirici",
        globs=(
            "Library/Caches/pip", "Library/Caches/uv", "Library/Caches/Homebrew",
            "Library/Caches/go-build", "Library/Caches/typescript",
            "Library/Caches/node-gyp", "Library/Caches/deno", "Library/Caches/ms-playwright",
            "Library/Caches/CocoaPods", "Library/Caches/org.carthage.CarthageKit",
            "Library/Caches/electron", "Library/Caches/electron-builder",
            ".npm/_cacache", ".yarn/cache", ".yarn/berry/cache",
            ".cache/uv", ".cache/pip", ".cache/yarn", ".cache/pnpm", ".cache/puppeteer",
            ".cache/huggingface", ".cache/torch", ".cache/ms-playwright",
            ".bun/install/cache", ".deno/gen",
            ".cargo/registry/cache", ".cargo/registry/src", ".rustup/downloads",
            ".gradle/caches", ".m2/repository/.cache", ".ivy2/cache",
            ".composer/cache", ".gem/specs", ".pub-cache/hosted",
            ".pyenv/cache", ".nvm/.cache", "go/pkg/mod/cache/download",
            "Library/pnpm/store",
        ),
    ),
    JunkRule(
        key="xcode",
        label="Xcode Artiklari",
        description="DerivedData, arsivler, cihaz destek dosyalari. Onlarca GB olabilir.",
        risk="warning", category="Gelistirici",
        globs=(
            "Library/Developer/Xcode/DerivedData/*",
            "Library/Developer/Xcode/Archives/*",
            "Library/Developer/Xcode/iOS DeviceSupport/*",
            "Library/Developer/Xcode/watchOS DeviceSupport/*",
            "Library/Developer/Xcode/tvOS DeviceSupport/*",
            "Library/Developer/Xcode/UserData/IB Support/*",
            "Library/Developer/XCPGDevices/*",
            "Library/Developer/CoreSimulator/Caches/*",
        ),
    ),
    JunkRule(
        key="simulators",
        label="Simulator Artiklari",
        description="Simulator cihazlarinin onbellek ve loglari. Cihazlar silinmez.",
        risk="safe", category="Gelistirici",
        globs=(
            "Library/Developer/CoreSimulator/Devices/*/data/Library/Caches/*",
            "Library/Developer/CoreSimulator/Devices/*/data/Library/Logs/*",
            "Library/Logs/CoreSimulator/*",
        ),
    ),
    JunkRule(
        key="ide_caches",
        label="Editor ve IDE Onbellekleri",
        description="VS Code, Cursor, JetBrains, Sublime onbellek ve loglari.",
        risk="safe", category="Gelistirici",
        globs=(
            "Library/Caches/JetBrains/*",
            "Library/Logs/JetBrains/*",
            "Library/Application Support/Code/Cache/*",
            "Library/Application Support/Code/CachedData/*",
            "Library/Application Support/Code/Code Cache/*",
            "Library/Application Support/Code/logs/*",
            "Library/Application Support/Cursor/Cache/*",
            "Library/Application Support/Cursor/CachedData/*",
            "Library/Application Support/Cursor/Code Cache/*",
            "Library/Application Support/Cursor/logs/*",
            "Library/Application Support/Sublime Text/Cache/*",
            "Library/Application Support/JetBrains/*/log/*",
        ),
    ),
    JunkRule(
        key="container_tools",
        label="Docker ve Sanal Makine Loglari",
        description="Docker/Colima log ve onbellekleri. Imajlara dokunulmaz.",
        risk="safe", category="Gelistirici",
        globs=(
            "Library/Caches/com.docker.docker/*",
            "Library/Containers/com.docker.docker/Data/log/*",
            "Library/Logs/Docker Desktop/*",
            ".colima/*/daemon.log",
        ),
    ),
    JunkRule(
        key="node_modules",
        label="Eski node_modules Klasorleri",
        description="30 gunden eski node_modules dizinleri. 'npm install' ile geri gelir.",
        risk="warning", category="Gelistirici",
        custom="node_modules", deep=True, min_age_days=30,
        enabled_by_default=False,
    ),

    # -------------------------------------------------------- Tarayicilar
    JunkRule(
        key="browser_caches",
        label="Tarayici Onbellekleri",
        description="Chrome, Safari, Firefox, Brave, Edge, Arc, Opera. Oturumlar korunur.",
        risk="safe", category="Tarayicilar",
        globs=(
            "Library/Caches/Google/Chrome/*",
            "Library/Caches/com.google.Chrome/*",
            "Library/Application Support/Google/Chrome/*/Service Worker/CacheStorage/*",
            "Library/Application Support/Google/Chrome/*/Code Cache/*",
            "Library/Application Support/Google/Chrome/*/GPUCache/*",
            "Library/Application Support/Google/Chrome/*/Application Cache/*",
            "Library/Caches/com.apple.Safari/*",
            "Library/Containers/com.apple.Safari/Data/Library/Caches/*",
            "Library/Caches/Firefox/Profiles/*/cache2/*",
            "Library/Caches/Mozilla/updates/*",
            "Library/Caches/BraveSoftware/*",
            "Library/Application Support/BraveSoftware/Brave-Browser/*/Code Cache/*",
            "Library/Caches/com.microsoft.edgemac/*",
            "Library/Application Support/Microsoft Edge/*/Code Cache/*",
            "Library/Caches/com.operasoftware.Opera/*",
            "Library/Caches/company.thebrowser.Browser/*",
            "Library/Caches/com.vivaldi.Vivaldi/*",
        ),
    ),
    JunkRule(
        key="browser_storage",
        label="Tarayici Site Verileri",
        description="HTTPStorages / IndexedDB artiklari. Bazi sitelerden cikis yapabilirsin.",
        risk="warning", category="Tarayicilar",
        globs=("Library/HTTPStorages/*",),
        enabled_by_default=False,
    ),

    # -------------------------------------------------------- Uygulamalar
    JunkRule(
        key="chat_caches",
        label="Mesajlasma Uygulamalari",
        description="Slack, Discord, Teams, Zoom onbellek ve loglari.",
        risk="safe", category="Uygulamalar",
        globs=(
            "Library/Application Support/Slack/Cache/*",
            "Library/Application Support/Slack/Code Cache/*",
            "Library/Application Support/Slack/Service Worker/CacheStorage/*",
            "Library/Application Support/Slack/logs/*",
            "Library/Application Support/discord/Cache/*",
            "Library/Application Support/discord/Code Cache/*",
            "Library/Application Support/discord/GPUCache/*",
            "Library/Application Support/Microsoft/Teams/Cache/*",
            "Library/Application Support/Microsoft/Teams/Code Cache/*",
            "Library/Application Support/Microsoft/Teams/logs/*",
            "Library/Application Support/zoom.us/AutoUpdater/*",
            "Library/Logs/zoom.us/*",
        ),
    ),
    JunkRule(
        key="media_apps",
        label="Muzik ve Medya Onbellekleri",
        description="Spotify, VLC, IINA gecici verileri.",
        risk="safe", category="Uygulamalar",
        globs=(
            "Library/Caches/com.spotify.client/*",
            "Library/Application Support/Spotify/PersistentCache/*",
            "Library/Caches/org.videolan.vlc/*",
            "Library/Caches/com.colliderli.iina/*",
        ),
    ),
    JunkRule(
        key="adobe",
        label="Adobe Onbellekleri",
        description="Media Cache ve Camera Raw onbellegi. Projeler etkilenmez.",
        risk="warning", category="Uygulamalar",
        globs=(
            "Library/Caches/Adobe/*",
            "Library/Application Support/Adobe/Common/Media Cache Files/*",
            "Library/Application Support/Adobe/Common/Media Cache/*",
            "Library/Application Support/Adobe/Common/Peak Files/*",
            "Library/Caches/Adobe Camera Raw*",
        ),
    ),
    JunkRule(
        key="games",
        label="Oyun Istemcisi Artiklari",
        description="Steam, Epic, Battle.net onbellek ve loglari. Oyunlar silinmez.",
        risk="safe", category="Uygulamalar",
        globs=(
            "Library/Application Support/Steam/appcache/*",
            "Library/Application Support/Steam/logs/*",
            "Library/Application Support/Steam/Steam.AppBundle/*/Contents/MacOS/*.log",
            "Library/Application Support/Epic/EpicGamesLauncher/Saved/Logs/*",
            "Library/Logs/Battle.net/*",
        ),
    ),
    JunkRule(
        key="mail",
        label="Mail Ekleri ve Indirmeleri",
        description="Mail.app'in acilan ek kopyalari. Mesajlar sunucuda kalir.",
        risk="warning", category="Uygulamalar",
        globs=(
            "Library/Containers/com.apple.mail/Data/Library/Mail Downloads/*",
            "Library/Containers/com.apple.mail/Data/Library/Caches/*",
        ),
        enabled_by_default=False,
    ),
    JunkRule(
        key="orphan_leftovers",
        label="Kaldirilmis Uygulama Artiklari",
        description="Yuklu olmayan uygulamalardan kalan ayar ve destek dosyalari.",
        risk="warning", category="Uygulamalar",
        custom="orphans", deep=True,
        enabled_by_default=False,
    ),

    # --------------------------------------------------------- Buyuk Veri
    JunkRule(
        key="ios_updates",
        label="iOS Yazilim Guncellemeleri",
        description="iPhone/iPad icin indirilmis IPSW dosyalari. Gerekirse yeniden iner.",
        risk="warning", category="Buyuk Veri",
        globs=(
            "Library/iTunes/iPhone Software Updates/*",
            "Library/iTunes/iPad Software Updates/*",
        ),
    ),
    JunkRule(
        key="old_installers",
        label="Eski Kurulum Dosyalari",
        description="Indirilenler klasorundeki 14 gunden eski dmg/pkg/iso arsivleri.",
        risk="warning", category="Buyuk Veri",
        globs=("Downloads/*",),
        suffixes=(".dmg", ".pkg", ".iso", ".msi"),
        min_age_days=14,
        enabled_by_default=False,
    ),
    JunkRule(
        key="old_downloads",
        label="Eski Indirilenler",
        description="90 gunden eski Downloads icerigi. Once bir goz at.",
        risk="danger", category="Buyuk Veri",
        globs=("Downloads/*",),
        min_age_days=90,
        enabled_by_default=False,
    ),
    JunkRule(
        key="trash",
        label="Cop Kutusu",
        description="~/.Trash icerigi. Bu geri donusu olmayan bir islem.",
        risk="warning", category="Buyuk Veri",
        globs=(".Trash/*",),
        enabled_by_default=False,
    ),
    JunkRule(
        key="ios_backups",
        label="iOS Yedekleri",
        description="iPhone/iPad yedekleri. Baska kopyan yoksa DOKUNMA.",
        risk="danger", category="Buyuk Veri",
        globs=("Library/Application Support/MobileSync/Backup/*",),
        enabled_by_default=False,
    ),
)

CATEGORY_ORDER: tuple[str, ...] = (
    "Sistem", "Gelistirici", "Tarayicilar", "Uygulamalar", "Buyuk Veri",
)


# --------------------------------------------------------------------- model
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


@dataclass(frozen=True)
class DuplicateGroup:
    digest: str
    size: int
    paths: tuple[Path, ...]

    @property
    def wasted(self) -> int:
        return self.size * max(0, len(self.paths) - 1)


# -------------------------------------------------------------------- guvenlik
def is_safe_target(path: Path) -> bool:
    """Silinmesine izin verilen bir yol mu? Supheli her sey False."""
    try:
        p = path.absolute()
    except OSError:
        return False

    if p in PROTECTED:
        return False

    for root, min_depth in SAFE_ROOTS:
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        return len(rel.parts) >= min_depth

    return False


def _cancelled(cancel: threading.Event | None) -> bool:
    return cancel is not None and cancel.is_set()


# ------------------------------------------------------------------- olcumler
def path_size(path: Path, cancel: threading.Event | None = None) -> int:
    """Sembolik baglantilari saymadan toplam bayt. Hatalar sessizce atlanir."""
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
        if _cancelled(cancel):
            return total
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


def path_age_days(path: Path) -> float:
    try:
        return max(0.0, (time.time() - path.stat().st_mtime) / 86400)
    except OSError:
        return 0.0


def disk_usage(mount: str = "/") -> tuple[int, int, int]:
    """(toplam, kullanilan, bos) bayt."""
    try:
        usage = shutil.disk_usage(mount)
        return usage.total, usage.used, usage.free
    except OSError:
        return 0, 0, 0


# ------------------------------------------------------------ ozel bulucular
def _find_node_modules(rule: JunkRule, cancel: threading.Event | None) -> list[Path]:
    """Ev dizininde makul derinlikte node_modules ara, icine girme."""
    found: list[Path] = []
    max_depth = 6
    home_str = str(HOME)

    for current, dirs, _files in os.walk(home_str, topdown=True):
        if _cancelled(cancel) or len(found) >= 400:
            break

        depth = current[len(home_str):].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue

        if "node_modules" in dirs:
            found.append(Path(current) / "node_modules")
            dirs.remove("node_modules")

        dirs[:] = [
            d for d in dirs
            if d not in WALK_SKIP_NAMES and not d.startswith(".")
        ]

    return found


def _bundle_like(name: str) -> str:
    """'com.foo.Bar.plist' -> 'com.foo.Bar'. Bundle id degilse bos doner."""
    stem = name
    for suffix in (".plist", ".savedState", ".binarycookies"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    # Group container'lar takim kimligi onegi tasir: S8EX82NJP6.com.macpaw.X
    parts = stem.split(".")
    if len(parts) > 3 and len(parts[0]) == 10 and parts[0].isupper() and parts[0].isalnum():
        parts = parts[1:]
        stem = ".".join(parts)

    if len(parts) < 3:
        return ""
    if not all(part and all(c.isalnum() or c in "-_" for c in part) for part in parts):
        return ""
    return stem


def _installed_bundle_ids() -> set[str]:
    ids: set[str] = set()
    for directory in (*APPLICATION_DIRS, *SYSTEM_APPLICATION_DIRS):
        if not directory.is_dir():
            continue
        try:
            bundles = list(directory.glob("*.app")) + list(directory.glob("*/*.app"))
        except OSError:
            continue
        for bundle in bundles:
            bundle_id, _ = _read_bundle_info(bundle)
            if bundle_id:
                ids.add(bundle_id.lower())
    return ids


def _find_orphans(rule: JunkRule, cancel: threading.Event | None) -> list[Path]:
    """Yuklu olmayan uygulamalarin bundle id'si adina acilmis klasorler."""
    installed = _installed_bundle_ids()
    # Cok az id okunabildiyse TCC/izin sorunu var demektir - yanlis pozitif uretme.
    if len(installed) < 20:
        return []

    # Apple ve sistem bilesenleri her zaman disarida.
    keep_prefixes = ("com.apple.", "group.com.apple.", "com.microsoft.autoupdate")

    search_dirs = (
        HOME / "Library" / "Application Support",
        HOME / "Library" / "Caches",
        HOME / "Library" / "Preferences",
        HOME / "Library" / "Containers",
        HOME / "Library" / "Saved Application State",
        HOME / "Library" / "HTTPStorages",
        HOME / "Library" / "WebKit",
    )

    found: list[Path] = []
    for directory in search_dirs:
        if _cancelled(cancel):
            break
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            bundle_id = _bundle_like(entry.name).lower()
            if not bundle_id or bundle_id in installed:
                continue
            if bundle_id.startswith(keep_prefixes):
                continue
            # Yardimci ve ust bilesenler: com.foo.App.helper <-> com.foo.App
            if any(
                bundle_id.startswith(f"{known}.") or known.startswith(f"{bundle_id}.")
                for known in installed
            ):
                continue
            found.append(Path(entry.path))

    return found


_CUSTOM_FINDERS: dict[str, Callable[[JunkRule, threading.Event | None], list[Path]]] = {
    "node_modules": _find_node_modules,
    "orphans": _find_orphans,
}


# --------------------------------------------------------------------- tarama
def _rule_matches(rule: JunkRule, cancel: threading.Event | None) -> Iterable[Path]:
    if rule.custom:
        finder = _CUSTOM_FINDERS.get(rule.custom)
        return finder(rule, cancel) if finder else []

    base = rule.base
    matches: list[Path] = []
    for pattern in rule.globs:
        if _cancelled(cancel):
            break
        try:
            matches.extend(base.glob(pattern))
        except (OSError, ValueError):
            continue
    return matches


def scan_rule(rule: JunkRule, cancel: threading.Event | None = None) -> ScanResult:
    """Tek kurali tara. Dedupe yapmaz - scan_all sonrasinda toplu yapilir."""
    result = ScanResult(rule=rule)
    seen: set[Path] = set()

    for match in _rule_matches(rule, cancel):
        if _cancelled(cancel):
            break
        if match in seen or not is_safe_target(match):
            continue
        if rule.suffixes and match.suffix.lower() not in rule.suffixes:
            continue
        if rule.min_age_days and path_age_days(match) < rule.min_age_days:
            continue

        size = path_size(match, cancel)
        if size <= 0:
            continue
        seen.add(match)
        result.items.append(JunkItem(path=match, size=size, rule_key=rule.key))

    result.items.sort(key=lambda item: item.size, reverse=True)
    return result


def _dedupe(results: list[ScanResult]) -> list[ScanResult]:
    """Ayni yol iki kurala dusmusse ilk kuralda kalir; alt yollar da elenir."""
    claimed: set[Path] = set()
    cleaned: list[ScanResult] = []

    for result in results:
        kept: list[JunkItem] = []
        for item in result.items:
            if item.path in claimed:
                continue
            if any(parent in claimed for parent in item.path.parents):
                continue
            claimed.add(item.path)
            kept.append(item)
        cleaned.append(ScanResult(rule=result.rule, items=kept))

    return cleaned


def active_rules(deep: bool = False, rules: Iterable[JunkRule] = RULES) -> list[JunkRule]:
    return [rule for rule in rules if deep or not rule.deep]


def scan_all(
    rules: Iterable[JunkRule] = RULES,
    progress_cb: Callable[[int, int, str], None] | None = None,
    *,
    deep: bool = False,
    cancel: threading.Event | None = None,
    workers: int = 6,
) -> list[ScanResult]:
    """Tum kurallari paralel tara, sonuclari kural sirasina gore dondur."""
    if not IS_MACOS:
        return []

    selected = active_rules(deep, rules)
    total = len(selected)
    if not total:
        return []

    results: dict[str, ScanResult] = {}
    done = 0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(scan_rule, rule, cancel): rule for rule in selected}
        for future, rule in futures.items():
            try:
                results[rule.key] = future.result()
            except Exception:
                results[rule.key] = ScanResult(rule=rule)
            done += 1
            if progress_cb:
                progress_cb(done, total, rule.label)
            if _cancelled(cancel):
                break

    ordered = [results.get(rule.key, ScanResult(rule=rule)) for rule in selected]
    return _dedupe(ordered)


# ------------------------------------------------------------- buyuk dosyalar
def find_large_files(
    min_size: int = 200 * MB,
    roots: Iterable[Path] | None = None,
    limit: int = 300,
    cancel: threading.Event | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> list[JunkItem]:
    """Ev dizinindeki buyuk dosyalari bul (Library ve gizli agaclar haric)."""
    if not IS_MACOS:
        return []

    roots = list(roots) if roots else [HOME]
    found: list[JunkItem] = []
    scanned = 0

    for root in roots:
        for current, dirs, files in os.walk(str(root), topdown=True):
            if _cancelled(cancel):
                break
            dirs[:] = [
                d for d in dirs
                if d not in WALK_SKIP_NAMES and not d.endswith((".app", ".photoslibrary"))
            ]
            scanned += 1
            if progress_cb and scanned % 200 == 0:
                progress_cb(current)

            for name in files:
                path = Path(current) / name
                try:
                    if path.is_symlink():
                        continue
                    size = path.stat().st_size
                except OSError:
                    continue
                if size >= min_size:
                    found.append(JunkItem(path=path, size=size, rule_key="large_files"))

        if _cancelled(cancel):
            break

    found.sort(key=lambda item: item.size, reverse=True)
    return found[:limit]


# ------------------------------------------------------------------ kopyalar
def _digest(path: Path, partial: bool = True, chunk: int = 256 * 1024) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as handle:
            if partial:
                hasher.update(handle.read(chunk))
            else:
                while True:
                    block = handle.read(1024 * 1024)
                    if not block:
                        break
                    hasher.update(block)
    except OSError:
        return ""
    return hasher.hexdigest()


def find_duplicates(
    roots: Iterable[Path] | None = None,
    min_size: int = 5 * MB,
    cancel: threading.Event | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> list[DuplicateGroup]:
    """Boyut -> kismi hash -> tam hash zinciriyle birebir ayni dosyalari bul."""
    if not IS_MACOS:
        return []

    if roots is None:
        roots = [
            HOME / "Downloads", HOME / "Documents", HOME / "Desktop",
            HOME / "Movies", HOME / "Music",
        ]

    by_size: dict[int, list[Path]] = {}
    for root in roots:
        if not Path(root).is_dir():
            continue
        for current, dirs, files in os.walk(str(root), topdown=True):
            if _cancelled(cancel):
                return []
            dirs[:] = [
                d for d in dirs
                if d not in DUP_SKIP_NAMES
                and not d.startswith(".")
                and not d.endswith((".app", ".photoslibrary"))
            ]
            for name in files:
                path = Path(current) / name
                try:
                    if path.is_symlink():
                        continue
                    size = path.stat().st_size
                except OSError:
                    continue
                if size >= min_size:
                    by_size.setdefault(size, []).append(path)

    groups: list[DuplicateGroup] = []
    candidates = {size: paths for size, paths in by_size.items() if len(paths) > 1}

    for size, paths in candidates.items():
        if _cancelled(cancel):
            break
        if progress_cb:
            progress_cb(human_size(size))

        partial_buckets: dict[str, list[Path]] = {}
        for path in paths:
            key = _digest(path, partial=True)
            if key:
                partial_buckets.setdefault(key, []).append(path)

        for bucket in partial_buckets.values():
            if len(bucket) < 2:
                continue
            full_buckets: dict[str, list[Path]] = {}
            for path in bucket:
                key = _digest(path, partial=False)
                if key:
                    full_buckets.setdefault(key, []).append(path)
            for digest, same in full_buckets.items():
                if len(same) > 1:
                    groups.append(DuplicateGroup(
                        digest=digest, size=size, paths=tuple(sorted(same)),
                    ))

    groups.sort(key=lambda group: group.wasted, reverse=True)
    return groups


# --------------------------------------------------------------------- silme
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
    progress_cb: Callable[[int, int, Path], None] | None = None,
    cancel: threading.Event | None = None,
) -> tuple[int, list[str]]:
    freed = 0
    errors: list[str] = []
    total = len(items)

    for index, item in enumerate(items, start=1):
        if _cancelled(cancel):
            errors.append("Islem kullanici tarafindan durduruldu.")
            break
        if progress_cb:
            progress_cb(index, total, item.path)

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


def reveal_in_finder(path: Path) -> bool:
    if not IS_MACOS:
        return False
    try:
        subprocess.run(["open", "-R", str(path)], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- uygulamalar
@dataclass(frozen=True)
class MacApp:
    name: str
    path: Path
    bundle_id: str
    version: str
    size: int


def _info_plist_path(bundle: Path) -> Path | None:
    """Mac uygulamalari Contents/Info.plist tasir; iPhone/iPad uygulamalari Wrapper/ altinda."""
    candidates = [bundle / "Contents" / "Info.plist", bundle / "Info.plist"]
    try:
        candidates.extend(sorted(bundle.glob("Wrapper/*.app/Info.plist")))
    except OSError:
        pass
    return next((path for path in candidates if path.is_file()), None)


def _read_bundle_info(bundle: Path) -> tuple[str, str]:
    info = _info_plist_path(bundle)
    if info is None:
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
