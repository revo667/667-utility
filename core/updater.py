
from __future__ import annotations

import json
import os
import re
import shlex
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from core import account
from core.platform_utils import IS_LINUX, IS_MACOS, IS_WINDOWS
from core.resources import is_frozen
from core.version import APP_VERSION, BUILD_SHA, short_sha

REPO = "revo667/667-utility"
API = f"https://api.github.com/repos/{REPO}"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
NIGHTLY_TAG = "nightly"

CHANNELS = ("stable", "nightly")
TIMEOUT_SECONDS = 30
USER_AGENT = "667Utility"

#: Windows'ta paketin icindeki yurutulebilirin adi (spec ile ayni).
WINDOWS_EXE = "667Utility.exe"
LINUX_EXE = "667Utility"


class UpdateError(Exception):
    """Kullaniciya gosterilebilecek, beklenen hata."""


@dataclass(frozen=True)
class Release:
    """Indirilebilir tek bir yayin."""

    tag: str
    label: str          # arayuzde gosterilen ad ("v0.3.0" / "gece surumu a1b2c3d")
    name: str           # dosya adi
    url: str
    size: int
    kind: str           # zip | dmg | targz
    published_at: str


@dataclass(frozen=True)
class CheckResult:
    release: Release | None
    message: str


# --------------------------------------------------------------------- ag

def _is_github_host(hostname: str | None) -> bool:
    """Yalnizca GitHub konaklarindan indiriyoruz - yonlendirme baska yere
    giderse birakiyoruz."""
    host = (hostname or "").lower()
    return (
        host == "github.com"
        or host.endswith(".github.com")
        or host.endswith("githubusercontent.com")
    )


def _request(url: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"Accept": accept, "User-Agent": USER_AGENT}
    )


def _urlopen(request: urllib.request.Request, timeout: int = TIMEOUT_SECONDS):
    """urlopen + sertifika yedegi.

    Python'un sertifika deposu bos gelen kurulumlarda (macOS'ta sik)
    dogrulama patliyor. account.trust_context() isletim sisteminin
    koklerini yukluyor - ayni cozumu burada tekrar yazmiyoruz.
    """
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as error:
        verify_failed = isinstance(error.reason, ssl.SSLCertVerificationError) or (
            "CERTIFICATE_VERIFY_FAILED" in str(error.reason)
        )
        context = account.trust_context() if verify_failed else None

        if context is None:
            raise

        return urllib.request.urlopen(request, timeout=timeout, context=context)


def _api(path: str) -> object:
    url = f"{API}{path}"
    try:
        with _urlopen(_request(url, "application/vnd.github+json")) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 403 neredeyse her zaman saatlik istek siniri (kimliksiz: 60/saat).
        if exc.code == 403:
            raise UpdateError("GitHub istek siniri asildi, biraz sonra dene") from exc
        raise UpdateError(f"GitHub {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise UpdateError(f"baglanti kurulamadi ({exc})") from exc


# ----------------------------------------------------------------- surum

def is_newer_version(candidate: str, current: str) -> bool:
    """1.2.3 > 1.2.0 karsilastirmasi. On-surum etiketleri (-beta) yok sayilir."""

    def parse(value: str) -> list[int]:
        cleaned = re.sub(r"^v", "", str(value).strip()).split("-")[0]
        parts: list[int] = []
        for chunk in cleaned.split(".")[:3]:
            parts.append(int(chunk) if chunk.isdigit() else 0)
        return parts + [0] * (3 - len(parts))

    left, right = parse(candidate), parse(current)
    return left > right


def _asset_pattern() -> tuple[str, str] | None:
    """(dosya sonu, tur) - bu platform icin yayinlanan dosya.

    Sonekler .github/workflows/build.yml icindeki arsivleme adimlariyla
    birebir ayni olmali; degisirse guncelleme sessizce 'dosya yok' der.
    """
    if IS_WINDOWS:
        return "-windows-x64.zip", "zip"
    if IS_MACOS:
        return "-macos.dmg", "dmg"
    if IS_LINUX:
        return "-linux-x86_64.tar.gz", "targz"
    return None


def _pick_asset(release: dict) -> dict | None:
    pattern = _asset_pattern()
    if pattern is None:
        return None
    suffix, kind = pattern
    for asset in release.get("assets") or []:
        if str(asset.get("name", "")).endswith(suffix):
            return {**asset, "kind": kind}
    return None


def _find_release(channel: str) -> dict | None:
    releases = _api("/releases?per_page=30")
    if not isinstance(releases, list):
        return None

    if channel == "stable":
        for item in releases:
            if not item.get("prerelease") and not item.get("draft") \
                    and item.get("tag_name") != NIGHTLY_TAG:
                return item
        return None

    for item in releases:
        if not item.get("draft"):
            return item
    return None


def _tag_sha(tag: str) -> str:
    """Etiketin isaret ettigi commit. Annotated etiketlerde bir adim fazla."""
    ref = _api(f"/git/ref/tags/{tag}")
    if not isinstance(ref, dict):
        return ""
    obj = ref.get("object") or {}
    if obj.get("type") == "tag":
        annotated = _api(f"/git/tags/{obj.get('sha')}")
        if isinstance(annotated, dict):
            return str((annotated.get("object") or {}).get("sha") or "")
    return str(obj.get("sha") or "")


def check(channel: str = "stable") -> CheckResult:
    """Yeni surum var mi? Ag hatasinda UpdateError firlatir."""
    if not is_frozen():
        return CheckResult(None, "gelistirme surumu - guncelleme kapali")

    release = _find_release(channel if channel in CHANNELS else "stable")
    if release is None:
        return CheckResult(None, "yayin bulunamadi")

    asset = _pick_asset(release)
    if asset is None:
        return CheckResult(None, f"bu platform icin dosya yok ({sys.platform})")

    tag = str(release.get("tag_name") or "")

    if tag == NIGHTLY_TAG:
        # Gece etiketi her yayinda tasindigi icin surum numarasi degismez;
        # hangi commit'ten uretildigini etiketin sha'si soyler.
        sha = _tag_sha(NIGHTLY_TAG)
        newer = bool(sha) and short_sha(sha) != short_sha(BUILD_SHA)
        label = f"gece surumu {short_sha(sha)}"
    else:
        newer = is_newer_version(tag, APP_VERSION)
        label = tag

    if not newer:
        return CheckResult(None, "guncel - en son surumu kullaniyorsun")

    return CheckResult(
        Release(
            tag=tag,
            label=label,
            name=str(asset.get("name") or ""),
            url=str(asset.get("browser_download_url") or ""),
            size=int(asset.get("size") or 0),
            kind=str(asset.get("kind") or ""),
            published_at=str(release.get("published_at") or ""),
        ),
        "guncelleme hazir",
    )


# --------------------------------------------------------------- indirme

ProgressCallback = Callable[[int], None]


def download(
    release: Release,
    on_progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[Path, Path]:
    """Dosyayi gecici klasore indirir, (klasor, dosya) doner."""
    if not _is_github_host(urlparse(release.url).hostname):
        raise UpdateError("beklenmeyen indirme adresi")

    directory = Path(tempfile.mkdtemp(prefix="667utility-update-"))
    target = directory / (release.name or "paket")

    try:
        with _urlopen(_request(release.url, "application/octet-stream")) as response:
            # urllib yonlendirmeyi kendi izler; varis noktasi da GitHub olmali.
            if not _is_github_host(urlparse(response.geturl()).hostname):
                raise UpdateError("yonlendirme GitHub disina cikti")

            total = int(response.headers.get("Content-Length") or release.size or 0)
            received = 0
            last_percent = -1

            with open(target, "wb") as handle:
                while True:
                    if should_cancel is not None and should_cancel():
                        raise UpdateError("indirme iptal edildi")

                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break

                    handle.write(chunk)
                    received += len(chunk)

                    percent = int(received * 100 / total) if total else 0
                    if on_progress is not None and percent != last_percent:
                        last_percent = percent
                        on_progress(percent)

        if total and received != total:
            raise UpdateError("indirme yarim kaldi")
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"indirme basarisiz ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"indirme basarisiz ({exc})") from exc

    return directory, target


# ---------------------------------------------------------------- kurulum

def app_root() -> Path:
    """Yerine konacak paketin koku.

    Windows/Linux (onedir): yurutulebilirin klasoru.
    macOS: .../667 Utility.app
    """
    executable = Path(sys.executable).resolve()

    if IS_MACOS:
        # .app/Contents/MacOS/667 Utility -> .app
        bundle = executable.parents[2] if len(executable.parents) >= 3 else executable.parent
        if bundle.suffix != ".app":
            raise UpdateError("uygulama paketi bulunamadi")
        return bundle

    return executable.parent


def _detach(command: list[str]) -> None:
    """Betigi uygulamadan bagimsiz baslatir - biz kapaninca o yasamaya devam eder."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if IS_WINDOWS:
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        kwargs["start_new_session"] = True

    subprocess.Popen(command, **kwargs)


def _write_script(path: Path, lines: list[str], executable: bool) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if executable:
        os.chmod(path, 0o700)
    return path


def _install_windows(archive: Path, workdir: Path, target: Path) -> None:
    stage = workdir / "stage"
    backup = target.with_name(target.name + ".old")

    import zipfile

    try:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(stage)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError(f"arsiv acilamadi ({exc})") from exc

    if not (stage / WINDOWS_EXE).is_file():
        raise UpdateError("arsiv beklenen dosyayi icermiyor")

    script = _write_script(workdir / "install.cmd", [
        "@echo off",
        # Wait-Process surec bitene kadar bekler; zaten bitmisse hata verir, yutuyoruz.
        'powershell -NoProfile -Command "try { Wait-Process -Id '
        f'{os.getpid()} -Timeout 60 }} catch {{ }}"',
        f'move /Y "{target}" "{backup}" >nul || exit /b 1',
        f'mkdir "{target}" >nul 2>&1',
        f'robocopy "{stage}" "{target}" /E /NFL /NDL /NJH /NJS /NP >nul',
        # robocopy 8 ve ustu = gercek hata; altindakiler "kopyalandi" anlaminda.
        "if errorlevel 8 goto restore",
        f'rmdir /s /q "{backup}"',
        f'start "" "{target}\\{WINDOWS_EXE}"',
        "exit /b 0",
        ":restore",
        f'rmdir /s /q "{target}"',
        f'move /Y "{backup}" "{target}" >nul',
        f'start "" "{target}\\{WINDOWS_EXE}"',
        "exit /b 1",
    ], executable=False)

    _detach(["cmd.exe", "/c", str(script)])


def _install_macos(archive: Path, workdir: Path, target: Path) -> None:
    mount = workdir / "mnt"
    backup = workdir / "backup.app"

    script = _write_script(workdir / "install.sh", [
        "#!/bin/sh",
        f"PID={os.getpid()}",
        f"APP={shlex.quote(str(target))}",
        f"DMG={shlex.quote(str(archive))}",
        f"MOUNT={shlex.quote(str(mount))}",
        f"BACKUP={shlex.quote(str(backup))}",
        "i=0",
        'while kill -0 "$PID" 2>/dev/null && [ "$i" -lt 150 ]; do sleep 0.2; i=$((i+1)); done',
        'mkdir -p "$MOUNT" || exit 1',
        'hdiutil attach "$DMG" -nobrowse -readonly -noautoopen -mountpoint "$MOUNT" '
        ">/dev/null 2>&1 || exit 1",
        'NEW=$(find "$MOUNT" -maxdepth 1 -name "*.app" | head -1)',
        'if [ -z "$NEW" ]; then hdiutil detach "$MOUNT" -quiet; exit 1; fi',
        'if ! mv "$APP" "$BACKUP"; then hdiutil detach "$MOUNT" -quiet; exit 1; fi',
        'if ditto "$NEW" "$APP"; then',
        '  rm -rf "$BACKUP"',
        # Imzasiz paket indirildigi icin karantina damgasi tasir; kaldirmazsak
        # Gatekeeper "hasarli" der ve uygulama hic acilmaz.
        '  xattr -dr com.apple.quarantine "$APP" 2>/dev/null',
        "else",
        '  rm -rf "$APP"',
        '  mv "$BACKUP" "$APP"',
        "fi",
        'hdiutil detach "$MOUNT" -quiet',
        'open "$APP"',
    ], executable=True)

    _detach(["/bin/sh", str(script)])


def _install_linux(archive: Path, workdir: Path, target: Path) -> None:
    stage = workdir / "stage"
    backup = workdir / "backup"

    script = _write_script(workdir / "install.sh", [
        "#!/bin/sh",
        f"PID={os.getpid()}",
        f"APP={shlex.quote(str(target))}",
        f"TGZ={shlex.quote(str(archive))}",
        f"STAGE={shlex.quote(str(stage))}",
        f"BACKUP={shlex.quote(str(backup))}",
        "i=0",
        'while kill -0 "$PID" 2>/dev/null && [ "$i" -lt 150 ]; do sleep 0.2; i=$((i+1)); done',
        'mkdir -p "$STAGE" || exit 1',
        'tar -xzf "$TGZ" -C "$STAGE" || exit 1',
        f'NEW=$(find "$STAGE" -maxdepth 2 -type f -name {shlex.quote(LINUX_EXE)} | head -1)',
        '[ -n "$NEW" ] || exit 1',
        'NEW=$(dirname "$NEW")',
        'mv "$APP" "$BACKUP" || exit 1',
        'if cp -R "$NEW" "$APP"; then',
        '  rm -rf "$BACKUP"',
        "else",
        '  rm -rf "$APP"',
        '  mv "$BACKUP" "$APP"',
        "fi",
        f'"$APP/{LINUX_EXE}" >/dev/null 2>&1 &',
    ], executable=True)

    _detach(["/bin/sh", str(script)])


def install(release: Release, archive: Path, workdir: Path) -> None:
    """Kurulum betigini baslatir. Doner donmez uygulama kapatilmali."""
    if not is_frozen():
        raise UpdateError("gelistirme surumu - guncelleme kapali")

    target = app_root()

    # Paketin kendi klasorunu degil, kaynak agacini guncellemeye calismak
    # gelistirme kurulumunu bozar.
    if "site-packages" in str(target) or target == Path(target.anchor):
        raise UpdateError("gecersiz kurulum konumu")

    if release.kind == "zip":
        _install_windows(archive, workdir, target)
    elif release.kind == "dmg":
        _install_macos(archive, workdir, target)
    elif release.kind == "targz":
        _install_linux(archive, workdir, target)
    else:
        raise UpdateError("desteklenmeyen paket turu")


def open_releases() -> None:
    import webbrowser

    webbrowser.open(RELEASES_PAGE)


def current_label() -> str:
    """Arayuzde gosterilen surum satiri."""
    build = short_sha()
    if not is_frozen():
        return f"{APP_VERSION} · gelistirme"
    return f"{APP_VERSION} · yapi {build}" if build else APP_VERSION
