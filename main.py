from __future__ import annotations

import sys
import warnings

from core.platform_utils import IS_WINDOWS

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


def selftest() -> int:
    import json

    from core.resources import (
        APPS_JSON,
        ASSETS_DIR,
        BAT_DIR,
        REGS_DIR,
        base_path,
        is_frozen,
    )

    problems: list[str] = []
    print(f"paketlenmis : {is_frozen()}")
    print(f"taban yol   : {base_path()}")

    if not ASSETS_DIR.is_dir():
        problems.append(f"assets klasoru yok: {ASSETS_DIR}")
    else:
        fonts = list(ASSETS_DIR.glob("*.ttf"))
        regs = list(REGS_DIR.glob("*.reg")) if REGS_DIR.is_dir() else []
        bats = list(BAT_DIR.glob("*.bat")) if BAT_DIR.is_dir() else []
        print(f"font        : {len(fonts)}")
        print(f"reg dosyasi : {len(regs)}")
        print(f"bat dosyasi : {len(bats)}")
        if not fonts:
            problems.append("paketli font bulunamadi")
        if not regs:
            problems.append("assets/regs bos veya yok")

    try:
        categories = json.loads(APPS_JSON.read_text(encoding="utf-8"))
        print(f"apps.json   : {len(categories)} kategori")
    except (OSError, ValueError) as exc:
        problems.append(f"apps.json okunamadi: {exc}")

    try:
        from PySide6.QtWidgets import QApplication

        from src.ui.pages import available_pages
        from src.ui.style import get_stylesheet
        from src.ui.workers import stop_all_threads

        app = QApplication.instance() or QApplication([])
        get_stylesheet()
        specs = available_pages()

        widgets = []
        for spec in specs:
            try:
                widgets.append(spec.factory())
            except Exception as exc:
                problems.append(f"sayfa kurulamadi ({spec.key}): {exc}")
        print(f"sayfa       : {len(widgets)}/{len(specs)}")


        app.processEvents()
        for widget in widgets:
            stop_all_threads(widget)
            widget.deleteLater()
        app.processEvents()
        widgets.clear()
        del app
    except Exception as exc:
        problems.append(f"Qt katmani baslatilamadi: {exc}")

    if problems:
        print("\nBASARISIZ:")
        for item in problems:
            print(f"  - {item}")
        return 1

    print("\nSELFTEST GECTI")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    if not is_admin():
        if relaunch_as_admin():
            return 0
        print("Yonetici hakki alinamadi - sinirli modda devam ediliyor.")

    from src.ui.app import run_app
    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
