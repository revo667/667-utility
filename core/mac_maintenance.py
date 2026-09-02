"""macOS bakim islemleri.

Dosya silmekten farkli olarak burada sistem komutlari calisiyor. Yonetici
gerektirenler osascript uzerinden macOS'un kendi parola diyalogunu acar -
uygulama parolayi hicbir zaman gormez.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.platform_utils import HOME, IS_MACOS, human_size

TIMEOUT = 180


@dataclass(frozen=True)
class MaintenanceTask:
    key: str
    label: str
    description: str
    risk: str                  # safe | warning | danger
    needs_admin: bool = False
    shell: str = ""            # yonetici gerektiren tek satirlik komut
    handler: str = ""          # _HANDLERS anahtari (shell yerine)


@dataclass(frozen=True)
class TaskResult:
    ok: bool
    message: str


# ------------------------------------------------------------------ yardimci
def _run(args: list[str], timeout: int = TIMEOUT) -> tuple[bool, str]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError:
        return False, f"Komut bulunamadi: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, "Islem zaman asimina ugradi."
    except OSError as exc:
        return False, str(exc)

    output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode == 0, output


def run_privileged(command: str, prompt: str) -> tuple[bool, str]:
    """Komutu macOS'un yonetici parolasi diyaloguyla calistirir."""
    if not IS_MACOS:
        return False, "macOS disi sistem."

    script = (
        f"do shell script {json.dumps(command)} "
        f"with administrator privileges "
        f"with prompt {json.dumps(prompt)}"
    )
    ok, output = _run(["osascript", "-e", script])
    if not ok and ("-128" in output or "User canceled" in output):
        return False, "Yonetici izni verilmedi."
    return ok, output


# ------------------------------------------------------------- ozel islemler
def _empty_trash() -> TaskResult:
    trash = HOME / ".Trash"
    if not trash.is_dir():
        return TaskResult(True, "Cop kutusu zaten bos.")

    freed = 0
    failed = 0
    for entry in trash.iterdir():
        try:
            size = _entry_size(entry)
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            else:
                shutil.rmtree(entry)
            freed += size
        except OSError:
            failed += 1

    message = f"{human_size(freed)} kalici olarak silindi."
    if failed:
        message += f" {failed} oge atlandi (kullanimda olabilir)."
    return TaskResult(True, message)


def _entry_size(path: Path) -> int:
    from core.mac_cleaner import path_size
    return path_size(path)


def _rebuild_launch_services() -> TaskResult:
    binary = (
        "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/"
        "LaunchServices.framework/Versions/A/Support/lsregister"
    )
    if not Path(binary).exists():
        return TaskResult(False, "lsregister bulunamadi.")
    ok, output = _run([
        binary, "-kill", "-r",
        "-domain", "local", "-domain", "system", "-domain", "user",
    ])
    return TaskResult(ok, "Ac ile menusu yeniden olusturuldu." if ok else output)


def _reset_quicklook() -> TaskResult:
    ok, output = _run(["qlmanage", "-r", "cache"])
    if ok:
        _run(["qlmanage", "-r"])
    return TaskResult(ok, "QuickLook onbellegi sifirlandi." if ok else output)


def _restart_finder() -> TaskResult:
    _run(["killall", "Finder"])
    _run(["killall", "Dock"])
    return TaskResult(True, "Finder ve Dock yeniden baslatildi.")


def list_local_snapshots() -> list[str]:
    """Time Machine yerel anlik goruntuleri."""
    if not IS_MACOS:
        return []
    ok, output = _run(["tmutil", "listlocalsnapshots", "/"], timeout=30)
    if not ok:
        return []
    return [
        line.strip() for line in output.splitlines()
        if line.strip().startswith("com.apple.TimeMachine")
    ]


def _thin_snapshots() -> TaskResult:
    snapshots = list_local_snapshots()
    if not snapshots:
        return TaskResult(True, "Silinecek yerel anlik goruntu yok.")

    dates = []
    for snapshot in snapshots:
        # com.apple.TimeMachine.2026-09-01-120000.local -> 2026-09-01-120000
        parts = snapshot.split(".")
        if len(parts) >= 4:
            dates.append(parts[3])

    if not dates:
        return TaskResult(False, "Anlik goruntu adlari cozulemedi.")

    command = " ; ".join(f"/usr/bin/tmutil deletelocalsnapshots {date}" for date in dates)
    ok, output = run_privileged(command, "667 Utility yerel yedekleri siliyor")
    return TaskResult(ok, f"{len(dates)} anlik goruntu silindi." if ok else output)


def _flush_dns() -> TaskResult:
    command = "/usr/bin/dscacheutil -flushcache ; /usr/bin/killall -HUP mDNSResponder"
    ok, output = run_privileged(command, "667 Utility DNS onbellegini temizliyor")
    return TaskResult(ok, "DNS onbellegi temizlendi." if ok else output)


def _purge_memory() -> TaskResult:
    ok, output = run_privileged("/usr/sbin/purge", "667 Utility bellek onbellegini bosaltiyor")
    return TaskResult(ok, "Inaktif bellek serbest birakildi." if ok else output)


def _font_cache() -> TaskResult:
    command = "/System/Library/Frameworks/ApplicationServices.framework/Frameworks/ATS.framework/Support/atsutil databases -remove"
    ok, output = run_privileged(command, "667 Utility yazi tipi onbellegini siliyor")
    return TaskResult(ok, "Yazi tipi onbellegi silindi. Oturumu yeniden ac." if ok else output)


def _reindex_spotlight() -> TaskResult:
    ok, output = run_privileged(
        "/usr/bin/mdutil -E /", "667 Utility Spotlight dizinini yeniliyor"
    )
    return TaskResult(ok, "Spotlight yeniden dizinleniyor (arka planda surer)." if ok else output)


def _periodic_scripts() -> TaskResult:
    ok, output = run_privileged(
        "/usr/sbin/periodic daily weekly monthly",
        "667 Utility sistem bakim betiklerini calistiriyor",
    )
    return TaskResult(ok, "Gunluk/haftalik/aylik bakim betikleri calisti." if ok else output)


def _verify_disk() -> TaskResult:
    ok, output = _run(["diskutil", "verifyVolume", "/"], timeout=300)
    tail = "\n".join(output.splitlines()[-6:]) if output else ""
    return TaskResult(ok, tail or ("Disk saglikli gorunuyor." if ok else "Dogrulama basarisiz."))


def _repair_permissions() -> TaskResult:
    """Ev dizini izinlerini ve ACL'leri sifirla."""
    command = (
        f"/usr/sbin/diskutil resetUserPermissions / $(id -u) "
        f"|| /bin/chmod -R -N {json.dumps(str(HOME))}"
    )
    ok, output = run_privileged(command, "667 Utility ev dizini izinlerini onariyor")
    return TaskResult(ok, "Izinler sifirlandi." if ok else output)


_HANDLERS: dict[str, Callable[[], TaskResult]] = {
    "empty_trash": _empty_trash,
    "launch_services": _rebuild_launch_services,
    "quicklook": _reset_quicklook,
    "restart_finder": _restart_finder,
    "thin_snapshots": _thin_snapshots,
    "flush_dns": _flush_dns,
    "purge_memory": _purge_memory,
    "font_cache": _font_cache,
    "spotlight": _reindex_spotlight,
    "periodic": _periodic_scripts,
    "verify_disk": _verify_disk,
    "repair_permissions": _repair_permissions,
}


TASKS: tuple[MaintenanceTask, ...] = (
    MaintenanceTask(
        key="empty_trash",
        label="Cop Kutusunu Bosalt",
        description="~/.Trash icerigini kalici olarak siler. Geri alinamaz.",
        risk="warning", handler="empty_trash",
    ),
    MaintenanceTask(
        key="purge_memory",
        label="Bellegi Bosalt",
        description="Inaktif RAM onbellegini serbest birakir. Sistem bir an yavaslayabilir.",
        risk="safe", needs_admin=True, handler="purge_memory",
    ),
    MaintenanceTask(
        key="flush_dns",
        label="DNS Onbellegini Temizle",
        description="Site cozumleme sorunlarinda ilk denenecek adim.",
        risk="safe", needs_admin=True, handler="flush_dns",
    ),
    MaintenanceTask(
        key="quicklook",
        label="QuickLook Onbellegini Sifirla",
        description="Bozuk onizleme kucuk resimlerini yeniden urettirir.",
        risk="safe", handler="quicklook",
    ),
    MaintenanceTask(
        key="launch_services",
        label="'Birlikte Ac' Menusunu Onar",
        description="Yinelenen veya hayalet uygulama girdilerini temizler.",
        risk="safe", handler="launch_services",
    ),
    MaintenanceTask(
        key="font_cache",
        label="Yazi Tipi Onbellegini Sil",
        description="Bozuk font gorunumlerini duzeltir. Oturum yenilemesi gerekir.",
        risk="warning", needs_admin=True, handler="font_cache",
    ),
    MaintenanceTask(
        key="thin_snapshots",
        label="Yerel Time Machine Yedeklerini Sil",
        description="Diski dolduran yerel anlik goruntuleri kaldirir. Harici yedek etkilenmez.",
        risk="warning", needs_admin=True, handler="thin_snapshots",
    ),
    MaintenanceTask(
        key="periodic",
        label="Sistem Bakim Betiklerini Calistir",
        description="macOS'un gunluk/haftalik/aylik log rotasyonunu tetikler.",
        risk="safe", needs_admin=True, handler="periodic",
    ),
    MaintenanceTask(
        key="spotlight",
        label="Spotlight Dizinini Yenile",
        description="Arama sonuclari eksikse. Yeniden dizinleme saatler surebilir.",
        risk="warning", needs_admin=True, handler="spotlight",
    ),
    MaintenanceTask(
        key="restart_finder",
        label="Finder ve Dock'u Yeniden Baslat",
        description="Takilan Dock/Finder icin hizli cozum. Acik pencereler kapanmaz.",
        risk="safe", handler="restart_finder",
    ),
    MaintenanceTask(
        key="verify_disk",
        label="Diski Dogrula",
        description="Baslangic diskini salt-okunur kontrol eder. Degisiklik yapmaz.",
        risk="safe", handler="verify_disk",
    ),
    MaintenanceTask(
        key="repair_permissions",
        label="Ev Dizini Izinlerini Onar",
        description="Bozuk ACL'leri sifirlar. Uzun surebilir.",
        risk="danger", needs_admin=True, handler="repair_permissions",
    ),
)


def run_task(task: MaintenanceTask) -> TaskResult:
    if not IS_MACOS:
        return TaskResult(False, "Bu islem yalnizca macOS'ta calisir.")

    handler = _HANDLERS.get(task.handler)
    if handler is None:
        if not task.shell:
            return TaskResult(False, "Tanimsiz islem.")
        ok, output = run_privileged(task.shell, f"667 Utility: {task.label}")
        return TaskResult(ok, output or task.label)

    try:
        return handler()
    except Exception as exc:  # bakim islemi UI'yi cokertmemeli
        return TaskResult(False, str(exc))


def task_by_key(key: str) -> MaintenanceTask | None:
    return next((task for task in TASKS if task.key == key), None)
