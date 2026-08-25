from __future__ import annotations

import os
import platform
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import psutil

from core.platform_utils import IS_LINUX, IS_MACOS, IS_WINDOWS

_MACOS_NAMES = {
    "26": "Tahoe",
    "15": "Sequoia",
    "14": "Sonoma",
    "13": "Ventura",
    "12": "Monterey",
    "11": "Big Sur",
}


def _sysctl(key: str) -> str:
    try:
        proc = subprocess.run(
            ["sysctl", "-n", key],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return (proc.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


@lru_cache(maxsize=1)
def cpu_name() -> str:
    if IS_MACOS:
        brand = _sysctl("machdep.cpu.brand_string")
        if brand:
            return brand

    if IS_LINUX:
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass

    return platform.processor() or platform.machine() or "Bilinmiyor"


@lru_cache(maxsize=1)
def os_name() -> str:
    if IS_MACOS:
        version = platform.mac_ver()[0] or ""
        major = version.split(".")[0] if version else ""
        friendly = _MACOS_NAMES.get(major, "")
        label = f"macOS {version}".strip()
        return f"{label} {friendly}".strip() if friendly else label

    if IS_WINDOWS:
        return f"Windows {platform.release()} ({platform.version()})"

    return f"{platform.system()} {platform.release()}"


@lru_cache(maxsize=1)
def data_volume() -> str:
    if IS_MACOS:
        candidate = "/System/Volumes/Data"
        if os.path.isdir(candidate):
            return candidate
        return "/"

    if IS_WINDOWS:
        # Windows bunu "SystemDrive" olarak tanimlar; buyuk harfli varyant yedek.
        drive = os.environ.get("SystemDrive") or os.environ.get("SYSTEMDRIVE") or "C:"  # noqa: SIM112
        return drive + "\\"

    return "/"


@lru_cache(maxsize=1)
def application_dirs() -> tuple[Path, ...]:
    if IS_MACOS:
        return (Path("/Applications"), Path.home() / "Applications")
    if IS_WINDOWS:
        roots = []
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(key)
            if value:
                roots.append(Path(value))
        return tuple(roots)
    return (Path("/usr/share/applications"),)


def installed_app_count() -> int:
    total = 0
    for directory in application_dirs():
        if not directory.is_dir():
            continue
        try:
            if IS_MACOS:
                total += sum(1 for _ in directory.glob("*.app"))
            else:
                total += sum(1 for entry in os.scandir(directory) if entry.is_dir())
        except OSError:
            continue
    return total


def uptime_text() -> str:
    try:
        seconds = time.time() - psutil.boot_time()
    except Exception:
        return "Bilinmiyor"

    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    if days:
        return f"{days}g {hours}s"
    if hours:
        return f"{hours}s {minutes}d"
    return f"{minutes}d"


def prime_cpu_sampling() -> None:
    psutil.cpu_percent(interval=None)


def get_system_info() -> dict:
    memory = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(data_volume())
        disk_total = disk.total / (1024 ** 3)
        disk_used = disk.used / (1024 ** 3)
        disk_free = disk.free / (1024 ** 3)
        disk_percent = disk.percent
    except OSError:
        disk_total = disk_used = disk_free = disk_percent = 0.0

    return {
        "os": os_name(),
        "hostname": platform.node(),
        "cpu_name": cpu_name(),
        "cpu_cores": psutil.cpu_count(logical=False) or 0,
        "cpu_threads": psutil.cpu_count(logical=True) or 0,
        "cpu_usage": psutil.cpu_percent(interval=None),
        "ram_total": memory.total / (1024 ** 3),
        "ram_used": memory.used / (1024 ** 3),
        "ram_percent": memory.percent,
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_free": disk_free,
        "disk_percent": disk_percent,
        "uptime": uptime_text(),
        "python": platform.python_version(),
    }
