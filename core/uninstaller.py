import re
import shlex
import subprocess

from core.platform_utils import IS_WINDOWS

if IS_WINDOWS:
    import winreg
else:
    winreg = None

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0

_MSI_GUID_RE = re.compile(r"\{[A-F0-9\-]+\}", re.IGNORECASE)


def run_cmd(cmd: list, timeout: int = 30):
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
        print(f"Timeout: {cmd}")
        return None
    except (OSError, FileNotFoundError) as exc:
        print(f"Calistirilamadi: {cmd} -> {exc}")
        return None

def get_installed_programs() -> list[dict]:
    if winreg is None:
        print("This feature is only available on Windows.")
        return []
    programs = []
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, path in keys:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    try:
                        uninstall_str = winreg.QueryValueEx(subkey, "UninstallString")[0]
                    except OSError:
                        uninstall_str = ""
                    if name and name.strip():
                        programs.append({
                            "name": name.strip(),
                            "uninstall_str": uninstall_str
                        })
                except OSError:
                    continue
        except OSError:
            continue

    seen = set()
    unique = []
    for p in programs:
        if p["name"] not in seen:
            seen.add(p["name"])
            unique.append(p)

    return sorted(unique, key=lambda x: x["name"].lower())

def uninstall_program(uninstall_str: str) -> bool:
    if not IS_WINDOWS:
        print("This feature is only available on Windows.")
        return False
    if not uninstall_str:
        return False
    try:
        if "msiexec" in uninstall_str.lower():
            match = _MSI_GUID_RE.search(uninstall_str)
            if match:
                result = run_cmd(["msiexec", "/x", match.group(), "/qn", "/norestart"])
            else:
                result = run_cmd(
                    ["msiexec", "/x", uninstall_str.split()[-1], "/qn", "/norestart"]
                )
        else:
            result = run_cmd(shlex.split(uninstall_str))

        return result.returncode == 0 if result else False
    except (OSError, ValueError) as exc:
        print(f"Uninstall error: {exc}")
        return False

BLOATWARE = [
    "Microsoft.BingNews",
    "Microsoft.BingWeather",
    "Microsoft.GetHelp",
    "Microsoft.Getstarted",
    "Microsoft.MicrosoftOfficeHub",
    "Microsoft.MicrosoftSolitaireCollection",
    "Microsoft.People",
    "Microsoft.PowerAutomateDesktop",
    "Microsoft.Todos",
    "Microsoft.WindowsAlarms",
    "Microsoft.WindowsCamera",
    "Microsoft.WindowsFeedbackHub",
    "Microsoft.WindowsMaps",
    "Microsoft.WindowsSoundRecorder",
    "Microsoft.Xbox.TCUI",
    "Microsoft.XboxApp",
    "Microsoft.XboxGameOverlay",
    "Microsoft.XboxGamingOverlay",
    "Microsoft.XboxIdentityProvider",
    "Microsoft.XboxSpeechToTextOverlay",
    "Microsoft.YourPhone",
    "Microsoft.ZuneMusic",
    "Microsoft.ZuneVideo",
    "MicrosoftTeams",
]

def remove_bloatware(remove_edge: bool = False) -> bool:
    """Onceden tanimli UWP bloatware paketlerini kaldirir.

    remove_edge varsayilan olarak False: Edge'i kaldirmak Windows Update ve
    bazi sistem bilesenlerini bozabiliyor, bu yuzden artik opt-in.
    """
    if not IS_WINDOWS:
        print("This feature is only available on Windows.")
        return False

    removed = 0
    for app in BLOATWARE:
        result = run_cmd([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            f"Get-AppxPackage *{app}* | Remove-AppxPackage -ErrorAction SilentlyContinue",
        ], timeout=60)
        if result is not None and result.returncode == 0:
            removed += 1

    if remove_edge:
        run_cmd([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            r"Get-ChildItem 'C:\Program Files (x86)\Microsoft\Edge\Application\*\Installer' | "
            r"ForEach-Object { Start-Process -FilePath (Join-Path $_.FullName 'setup.exe') "
            r"-ArgumentList '--uninstall --system-level --verbose-logging --force-uninstall' -Wait }",
        ], timeout=300)

    return removed > 0
