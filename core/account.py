"""revo667 hesabi - tum ekosistem icin tek kimlik.

Universe ile ayni akis: tarayicida revo667.com acilir, kullanici onaylar,
site cihaz jetonunu 127.0.0.1 uzerindeki gecici sunucuya birakir. Jeton
kullanici klasorune yazilir, sonraki aciliuslarda giris istenmez.

Sadece standart kutuphane kullanilir - yeni bagimlilik yok.
"""

from __future__ import annotations

import http.server
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

ACCOUNT_ORIGIN = os.environ.get("REVO667_ACCOUNT_ORIGIN", "https://www.revo667.com")
APP_LABEL = "667 Utility"
CALLBACK_PORT = 8901
CALLBACK_URL = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
TIMEOUT_SECONDS = 240

_PAGE_OK = """<!doctype html><meta charset="utf-8">
<title>667 Utility</title>
<body style="background:#0a080e;color:#a78bc4;font-family:system-ui;display:flex;
height:100vh;margin:0;align-items:center;justify-content:center">
<h2>Giris tamam - uygulamaya donebilirsiniz.</h2></body>"""

_PAGE_FAIL = """<!doctype html><meta charset="utf-8">
<title>667 Utility</title>
<body style="background:#0a080e;color:#d16a8f;font-family:system-ui;display:flex;
height:100vh;margin:0;align-items:center;justify-content:center">
<h2>Giris dogrulanamadi.</h2></body>"""


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return root / "667utility"


def token_path() -> Path:
    return config_dir() / "account.json"


def load_token() -> str:
    try:
        data = json.loads(token_path().read_text(encoding="utf-8"))
        return str(data.get("token") or "")
    except (OSError, ValueError):
        return ""


def save_token(token: str) -> None:
    path = token_path()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"token": token}), encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_token() -> None:
    try:
        token_path().unlink()
    except OSError:
        pass


# --- TLS kok sertifikalari -------------------------------------------------
# Python macOS anahtar zincirini kullanmaz; kendi CA paketini bekler. Python.org
# kurulumunda "Install Certificates.command" bunu yapar, ama paketlenmis (.app)
# bir uygulamada veya farkli bir kurulumda paket eksik olur ve her HTTPS istegi
# CERTIFICATE_VERIFY_FAILED ile duser. Once varsayilani deneriz; sadece
# dogrulama patlarsa isletim sisteminin kendi koklerine duseriz.

_fallback_ctx: Optional[ssl.SSLContext] = None
DIAGNOSTICS: list[str] = []


def _macos_root_bundle() -> Optional[str]:
    """macOS sistem koklerini PEM olarak disa aktarir ve onbellekler."""
    path = config_dir() / "system-roots.pem"

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


def _build_fallback_context() -> Optional[ssl.SSLContext]:
    context = ssl.create_default_context()

    try:
        import certifi

        context.load_verify_locations(certifi.where())
        DIAGNOSTICS.append("certifi bulundu")
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


def _curl_get(url: str, token: str, timeout: int = 20) -> str:
    """Son care: macOS'un kendi curl'u. Sistem guven deposunu kullanir, yani
    Safari calisiyorsa bu da calisir. Jeton argv'ye degil stdin'e verilir ki
    `ps` ciktisinda gorunmesin."""
    config = f'url = "{url}"\nheader = "Authorization: Bearer {token}"\nheader = "Accept: application/json"\nsilent\nshow-error\nfail\n'

    result = subprocess.run(
        ["/usr/bin/curl", "--config", "-"],
        input=config,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise OSError(f"curl {result.returncode}: {result.stderr.strip()[:120]}")

    return result.stdout


def _open(request: urllib.request.Request, timeout: int = 12) -> str:
    """Istegi gonderir. Sertifika dogrulamasi patlarsa once OS koklerine,
    sonra sistem curl'une duser. Hangi katmanin patladigi kaydedilir."""
    global _fallback_ctx

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_fallback_ctx) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as error:
        verify_failed = isinstance(error.reason, ssl.SSLCertVerificationError) or (
            "CERTIFICATE_VERIFY_FAILED" in str(error.reason)
        )

        if not verify_failed:
            raise

        if _fallback_ctx is None:
            context = _build_fallback_context()

            if context is not None:
                _fallback_ctx = context
                DIAGNOSTICS.append("os-kokleri yuklendi")

                try:
                    with urllib.request.urlopen(
                        request, timeout=timeout, context=_fallback_ctx
                    ) as response:
                        return response.read().decode("utf-8")
                except urllib.error.URLError as retry_error:
                    DIAGNOSTICS.append(f"os-kokleri de yetmedi ({retry_error.reason})")
            else:
                DIAGNOSTICS.append("os-kokleri alinamadi")

        if sys.platform == "darwin":
            try:
                body = _curl_get(request.full_url, request.headers.get("Authorization", "").removeprefix("Bearer "))
                DIAGNOSTICS.append("sistem curl kullanildi")
                return body
            except (OSError, subprocess.SubprocessError) as curl_error:
                DIAGNOSTICS.append(f"curl da patladi ({curl_error})")

        raise


# Yeni ad once denenir; site henuz guncellenmediyse eski yol calisir.
ME_PATHS = ("/api/account/me", "/api/universe/me")


def _probe(path: str, token: str) -> tuple[Optional[dict], str]:
    """Tek bir uc noktayi dener. (hesap, hata_aciklamasi) doner."""
    request = urllib.request.Request(
        f"{ACCOUNT_ORIGIN}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )

    try:
        data = json.loads(_open(request))

        if isinstance(data, dict) and data.get("id"):
            return data, ""

        return None, f"{path}: beklenmeyen yanit"
    except urllib.error.HTTPError as error:
        return None, f"{path}: sunucu {error.code}"
    except urllib.error.URLError as error:
        return None, f"{path}: baglanti yok ({error.reason})"
    except ssl.SSLError as error:
        return None, f"{path}: TLS hatasi ({error})"
    except ValueError:
        return None, f"{path}: yanit JSON degil (muhtemelen sayfa dondu)"
    except (OSError, TimeoutError) as error:
        return None, f"{path}: {error}"


def verify(token: str) -> tuple[Optional[dict], str]:
    """Jetonu dogrular. Basarisizsa NEDEN basarisiz oldugunu da soyler."""
    if not token:
        return None, "jeton yok"

    problems = []
    unauthorized = False

    for path in ME_PATHS:
        account, detail = _probe(path, token)

        if account:
            return account, ""

        if detail.endswith("401"):
            unauthorized = True

        problems.append(detail)

    if unauthorized:
        clear_token()

    if DIAGNOSTICS:
        problems.append("adimlar: " + ", ".join(DIAGNOSTICS[-4:]))

    return None, " / ".join(problems)


def fetch_account(token: str) -> Optional[dict]:
    """Geriye donuk uyumluluk icin sade surum."""
    return verify(token)[0]


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


class SignInFlow:
    """Tarayici tabanli giris. start() cagrilir, sonra result() ile beklenir."""

    def __init__(self) -> None:
        self.nonce = secrets.token_hex(16)
        self.token = ""
        self.error = ""
        self._done = threading.Event()
        self._server: Optional[http.server.HTTPServer] = None

    def _handler(self):
        flow = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_GET(self):
                parsed = urlparse(self.path)

                if parsed.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return

                params = parse_qs(parsed.query)
                token = (params.get("token") or [""])[0]
                state = (params.get("state") or [""])[0]
                ok = bool(token) and secrets.compare_digest(state, flow.nonce)

                body = (_PAGE_OK if ok else _PAGE_FAIL).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

                if ok:
                    flow.token = token
                else:
                    flow.error = "giris dogrulanamadi"

                flow._done.set()

        return Handler

    def start(self) -> bool:
        if not port_free(CALLBACK_PORT):
            self.error = f"127.0.0.1:{CALLBACK_PORT} kullanimda"
            self._done.set()
            return False

        try:
            self._server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), self._handler())
        except OSError as exc:
            self.error = str(exc)
            self._done.set()
            return False

        threading.Thread(target=self._serve, daemon=True).start()

        query = urlencode({"redirect": CALLBACK_URL, "state": self.nonce, "app": APP_LABEL})
        webbrowser.open(f"{ACCOUNT_ORIGIN}/universe/auth?{query}")

        return True

    def _serve(self) -> None:
        server = self._server

        if server is None:
            return

        server.timeout = 1
        waited = 0

        while not self._done.is_set() and waited < TIMEOUT_SECONDS:
            server.handle_request()
            waited += 1

        if not self._done.is_set():
            self.error = "sure doldu"
            self._done.set()

        try:
            server.server_close()
        except OSError:
            pass

    def finished(self) -> bool:
        return self._done.is_set()

    def cancel(self) -> None:
        self._done.set()


def log_path() -> Path:
    return config_dir() / "last-error.txt"


def record(detail: str) -> None:
    """Hatayi hem diske hem stdout'a yazar - diyalog metni kesilse bile kaybolmasin."""
    if not detail:
        return

    print(f"[667utility/account] {detail}", flush=True)

    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(detail, encoding="utf-8")
    except OSError:
        pass


def current_account() -> tuple[Optional[dict], str]:
    """Diskteki jetonla hesabi dogrular. (hesap, hata) doner."""
    found, detail = verify(load_token())

    record(detail)

    return found, detail
