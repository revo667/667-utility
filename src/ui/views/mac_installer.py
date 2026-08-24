from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QVBoxLayout, QWidget,
)

from core.mac_installer import (
    Package, install, install_instructions, is_available, search,
)
from src.ui.views.modern_button import ModernButton


class SearchWorker(QThread):
    done = Signal(bool, list, str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        ok, packages, message = search(self.query)
        self.done.emit(ok, packages, message)


class InstallWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, package):
        super().__init__()
        self.package = package

    def run(self):
        ok, message = install(self.package)
        self.done.emit(ok, message)


class MacInstallerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacInstallerPage")
        self._search_worker = None
        self._install_worker = None
        self._build_ui()
        self._check_brew()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Install Apps")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Homebrew uzerinden uygulama ve komut satiri araci kur.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        self.notice.hide()
        layout.addWidget(self.notice)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Paket ara (orn. firefox, ripgrep, iterm2)")
        self.search_input.returnPressed.connect(self._start_search)
        self.search_button = ModernButton("Ara", variant="ghost")
        self.search_button.setFixedWidth(110)
        self.search_button.clicked.connect(self._start_search)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.results = QListWidget()
        self.results.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.results, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.status = QLabel("Hazir.")
        self.status.setWordWrap(True)
        self.install_button = ModernButton("Kur", variant="primary")
        self.install_button.setFixedWidth(140)
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._start_install)
        bottom.addWidget(self.status, stretch=1)
        bottom.addWidget(self.install_button)
        layout.addLayout(bottom)

    def _check_brew(self):
        if is_available():
            return
        self.notice.setText(install_instructions())
        self.notice.show()
        self.search_input.setEnabled(False)
        self.search_button.setEnabled(False)
        self.status.setText("Homebrew bulunamadi.")

    @Slot()
    def _start_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.search_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.results.clear()
        self.progress.show()
        self.status.setText(f"Araniyor: {query}")

        self._search_worker = SearchWorker(query)
        self._search_worker.done.connect(self._on_search_done)
        self._search_worker.start()

    @Slot(bool, list, str)
    def _on_search_done(self, ok, packages, message):
        self.progress.hide()
        self.search_button.setEnabled(True)

        if not ok:
            self.status.setText(message or "Sonuc bulunamadi.")
            return

        for package in packages:
            item = QListWidgetItem(package.label)
            item.setData(256, package)
            self.results.addItem(item)
        self.status.setText(f"{len(packages)} sonuc.")

    @Slot()
    def _on_selection(self):
        self.install_button.setEnabled(bool(self.results.selectedItems()))

    @Slot()
    def _start_install(self):
        items = self.results.selectedItems()
        if not items:
            return
        package: Package = items[0].data(256)

        answer = QMessageBox.question(
            self, "Kurulumu Onayla",
            f"{package.token} kurulacak.\n\nBu islem birkac dakika surebilir. Devam?",
        )
        if answer != QMessageBox.Yes:
            return

        self.install_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.progress.show()
        self.status.setText(f"Kuruluyor: {package.token} ...")

        self._install_worker = InstallWorker(package)
        self._install_worker.done.connect(self._on_install_done)
        self._install_worker.start()

    @Slot(bool, str)
    def _on_install_done(self, ok, message):
        self.progress.hide()
        self.search_button.setEnabled(True)
        self.install_button.setEnabled(True)
        self.status.setText(message if ok else message[:300])
        if not ok:
            QMessageBox.warning(self, "Kurulum Basarisiz", message[:1000])
