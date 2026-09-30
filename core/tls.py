
from __future__ import annotations

import os
import ssl
import subprocess
import sys
from pathlib import Path

_fallback_ctx: ssl.SSLContext | None = None


def _cache_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return root / "667utility"


def _macos_root_bundle() -> str | None:
    """macOS sistem koklerini PEM olarak disa aktarir ve onbellekler."""
    path = _cache_dir() / "system-roots.pem"

    try:
        if path.exists() and path.stat().st_size > 4096:
            return str(path)

        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-certificate",
                "-a",
                "-p",
                "/System/Library/Keychains/SystemRootCertificates.keychain",
            ],
            capture_output=True,
            text=True,
            timeout=25,
        )

        if result.returncode != 0 or "BEGIN CERTIFICATE" not in result.stdout:
            return None

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.stdout, encoding="utf-8")

        return str(path)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _build_fallback_context() -> ssl.SSLContext | None:
    context = ssl.create_default_context()

    try:
        import certifi

        context.load_verify_locations(certifi.where())
        return context
    except Exception:
        pass

    if sys.platform == "darwin":
        bundle = _macos_root_bundle()

        if bundle:
            try:
                context.load_verify_locations(bundle)
                return context
            except (ssl.SSLError, OSError):
                return None

    return None


def trust_context() -> ssl.SSLContext | None:
    """Sistem koklerini yukleyen yedek SSL baglami.

    Python'un kendi sertifika deposu bos gelebiliyor (macOS'ta "Install
    Certificates" calistirilmamis kurulumlar, paketlenmis yapilar). Bu
    durumda dogrulamayi kapatmak yerine isletim sisteminin koklerini
    yukluyoruz. Bulunamazsa None doner - cagiran varsayilanla devam eder.
    """
    global _fallback_ctx

    if _fallback_ctx is None:
        _fallback_ctx = _build_fallback_context()

    return _fallback_ctx
