import subprocess
from typing import Tuple

def install_by_winget_id(winget_id: str) -> Tuple[int, str]:
    """
    Run winget install and return (exit_code, combined_output).
    exit_code == 0 means success; otherwise failure.
    """
    cmd = [
        "winget", "install", "--id", winget_id, "-e",
        "--accept-package-agreements", "--accept-source-agreements"
    ]
    try:
        res = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True
        )
        out = ""
        if res.stdout:
            out += res.stdout
        if res.stderr:
            out += ("\n[stderr]\n" + res.stderr)
        return res.returncode, out or f"winget exited with code {res.returncode}"
    except FileNotFoundError:
        return -1, "Error: winget not found on PATH (FileNotFoundError)"
    except Exception as e:
        return -2, f"Unexpected exception: {e}"