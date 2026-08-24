from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.mac_cleaner import RULES, ScanResult, clean, scan_all
from core.mac_permissions import check_access, open_privacy_settings, prompt_native_dialogs
from core.platform_utils import human_size
from src.ui.theme import Colors
from src.ui.views.modern_button import ModernButton

_ROLE_ITEM = Qt.UserRole + 1


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    finished_scan = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            results = scan_all(progress_cb=lambda i, t, label: self.progress.emit(i, t, label))
            self.finished_scan.emit(results)
        except Exception as exc:  # tarama UI'yi cokertmemeli
            self.failed.emit(str(exc))


class CleanWorker(QThread):
    finished_clean = Signal(int, list)

    def __init__(self, items, permanent=False):
        super().__init__()
        self._items = items
        self._permanent = permanent

    def run(self):
        freed, errors = clean(self._items, dry_run=False, permanent=self._permanent)
        self.finished_clean.emit(freed, errors)


class MacCleanerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacCleanerPage")
        self._results: list[ScanResult] = []
        self._scan_worker: ScanWorker | None = None
        self._clean_worker: CleanWorker | None = None
        self._build_ui()
        self._refresh_permissions()

    # ------------------------------------------------------------ arayuz
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Mac Cleaner")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Onbellekleri, loglari ve gelistirici artiklarini temizle.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # izin serifi
        self.permission_bar = QFrame()
        self.permission_bar.setObjectName("PermissionBar")
        self.permission_bar.setStyleSheet(f"""
            QFrame#PermissionBar {{
                background: {Colors.CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        perm_layout = QHBoxLayout(self.permission_bar)
        perm_layout.setContentsMargins(16, 12, 16, 12)
        perm_layout.setSpacing(12)

        self.permission_label = QLabel("Izinler kontrol ediliyor...")
        self.permission_label.setWordWrap(True)
        self.grant_button = ModernButton("Izin Ver", variant="ghost")
        self.grant_button.setFixedWidth(120)
        self.grant_button.clicked.connect(self._request_access)

        perm_layout.addWidget(self.permission_label, stretch=1)
        perm_layout.addWidget(self.grant_button)
        layout.addWidget(self.permission_bar)

        # sonuc agaci
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Kategori / Dosya", "Boyut"])
        self.tree.setColumnWidth(0, 520)
        self.tree.setAlternatingRowColors(False)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, stretch=1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.hide()
        layout.addWidget(self.progress)

        # alt bar
        bottom = QHBoxLayout()
        self.summary_label = QLabel("Henuz tarama yapilmadi.")
        self.summary_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 13px;")

        self.scan_button = ModernButton("Tara", variant="ghost")
        self.scan_button.setFixedWidth(120)
        self.scan_button.clicked.connect(self._start_scan)

        self.clean_button = ModernButton("Cop Kutusuna Tasi", variant="primary")
        self.clean_button.setFixedWidth(190)
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(self._start_clean)

        bottom.addWidget(self.summary_label, stretch=1)
        bottom.addWidget(self.scan_button)
        bottom.addWidget(self.clean_button)
        layout.addLayout(bottom)

    # ------------------------------------------------------------ izinler
    def _refresh_permissions(self):
        report = check_access()
        self.permission_label.setText(report.summary())
        color = Colors.SUCCESS if report.is_sufficient else Colors.WARNING
        self.permission_label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self.grant_button.setVisible(not report.full_disk_access)

    @Slot()
    def _request_access(self):
        prompt_native_dialogs()
        self._refresh_permissions()
        if not check_access().full_disk_access:
            open_privacy_settings("full_disk")
            QMessageBox.information(
                self,
                "Izin Gerekiyor",
                "System Settings acildi.\n\n"
                "Privacy & Security > Full Disk Access altindan bu uygulamayi ekleyip "
                "isaretle, sonra uygulamayi yeniden baslat.",
            )

    # ------------------------------------------------------------ tarama
    @Slot()
    def _start_scan(self):
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.tree.clear()
        self.progress.setRange(0, len(RULES))
        self.progress.setValue(0)
        self.progress.show()

        self._scan_worker = ScanWorker()
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished_scan.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    @Slot(int, int, str)
    def _on_scan_progress(self, index, total, label):
        self.progress.setValue(index)
        self.progress.setFormat(f"Taraniyor: {label} ({index}/{total})")

    @Slot(str)
    def _on_scan_failed(self, message):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.summary_label.setText(f"Tarama basarisiz: {message}")

    @Slot(list)
    def _on_scan_finished(self, results):
        self._results = results
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.tree.blockSignals(True)
        self.tree.clear()

        for result in results:
            if not result.items:
                continue
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{result.rule.label}  —  {result.rule.description}")
            parent.setText(1, result.pretty_size)
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            checked = Qt.Checked if result.rule.enabled_by_default else Qt.Unchecked
            parent.setCheckState(0, checked)
            if result.rule.risk == "danger":
                parent.setForeground(0, Qt.red)

            for item in result.items[:200]:  # UI'yi bogmamak icin ilk 200
                child = QTreeWidgetItem(parent)
                child.setText(0, str(item.path))
                child.setText(1, human_size(item.size))
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, checked)
                child.setData(0, _ROLE_ITEM, item)

        self.tree.blockSignals(False)
        self._update_summary()

    # ------------------------------------------------------------ secim
    @Slot(QTreeWidgetItem, int)
    def _on_item_changed(self, item, column):
        if column == 0:
            self._update_summary()

    def _selected_items(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    data = child.data(0, _ROLE_ITEM)
                    if data is not None:
                        selected.append(data)
        return selected

    def _update_summary(self):
        selected = self._selected_items()
        total = sum(item.size for item in selected)
        self.clean_button.setEnabled(bool(selected))
        if not selected:
            self.summary_label.setText("Secili oge yok.")
        else:
            self.summary_label.setText(
                f"{len(selected)} oge secili — {human_size(total)} kazanilacak."
            )

    # ------------------------------------------------------------ temizlik
    @Slot()
    def _start_clean(self):
        selected = self._selected_items()
        if not selected:
            return
        total = sum(item.size for item in selected)

        answer = QMessageBox.question(
            self,
            "Temizligi Onayla",
            f"{len(selected)} oge cop kutusuna tasinacak ({human_size(total)}).\n\n"
            "Cop kutusundan geri alabilirsin. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.clean_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.summary_label.setText("Temizleniyor...")

        self._clean_worker = CleanWorker(selected, permanent=False)
        self._clean_worker.finished_clean.connect(self._on_clean_finished)
        self._clean_worker.start()

    @Slot(int, list)
    def _on_clean_finished(self, freed, errors):
        self.scan_button.setEnabled(True)
        message = f"{human_size(freed)} temizlendi."
        if errors:
            message += f" {len(errors)} oge atlandi."
        self.summary_label.setText(message)
        self.tree.clear()
        self._results = []
        self.clean_button.setEnabled(False)

        if errors:
            QMessageBox.warning(
                self, "Bazi Ogeler Atlandi", "\n".join(errors[:15])
            )
