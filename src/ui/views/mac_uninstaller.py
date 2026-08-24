from dataclasses import replace

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QTextEdit, QVBoxLayout, QWidget,
)

from core.mac_cleaner import path_size
from core.mac_uninstaller import (
    MacAppEntry, UninstallPlan, build_plan, execute, list_installed_apps,
)
from core.platform_utils import human_size
from src.ui.views.modern_button import ModernButton

_ROLE_ENTRY = Qt.UserRole + 1


class AppScanWorker(QThread):
    done = Signal(list, str)

    def run(self):
        tokens = set()
        try:
            from core.mac_installer import installed_casks
            tokens = installed_casks()
        except Exception:
            tokens = set()

        try:
            entries = list_installed_apps(with_size=False, cask_tokens=tokens)
            self.done.emit(entries, "")
        except Exception as exc:
            self.done.emit([], f"{type(exc).__name__}: {exc}")


class PlanWorker(QThread):
    done = Signal(object, str)

    def __init__(self, entry, include_leftovers):
        super().__init__()
        self.entry = entry
        self.include_leftovers = include_leftovers

    def run(self):
        try:
            entry = self.entry
            if entry.size == 0:
                entry = replace(entry, size=path_size(entry.path))
            self.done.emit(build_plan(entry, self.include_leftovers), "")
        except Exception as exc:
            self.done.emit(None, f"{type(exc).__name__}: {exc}")


class UninstallWorker(QThread):
    done = Signal(bool, int, list)

    def __init__(self, plan):
        super().__init__()
        self.plan = plan

    def run(self):
        try:
            ok, freed, messages = execute(self.plan, dry_run=False)
            self.done.emit(ok, freed, messages)
        except Exception as exc:
            self.done.emit(False, 0, [f"{type(exc).__name__}: {exc}"])


class MacUninstallerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacUninstallerPage")
        self._entries: list[MacAppEntry] = []
        self._plan: UninstallPlan | None = None
        self._workers = set()
        self._scan_worker = None
        self._plan_worker = None
        self._uninstall_worker = None
        self._build_ui()
        self._start_scan()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Uninstall Apps")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Uygulamalari ve geride biraktiklari artiklari kaldir.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Uygulama filtrele")
        self.filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_input)

        split = QHBoxLayout()
        self.app_list = QListWidget()
        self.app_list.itemSelectionChanged.connect(self._on_selection)
        split.addWidget(self.app_list, stretch=1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Bir uygulama sec.")
        split.addWidget(self.detail, stretch=1)
        layout.addLayout(split, stretch=1)

        self.leftover_check = QCheckBox("Artik dosyalari da kaldir")
        self.leftover_check.setChecked(True)
        self.leftover_check.stateChanged.connect(self._on_selection)
        layout.addWidget(self.leftover_check)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.status = QLabel("Uygulamalar taraniyor...")
        self.status.setWordWrap(True)
        self.refresh_button = ModernButton("Yenile", variant="ghost")
        self.refresh_button.setFixedWidth(110)
        self.refresh_button.clicked.connect(self._start_scan)
        self.uninstall_button = ModernButton("Kaldir", variant="danger")
        self.uninstall_button.setFixedWidth(140)
        self.uninstall_button.setEnabled(False)
        self.uninstall_button.clicked.connect(self._start_uninstall)
        bottom.addWidget(self.status, stretch=1)
        bottom.addWidget(self.refresh_button)
        bottom.addWidget(self.uninstall_button)
        layout.addLayout(bottom)

    def _track(self, worker):
        self._workers.add(worker)
        worker.finished.connect(lambda w=worker: self._untrack(w))
        return worker

    def _untrack(self, worker):
        self._workers.discard(worker)
        worker.deleteLater()

    def _retire(self, worker):
        if worker is None:
            return
        try:
            worker.done.disconnect()
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event):
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(5000)
        super().closeEvent(event)

    @Slot()
    def _start_scan(self):
        self.refresh_button.setEnabled(False)
        self.uninstall_button.setEnabled(False)
        self.app_list.blockSignals(True)
        self.app_list.clear()
        self.app_list.blockSignals(False)
        self.detail.clear()
        self.progress.show()
        self.status.setText("Uygulamalar taraniyor...")

        self._retire(self._scan_worker)
        self._scan_worker = self._track(AppScanWorker())
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.start()

    @Slot(list, str)
    def _on_scan_done(self, entries, error):
        self.progress.hide()
        self.refresh_button.setEnabled(True)

        if error:
            self.status.setText(f"Tarama basarisiz: {error}")
            self.detail.setPlainText(error)
            return

        self._entries = entries
        self._populate()
        removable = sum(1 for entry in entries if not entry.is_protected)
        self.status.setText(f"{len(entries)} uygulama ({removable} kaldirilabilir).")

    def _populate(self):
        self.app_list.blockSignals(True)
        self.app_list.clear()
        needle = self.filter_input.text().strip().lower()

        for entry in self._entries:
            if needle and needle not in entry.name.lower():
                continue
            label = entry.name
            if entry.cask_token:
                label += "   [brew]"
            if entry.is_protected:
                label += "   (korumali)"
            item = QListWidgetItem(label)
            item.setData(_ROLE_ENTRY, entry)
            if entry.is_protected:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.app_list.addItem(item)

        self.app_list.blockSignals(False)

    @Slot()
    def _apply_filter(self):
        self._populate()

    @Slot()
    def _on_selection(self):
        items = self.app_list.selectedItems()
        if not items:
            self.uninstall_button.setEnabled(False)
            return

        entry: MacAppEntry = items[0].data(_ROLE_ENTRY)
        if entry.is_protected:
            self.detail.setPlainText(f"{entry.name}\n\n{entry.protection_reason}")
            self.uninstall_button.setEnabled(False)
            return

        self.detail.setPlainText("Boyut ve artiklar hesaplaniyor...")
        self.uninstall_button.setEnabled(False)

        self._retire(self._plan_worker)
        self._plan_worker = self._track(PlanWorker(entry, self.leftover_check.isChecked()))
        self._plan_worker.done.connect(self._on_plan_ready)
        self._plan_worker.start()

    @Slot(object, str)
    def _on_plan_ready(self, plan, error):
        if error or plan is None:
            self.detail.setPlainText(error or "Plan olusturulamadi.")
            self.uninstall_button.setEnabled(False)
            return
        self._plan = plan
        self.detail.setPlainText(plan.describe())
        self.uninstall_button.setEnabled(True)

    @Slot()
    def _start_uninstall(self):
        if self._plan is None:
            return

        answer = QMessageBox.question(
            self, "Kaldirmayi Onayla",
            f"{self._plan.entry.name} kaldirilacak.\n\n"
            f"Toplam {self._plan.pretty_total} cop kutusuna tasinacak.\n"
            "Cop kutusundan geri alabilirsin. Devam?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.uninstall_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.progress.show()
        self.status.setText("Kaldiriliyor...")

        self._retire(self._uninstall_worker)
        self._uninstall_worker = self._track(UninstallWorker(self._plan))
        self._uninstall_worker.done.connect(self._on_uninstall_done)
        self._uninstall_worker.start()

    @Slot(bool, int, list)
    def _on_uninstall_done(self, ok, freed, messages):
        self.progress.hide()
        self.refresh_button.setEnabled(True)
        self.status.setText(f"{human_size(freed)} temizlendi.")
        self.detail.setPlainText("\n".join(messages))
        self._plan = None
        if not ok:
            QMessageBox.warning(self, "Kismen Basarisiz", "\n".join(messages[:15]))
        QTimer.singleShot(300, self._start_scan)