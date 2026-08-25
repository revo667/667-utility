import shutil
import subprocess


def install_by_winget_id(winget_id: str) -> tuple[int, str]:
    if not shutil.which("winget"):
        return -1, "winget not found on PATH."

    cmd = [
        "winget", "install", "--id", winget_id, "-e",
        "--accept-package-agreements", "--accept-source-agreements",
        "--silent"
    ]

    try:
        res = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = res.stdout or ""
        if res.stderr:
            out += f"\n[stderr]\n{res.stderr}"
        return res.returncode, out or f"Exited with code {res.returncode}"
    except FileNotFoundError:
        return -2, "winget not found."
    except Exception as e:
        return -4, f"Unexpected error: {e}"


def install_multiple(winget_ids: list[str]) -> list[tuple[str, int, str]]:
    results = []
    for winget_id in winget_ids:
        code, out = install_by_winget_id(winget_id)
        results.append((winget_id, code, out))
    return results
