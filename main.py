"""667 Utility giris noktasi.

Windows'ta bazi tweak'ler yonetici hakki ister; uygulama kendini yukseltilmis
olarak yeniden baslatir. Diger platformlarda boyle bir adim yok.
"""

from __future__ import annotations

import sys
import warnings

from core.platform_utils import IS_WINDOWS

# PySide6'nin bazi surumleri kapanista zararsiz RuntimeWarning basiyor.
warnings.filterwarnings("ignore", category=RuntimeWarning)


def is_admin() -> bool:
    if not IS_WINDOWS:
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin() -> bool:
    """UAC istemi gosterir. Kullanici reddederse False doner."""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{sys.argv[0]}"', None, 1
        )
        # ShellExecuteW 32'den buyuk deger dondurunce basarili sayilir.
        return int(result) > 32
    except (AttributeError, OSError):
        return False


def main() -> int:
    if not is_admin():
        if relaunch_as_admin():
            return 0
        print("Yonetici hakki alinamadi - sinirli modda devam ediliyor.")

    from src.ui.app import run_app
    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
