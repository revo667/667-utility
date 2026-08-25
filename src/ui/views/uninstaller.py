from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.platform_utils import IS_WINDOWS
from core.uninstaller import get_installed_programs, remove_bloatware, uninstall_program
from src.ui.settings_store import settings
from src.ui.theme import Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton


class WorkerThread(QThread):
    """Sinyal adi 'done': QThread'in kendi 'finished' sinyalini golgelememesi icin."""

    done = Signal(bool, str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args

    def run(self):
        try:
            result = self.fn(*self.args)
            self.done.emit(bool(result), "")
        except Exception as exc:
            self.done.emit(False, str(exc))


class ProgramRow(QFrame):
    def __init__(self, name: str, uninstall_str: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.uninstall_str = uninstall_str
        self.setObjectName("AppRow")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)

        name_label = QLabel(self.name)
        name_label.setObjectName("ItemTitle")

        self.btn = ModernButton("Kaldir", "danger", "uninstaller")
        self.btn.setFixedWidth(120)
        self.btn.clicked.connect(self._on_uninstall)

        layout.addWidget(name_label, stretch=1)
        layout.addWidget(self.btn)

    def _on_uninstall(self):
        self.btn.setEnabled(False)
        self.btn.setText("Kaldiriliyor...")
        self.worker = WorkerThread(uninstall_program, self.uninstall_str)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self, success, error):
        if success:
            self.btn.setText("Kaldirildi")
            self.btn.set_variant("subtle")
            notify(self, f"{self.name} kaldirildi.", "success")
        else:
            self.btn.setEnabled(True)
            self.btn.setText("Basarisiz")
            notify(self, f"{self.name} kaldirilamadi. {error}".strip(), "danger")


class UninstallerView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("UninstallerView")
        self.all_programs = []
        self.rows = []
        self._build_ui()
        self._load_programs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Uninstall Tool")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Kurulu programlari kaldir veya Windows bloatware'ini temizle.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.bloat_btn = ModernButton("Windows Bloatware'ini Kaldir", "danger", "cleaner")
        self.bloat_btn.setFixedHeight(42)
        self.bloat_btn.clicked.connect(self._on_remove_bloatware)
        layout.addWidget(self.bloat_btn)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Program ara...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.count_label = QLabel("")
        self.count_label.setObjectName("ItemMeta")
        layout.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(Spacing.XS)
        self.list_layout.setContentsMargins(0, 0, Spacing.SM, 0)

        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll, stretch=1)

    def _load_programs(self):
        if not IS_WINDOWS:
            self.count_label.setText("Bu ozellik yalnizca Windows'ta kullanilabilir.")
            self.bloat_btn.setEnabled(False)
            self.search.setEnabled(False)
            return
        self.all_programs = get_installed_programs()
        self._render(self.all_programs)

    def _render(self, programs):
        # Mevcut listeyi temizle
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.rows = []

        for p in programs:
            row = ProgramRow(p["name"], p["uninstall_str"])
            self.list_layout.addWidget(row)
            self.rows.append(row)

        self.list_layout.addStretch()
        self.count_label.setText(f"{len(programs)} program listeleniyor")

    def _filter(self, text):
        filtered = [p for p in self.all_programs
                    if text.lower() in p["name"].lower()]
        self._render(filtered)

    def _on_remove_bloatware(self):
        if not IS_WINDOWS:
            return

        if settings.get("confirm_destructive"):
            answer = QMessageBox.question(
                self, "Bloatware Kaldirilacak",
                "Onceden tanimli Microsoft UWP uygulamalari kaldirilacak "
                "(Xbox, Haritalar, Haberler, Zune vb.).\n\n"
                "Bunlari sonradan Microsoft Store uzerinden geri kurabilirsin.\n\n"
                "Devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        self.bloat_btn.setEnabled(False)
        self.bloat_btn.setText("Kaldiriliyor...")
        self.worker = WorkerThread(remove_bloatware)
        self.worker.done.connect(self._on_bloat_done)
        self.worker.start()

    def _on_bloat_done(self, success, error):
        self.bloat_btn.setEnabled(True)
        self.bloat_btn.setText("Windows Bloatware'ini Kaldir")
        notify(
            self,
            "Bloatware temizlendi." if success else f"Temizlik basarisiz. {error}".strip(),
            "success" if success else "danger",
        )
