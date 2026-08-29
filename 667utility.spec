import re
import sys
from pathlib import Path

APP_NAME = "667 Utility"
BUNDLE_ID = "com.revo667.utility"

ROOT = Path(SPECPATH)
ASSETS = ROOT / "assets"


def read_version():

    text = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "0.0.0"


VERSION = read_version()

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


def icon_for_platform():
    candidate = ASSETS / ("icon.icns" if IS_MAC else "icon.ico" if IS_WIN else "icon.png")
    return str(candidate) if candidate.is_file() else None



datas = [
    (str(ASSETS), "assets"),
    (str(ROOT / "src" / "apps.json"), "src"),
]


hiddenimports = [
    "src.ui.views.dashboard",
    "src.ui.views.installer",
    "src.ui.views.uninstaller",
    "src.ui.views.optimizer",
    "src.ui.views.mac_cleaner",
    "src.ui.views.mac_installer",
    "src.ui.views.mac_uninstaller",
    "src.ui.views.mac_snapshots",
    "src.ui.views.settings",
]


excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtQuick3D",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtTest",
    "tkinter", "matplotlib", "numpy", "PIL", "pytest",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME if IS_MAC else "667Utility",
    debug=False,
    strip=False,
    upx=False,              # UPX antivirus yanlis pozitifi uretiyor, kapali
    console=False,          # GUI uygulamasi: konsol penceresi acilmasin
    icon=icon_for_platform(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="667Utility",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier=BUNDLE_ID,
        icon=icon_for_platform(),
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "NSDesktopFolderUsageDescription":
                "Temizlik taramasi icin Masaustu klasorunu okumasi gerekiyor.",
            "NSDocumentsFolderUsageDescription":
                "Temizlik taramasi icin Belgeler klasorunu okumasi gerekiyor.",
            "NSDownloadsFolderUsageDescription":
                "Temizlik taramasi icin Indirilenler klasorunu okumasi gerekiyor.",
            "NSAppleEventsUsageDescription":
                "Uygulamalari cop kutusuna tasimak icin Finder'i kullanir.",
            "LSMinimumSystemVersion": "11.0",
        },
    )
