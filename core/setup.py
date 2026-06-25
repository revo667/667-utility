import os
import shutil
import sys


def install_font():
    font_src = os.path.join(
        os.path.dirname(__file__), "assets", "JetBrainsMonoNerdFont-Bold.ttf"
    )

    if not os.path.exists(font_src):
        print("Font file not found in assets/")
        return False

    fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    font_dst = os.path.join(fonts_dir, "JetBrainsMonoNerdFont-Bold.ttf")

    if os.path.exists(font_dst):
        print("Font already installed.")
        return True

    try:
        shutil.copy2(font_src, font_dst)

        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(
            key,
            "JetBrainsMono Nerd Font (TrueType)",
            0,
            winreg.REG_SZ,
            "JetBrainsMonoNerdFont-Bold.ttf",
        )
        winreg.CloseKey(key)

        print("Font installed successfully.")
        return True

    except Exception as e:
        print(f"Font install failed: {e}")
        return False


if __name__ == "__main__":
    install_font()
