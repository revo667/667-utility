import ctypes
import sys
import warnings
from src.ui.app import run_app
from core.setup import install_font

install_font()

warnings.filterwarnings("ignore", category=RuntimeWarning)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:

        return False

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{sys.argv[0]}"', None, 1
        )
        sys.exit()
    else:
        run_app()