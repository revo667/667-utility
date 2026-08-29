"""Ayarlar sayfasindaki guncelleme karti.

Universe'teki panelin karsiligi: surum bilgisi, durum satiri, ilerleme
cubugu ve uc dugme (ara / indir-kur / yayinlar).

Ag isleri QThread'de: kontrol ve indirme arayuzu kilitlemez. Her iki thread
de bu karta parent olarak bagli - workers.stop_all_threads() kapanista
onlari da topluyor (bkz. src/ui/workers.py).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from core import updater
from core.platform_utils import human_size
from src.ui.settings_store import settings
from src.ui.style import repolish
from src.ui.theme import Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton

#: Acilistaki sessiz kontrol icin gecikme. Uygulama once acilsin, sonra ag.
STARTUP_DELAY_MS = 4000


class CheckThread(QThread):
    """Yeni surum var mi diye bakar."""

    done = Signal(object, str, bool)  # release | None, mesaj, hata mi

    def __init__(self, parent=None, channel: str = "stable") -> None:
        super().__init__(parent)
        self.channel = channel

    def run(self) -> None:
        try:
            result = updater.check(self.channel)
        except updater.UpdateError as exc:
            self.done.emit(None, str(exc), True)
            return
        except Exception as exc:  # beklenmeyen: yine de arayuze tasi
            self.done.emit(None, f"beklenmeyen hata ({exc})", True)
            return

        self.done.emit(result.release, result.message, False)


class InstallThread(QThread):
    """Indirir ve kurulum betigini baslatir.

    Betik calismaya basladiginda 'ready' gelir; uygulamayi kapatmak
    cagiranin isi - kapanmazsa betik dosyalari degistiremez.
    """

    progress = Signal(int)
    ready = Signal()
    failed = Signal(str)

    def __init__(self, parent=None, release: updater.Release | None = None) -> None:
        super().__init__(parent)
        self.release = release

    def run(self) -> None:
        if self.release is None:
            self.failed.emit("indirilecek surum yok")
            return

        try:
            directory, archive = updater.download(
                self.release,
                on_progress=self.progress.emit,
                should_cancel=self.isInterruptionRequested,
            )
            updater.install(self.release, Path(archive), Path(directory))
        except updater.UpdateError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"beklenmeyen hata ({exc})")
            return

        self.ready.emit()


class UpdateCard(QFrame):
    """Guncelleme durumunu gosteren ve islemleri baslatan kart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        self._release: updater.Release | None = None
        self._checker: CheckThread | None = None
        self._installer: InstallThread | None = None
        self._silent = True

        self._build_ui()
        self._set_status("henuz denetlenmedi", "muted")

        if settings.get("update_check_on_start") and updater.is_frozen():
            QTimer.singleShot(STARTUP_DELAY_MS, self.check_silently)

    # ------------------------------------------------------------- arayuz
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        title = QLabel("Guncelleme")
        title.setObjectName("ItemTitle")

        self.version_label = QLabel(f"667 Utility {updater.current_label()}")
        self.version_label.setObjectName("ItemMeta")
        self.version_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.status_label = QLabel()
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.check_button = ModernButton("Guncelleme Ara", "ghost", "refresh")
        self.check_button.clicked.connect(self.check_now)

        self.install_button = ModernButton("Indir ve Kur", "primary", "check")
        self.install_button.clicked.connect(self.install_now)
        self.install_button.setVisible(False)

        self.releases_button = ModernButton("Yayinlar", "subtle")
        self.releases_button.clicked.connect(lambda: updater.open_releases())

        buttons = QHBoxLayout()
        buttons.setSpacing(Spacing.SM)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.install_button)
        buttons.addStretch(1)
        buttons.addWidget(self.releases_button)

        layout.addWidget(title)
        layout.addWidget(self.version_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)

    def _set_status(self, message: str, tone: str = "muted") -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("tone", tone)
        repolish(self.status_label)

    def _busy(self) -> bool:
        for worker in (self._checker, self._installer):
            if worker is not None and worker.isRunning():
                return True
        return False

    # ------------------------------------------------------------ kontrol
    @Slot()
    def check_now(self) -> None:
        self._start_check(silent=False)

    @Slot()
    def check_silently(self) -> None:
        self._start_check(silent=True)

    def _start_check(self, silent: bool) -> None:
        if self._busy():
            return

        if not updater.is_frozen():
            self._set_status("gelistirme surumu - guncelleme kapali", "muted")
            return

        self._silent = silent
        self.check_button.setEnabled(False)
        self.check_button.setText("Araniyor...")
        self._set_status("yayinlar denetleniyor...", "warning")

        # Her seferinde yeni thread: bitmis bir QThread yeniden baslatilabilir
        # ama parent'a bagli kalmasi icin ayni degiskene atiyoruz.
        self._checker = CheckThread(self, str(settings.get("update_channel")))
        self._checker.done.connect(self._on_checked)
        self._checker.start()

    @Slot(object, str, bool)
    def _on_checked(self, release: object, message: str, failed: bool) -> None:
        self.check_button.setEnabled(True)
        self.check_button.setText("Guncelleme Ara")

        if failed:
            self._release = None
            self.install_button.setVisible(False)
            self._set_status(f"hata · {message}", "danger")
            if not self._silent:
                notify(self, f"Guncelleme denetlenemedi: {message}", "warning")
            return

        if not isinstance(release, updater.Release):
            self._release = None
            self.install_button.setVisible(False)
            self._set_status(message, "muted")
            if not self._silent:
                notify(self, message, "info")
            return

        self._release = release
        self.install_button.setVisible(True)

        size = f" · {human_size(release.size)}" if release.size else ""
        self._set_status(f"yeni surum hazir · {release.label}{size}", "success")
        notify(self, f"Yeni surum var: {release.label}", "success")

    # ------------------------------------------------------------ kurulum
    @Slot()
    def install_now(self) -> None:
        if self._busy() or self._release is None:
            return

        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._set_status(f"indiriliyor · {self._release.name}", "warning")

        self._installer = InstallThread(self, self._release)
        self._installer.progress.connect(self._on_progress)
        self._installer.ready.connect(self._on_ready)
        self._installer.failed.connect(self._on_failed)
        self._installer.start()

    @Slot(int)
    def _on_progress(self, percent: int) -> None:
        self.progress.setValue(percent)
        self._set_status(f"indiriliyor · %{percent}", "warning")

    @Slot()
    def _on_ready(self) -> None:
        self.progress.setValue(100)
        self._set_status("kuruluyor - uygulama kapanip yeniden acilacak", "success")
        notify(self, "Guncelleme kuruluyor, uygulama kapaniyor.", "success")

        # Betik surecin bitmesini bekliyor; once olay dongusunun toast'i
        # cizmesine izin ver, sonra cik.
        QTimer.singleShot(1200, self._quit)

    @staticmethod
    def _quit() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(True)
        self._set_status(f"hata · {message}", "danger")
        notify(self, f"Guncelleme basarisiz: {message}", "danger")

    # --------------------------------------------------------------- diger
    def refresh_version(self) -> None:
        self.version_label.setText(f"667 Utility {updater.current_label()}")


__all__ = ["UpdateCard", "CheckThread", "InstallThread"]
