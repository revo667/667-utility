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


def fetch_account(token: str) -> Optional[dict]:
    """Jetonu dogrular. Gecerliyse hesap bilgisini, degilse None doner."""
    if not token:
        return None

    request = urllib.request.Request(
        f"{ACCOUNT_ORIGIN}/api/account/me",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            clear_token()
        return None
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


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


def current_account() -> Optional[dict]:
    """Diskteki jetonla hesabi dogrular. Girissizse None."""
    return fetch_account(load_token())
