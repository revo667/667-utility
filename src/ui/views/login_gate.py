"""Giris kapisi - uygulama acilmadan once revo667 hesabi ister."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core import account


class VerifyThread(QThread):
    """Jetonu dogrular. Ag isi arayuzu kilitlemesin."""

    done = Signal(object, str)

    def __init__(self, parent=None, token: str = "") -> None:
        super().__init__(parent)
        self.token = token

    def run(self) -> None:
        found, detail = account.verify(self.token or account.load_token())
        self.done.emit(found, detail)


class LoginGate(QDialog):
    def __init__(self) -> None:
        super().__init__()

        self.account: Optional[dict] = None
        self.flow: Optional[account.SignInFlow] = None

        self.setWindowTitle("667 Utility")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

        self.title = QLabel("revo667 hesabi")
        self.title.setStyleSheet("font-size:18px;font-weight:600;")

        self.status = QLabel("Oturum kontrol ediliyor...")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.setStyleSheet("color:rgba(255,255,255,0.55);")

        self.sign_in = QPushButton("revo667.com ile giris yap")
        self.sign_in.clicked.connect(self.start_sign_in)
        self.sign_in.setVisible(False)

        self.quit = QPushButton("Cik")
        self.quit.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.quit)
        buttons.addWidget(self.sign_in)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addLayout(buttons)

        self.poll = QTimer(self)
        self.poll.setInterval(400)
        self.poll.timeout.connect(self.check_flow)

        self.verifier = VerifyThread(self)
        self.verifier.done.connect(self.on_verified)

        QTimer.singleShot(0, self.verifier.start)

    def on_verified(self, result: object, detail: str) -> None:
        if isinstance(result, dict):
            self.account = result
            self.accept()
            return

        note = "" if detail in ("", "jeton yok") else f"\n\n({detail})"

        self.status.setText(
            "Universe, trading journal ve 667 Utility ayni hesabi kullanir.\n"
            "Giris tarayicida tamamlanir." + note
        )
        self.sign_in.setVisible(True)
        self.adjustSize()

    def start_sign_in(self) -> None:
        self.sign_in.setEnabled(False)
        self.status.setText("Tarayici acildi - onayladiktan sonra buraya donun.")

        self.flow = account.SignInFlow()

        if not self.flow.start():
            self.fail(self.flow.error or "giris baslatilamadi")
            return

        self.poll.start()

    def check_flow(self) -> None:
        if self.flow is None or not self.flow.finished():
            return

        self.poll.stop()

        if not self.flow.token:
            self.fail(self.flow.error or "giris tamamlanmadi")
            return

        account.save_token(self.flow.token)
        self.status.setText("Dogrulaniyor...")

        self.verifier = VerifyThread(self, self.flow.token)
        self.verifier.done.connect(self.on_signed_in)
        self.verifier.start()

    def on_signed_in(self, result: object, detail: str) -> None:
        if isinstance(result, dict):
            self.account = result
            self.accept()
            return

        self.fail(detail or "hesap dogrulanamadi")

    def fail(self, message: str) -> None:
        account.record(message)

        self.status.setText(
            f"Giris basarisiz.\n{message}\n\nAyrinti: {account.log_path()}"
        )
        self.adjustSize()
        self.sign_in.setEnabled(True)
        self.sign_in.setText("Tekrar dene")

    def reject(self) -> None:
        if self.flow is not None:
            self.flow.cancel()

        super().reject()


def require_account() -> Optional[dict]:
    """Girisi zorunlu kilar. Kullanici vazgecerse None doner."""
    gate = LoginGate()

    return gate.account if gate.exec() == QDialog.DialogCode.Accepted else None
