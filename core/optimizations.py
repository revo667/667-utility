"""Windows performans ayarlari.

Her tweak'in bir geri alma karsiligi olmali. Geri alinamayan bir sey
uyguluyorsan, kart 'warning' veya 'danger' olarak isaretlenmeli.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core.platform_utils import IS_WINDOWS

#: `sc` ve `powercfg` cagrisi normalde aninda doner, ama servis durdurmak
#: bazen bloke olur. 5 saniye cok kisaydi, servisleri yarim birakiyordu.
_CMD_TIMEOUT = 30

#: Uzun surebilen betikler (bat dosyalari, appx kaldirma).
_SCRIPT_TIMEOUT = 120

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
REGS_PATH = _ASSETS / "regs"
BAT_PATH = _ASSETS / "bat"

#: Windows'ta her subprocess cagrisinda konsol penceresi acilmasin.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


def run_cmd(cmd: list[str], timeout: int = _CMD_TIMEOUT) -> subprocess.CompletedProcess | None:
    """Komutu calistirir. Basarisizlikta None doner - cagiran taraf kontrol etmeli."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        print(f"Timeout: {' '.join(cmd)}")
        return None
    except (OSError, FileNotFoundError) as exc:
        print(f"Calistirilamadi: {' '.join(cmd)} -> {exc}")
        return None


def _ok(result: subprocess.CompletedProcess | None) -> bool:
    """run_cmd None dondugunde patlamamak icin tek noktadan kontrol."""
    return result is not None and result.returncode == 0


def _powershell(script: str, timeout: int = _SCRIPT_TIMEOUT) -> bool:
    """PowerShell betigini TEK bir argüman olarak gecirir.

    Onemli: '|' gibi operatorleri ayri argv ogesi olarak vermek betigi bozar -
    PowerShell onlari komut degil, string parametresi olarak gorur.
    """
    result = run_cmd(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )
    return _ok(result)


def _set_services(names: list[str], *, enable: bool) -> bool:
    """Servis grubunu topluca ac/kapat. Hepsi basarisiz olursa False."""
    start_mode = "start=auto" if enable else "start=disabled"
    action = "start" if enable else "stop"
    any_success = False
    for svc in names:
        if _ok(run_cmd(["sc", action, svc])):
            any_success = True
        if _ok(run_cmd(["sc", "config", svc, start_mode])):
            any_success = True
    return any_success


TELEMETRY_SERVICES = ["DiagTrack", "dmwappushservice"]

XBOX_SERVICES = ["XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc"]

#: Oyun performansi icin kapatilabilecek servisler. Spooler = yazici,
#: TermService = uzak masaustu. Bunlari kullaniyorsan bu tweak'i uygulama.
REDUCIBLE_SERVICES = [
    "Fax", "TabletInputService", "WerSvc", "seclogon", "NetTcpPortSharing",
    "CDPSvc", "CDPUserSvc", "SharedAccess", "TermService", "SessionEnv",
    "wisvc", "WbioSrvc", "DusmSvc", "CscService", "UsoSvc", "Spooler",
    "SCardSvr", "MapsBroker", "RasSstp", "StorSvc",
]

_HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
_BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"


class Optimizations:
    # ---------------------------------------------------------------- SysMain
    @staticmethod
    def disable_sysmain() -> bool:
        stopped = _ok(run_cmd(["sc", "stop", "SysMain"]))
        configured = _ok(run_cmd(["sc", "config", "SysMain", "start=disabled"]))
        return stopped or configured

    @staticmethod
    def enable_sysmain() -> bool:
        configured = _ok(run_cmd(["sc", "config", "SysMain", "start=auto"]))
        started = _ok(run_cmd(["sc", "start", "SysMain"]))
        return configured or started

    # ------------------------------------------------------------- Guc plani
    @staticmethod
    def set_high_performance() -> bool:
        # Not: eskiden burada SysMain de kapatiliyordu - alakasiz bir yan etkiydi,
        # kaldirildi. Guc plani sadece guc planini degistirir.
        return _ok(run_cmd(["powercfg", "/setactive", _HIGH_PERFORMANCE_GUID]))

    @staticmethod
    def set_balanced_power() -> bool:
        return _ok(run_cmd(["powercfg", "/setactive", _BALANCED_GUID]))

    # ------------------------------------------------------------- Telemetri
    @staticmethod
    def disable_telemetry() -> bool:
        return _set_services(TELEMETRY_SERVICES, enable=False)

    @staticmethod
    def enable_telemetry() -> bool:
        return _set_services(TELEMETRY_SERVICES, enable=True)

    # ------------------------------------------------------- Gecici dosyalar
    @staticmethod
    def clear_temp() -> bool:
        """Gecici klasorleri bosaltir.

        Her hedef ayri bir `cmd /c` cagrisi - eskiden argumanlar tek string
        halinde birlestirildigi icin komutlarin bir kismi hic calismiyordu.
        """
        windir = os.environ.get("WINDIR", r"C:\Windows")
        targets = [
            os.environ.get("TEMP", ""),
            os.path.join(windir, "Temp"),
            os.path.join(windir, "SoftwareDistribution", "Download"),
            os.path.join(windir, "Prefetch"),
        ]

        cleaned_any = False
        for target in targets:
            if not target:
                continue
            # /q sessiz, /f salt-okunuru zorla, /s alt klasorler dahil
            if run_cmd(["cmd", "/c", "del", "/q", "/f", "/s", os.path.join(target, "*")]) is not None:
                cleaned_any = True

        run_cmd(["cleanmgr", "/sagerun:1"], timeout=_SCRIPT_TIMEOUT)
        return cleaned_any

    # ------------------------------------------------------ Arama indeksleme
    @staticmethod
    def disable_search_index() -> bool:
        stopped = _ok(run_cmd(["sc", "stop", "WSearch"]))
        configured = _ok(run_cmd(["sc", "config", "WSearch", "start=disabled"]))
        return stopped or configured

    @staticmethod
    def enable_search_index() -> bool:
        configured = _ok(run_cmd(["sc", "config", "WSearch", "start=auto"]))
        started = _ok(run_cmd(["sc", "start", "WSearch"]))
        return configured or started

    # ------------------------------------------------------------------ Xbox
    @staticmethod
    def disable_xbox_services() -> bool:
        _set_services(XBOX_SERVICES, enable=False)
        # Tek string olarak gecmek sart - '|' ayri argv ogesi olursa pipe calismaz.
        _powershell(
            "Get-AppxPackage *Microsoft.GamingServices* | "
            "Remove-AppxPackage -ErrorAction SilentlyContinue"
        )
        _powershell(
            "Get-AppxPackage *Microsoft.XboxGamingOverlay* | "
            "Remove-AppxPackage -ErrorAction SilentlyContinue"
        )
        return True

    @staticmethod
    def enable_xbox_services() -> bool:
        _set_services(XBOX_SERVICES, enable=True)
        # Kaldirilan Xbox uygulamalari Store uzerinden geri kurulur.
        run_cmd(["cmd", "/c", "start", "ms-windows-store://pdp/?productid=9MWPM2CQNLHN"])
        return True

    # -------------------------------------------------------- Servis azaltma
    @staticmethod
    def reduce_services() -> bool:
        return _set_services(REDUCIBLE_SERVICES, enable=False)

    @staticmethod
    def restore_services() -> bool:
        return _set_services(REDUCIBLE_SERVICES, enable=True)

    # ------------------------------------------------------- Registry tweaks
    @staticmethod
    def apply_all_reg() -> bool:
        """assets/regs altindaki tum .reg dosyalarini uygular."""
        if not REGS_PATH.is_dir():
            print(f"Reg klasoru bulunamadi: {REGS_PATH}")
            return False

        files = sorted(REGS_PATH.glob("*.reg"))
        if not files:
            print("Uygulanacak .reg dosyasi yok.")
            return False

        applied = 0
        for path in files:
            # regedit /s hata kodu dondurmez; reg import daha durust.
            result = run_cmd(["reg", "import", str(path)])
            if _ok(result):
                applied += 1
            else:
                print(f"Uygulanamadi: {path.name}")

        # Eskiden bu fonksiyon hicbir sey dondurmuyordu (None = basarisiz gorunuyordu).
        return applied > 0

    # ------------------------------------------------------------ Input lag
    @staticmethod
    def lower_input_delay() -> bool:
        """assets/bat/Lower_Input_Delay.bat calistirir.

        Dosya adi buyuk-kucuk harf duyarli sistemlerde de bulunsun diye
        glob ile araniyor - eskiden sabit kucuk harfle aranıyordu.
        """
        if not BAT_PATH.is_dir():
            return False

        matches = [p for p in BAT_PATH.glob("*.bat") if p.stem.lower() == "lower_input_delay"]
        if not matches:
            print("Lower_Input_Delay.bat bulunamadi.")
            return False

        result = run_cmd(["cmd", "/c", str(matches[0])], timeout=_SCRIPT_TIMEOUT)
        if result is None:
            return False

        # Betik basarili oldugunda %TEMP% altina bir log birakiyor.
        log_path = Path(os.environ.get("TEMP", "")) / "lower_input_delay.log"
        if log_path.is_file():
            try:
                log_path.unlink()
            except OSError:
                pass
            return True

        return result.returncode == 0

    # ------------------------------------------------------ Arka plan uygl.
    @staticmethod
    def disable_background_apps() -> bool:
        ok = _powershell(
            "Get-AppxPackage | Where-Object { $_.IsFramework -eq $false } | ForEach-Object { "
            "Set-ItemProperty -Path "
            "\"HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\BackgroundAccessApplications\\$($_.PackageFamilyName)\" "
            "-Name 'Disabled' -Value 1 -Force -ErrorAction SilentlyContinue }"
        )
        _ok(run_cmd([
            "reg", "add",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            "/v", "GlobalUserDisabled", "/t", "REG_DWORD", "/d", "1", "/f",
        ]))
        _ok(run_cmd([
            "reg", "add",
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy",
            "/v", "LetAppsRunInBackground", "/t", "REG_DWORD", "/d", "2", "/f",
        ]))
        return ok

    @staticmethod
    def enable_background_apps() -> bool:
        run_cmd([
            "reg", "delete",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            "/v", "GlobalUserDisabled", "/f",
        ])
        run_cmd([
            "reg", "delete",
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy",
            "/v", "LetAppsRunInBackground", "/f",
        ])
        return True
