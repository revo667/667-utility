"""Time Machine yerel snapshot sayfasi.

core/mac_snapshots.py uzun suredir yaziliydi ama hicbir yerden cagrilmiyordu.
Bu sayfa onu arayuze baglar. Tasarim karari: varsayilan eylem 'incelt'
(thinlocalsnapshots), tek tek silme ise ayri ve daha gorunur bir onay ister -
cunku snapshot silmek geri alinamaz.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.mac_snapshots import (
    MIN_AGE_HOURS,
    Snapshot,
    SnapshotReport,
    delete_snapshot,
    scan_snapshots,
    thin_snapshots,
)
from core.platform_utils import human_size
from src.ui import icons
from src.ui.style import repolish
from src.ui.theme import Colors, Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton
from src.ui.workers import stop_worker

_ROLE_SNAPSHOT = Qt.UserRole + 1

#: Inceltme hedefi. 'Ne kadar yer acilsin' sorusuna makul bir varsayilan.
_THIN_TARGET_GB = 20


class ScanWorker(QThread):
    done = Signal(object)

    def run(self):
        self.done.emit(scan_snapshots())


class ThinWorker(QThread):
    done = Signal(bool, int, str)

    def __init__(self, target_bytes: int, parent=None):
        super().__init__(parent)
        self._target = target_bytes

    def run(self):
        ok, freed, message = thin_snapshots(self._target, urgency=1, dry_run=False)
        self.done.emit(ok, freed, message)


class DeleteWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, snapshot: Snapshot, parent=None):
        super().__init__(parent)
        self._snapshot = snapshot

    def run(self):
        ok, message = delete_snapshot(self._snapshot, dry_run=False)
        self.done.emit(ok, message)


class MacSnapshotsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacSnapshotsPage")
        self._report: SnapshotReport | None = None
        self._worker: QThread | None = None
        self._build_ui()
        self._start_scan()

    # ------------------------------------------------------------- arayuz
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Time Machine Snapshots")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Yerel snapshot'lar disk alani tutar ama ayni zamanda tek geri donus "
            f"noktan olabilir. {MIN_AGE_HOURS} saatten yeni olanlara dokunulmaz."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # -- risk serifi
        self.notice = QFrame()
        self.notice.setObjectName("PermissionBar")
        notice_row = QHBoxLayout(self.notice)
        notice_row.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        notice_row.setSpacing(Spacing.MD)

        self.notice_icon = QLabel()
        self.notice_icon.setPixmap(icons.pixmap("info", Colors.INFO, 18))
        self.notice_icon.setFixedWidth(20)

        self.notice_label = QLabel("Snapshot'lar taraniyor...")
        self.notice_label.setWordWrap(True)
        self.notice_label.setProperty("tone", "secondary")

        notice_row.addWidget(self.notice_icon)
        notice_row.addWidget(self.notice_label, stretch=1)
        layout.addWidget(self.notice)

        # -- liste
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Snapshot", "Yas", "Durum"])
        self.tree.setRootIsDecorated(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.tree, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        # -- alt bar
        bottom = QHBoxLayout()
        bottom.setSpacing(Spacing.SM)

        self.summary = QLabel("")
        self.summary.setProperty("tone", "secondary")
        self.summary.setWordWrap(True)

        self.refresh_button = ModernButton("Yenile", "ghost", "refresh")
        self.refresh_button.clicked.connect(self._start_scan)

        self.delete_button = ModernButton("Secileni Sil", "danger", "uninstaller")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)

        self.thin_button = ModernButton(
            f"{_THIN_TARGET_GB} GB Yer Ac", "primary", "cleaner"
        )
        self.thin_button.setEnabled(False)
        self.thin_button.clicked.connect(self._thin)

        bottom.addWidget(self.summary, stretch=1)
        bottom.addWidget(self.refresh_button)
        bottom.addWidget(self.delete_button)
        bottom.addWidget(self.thin_button)
        layout.addLayout(bottom)

    # -------------------------------------------------------------- tarama
    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.refresh_button.setEnabled(not busy)
        self.thin_button.setEnabled(not busy and self._has_thinnable())
        self.delete_button.setEnabled(not busy and bool(self._selected_snapshot()))

    def _has_thinnable(self) -> bool:
        return bool(self._report and self._report.available and self._report.thinnable)

    @Slot()
    def _start_scan(self):
        self._set_busy(True)
        self.notice_label.setText("Snapshot'lar taraniyor...")
        stop_worker(self._worker)
        self._worker = ScanWorker(self)
        self._worker.done.connect(self._on_scan_done)
        self._worker.start()

    @Slot(object)
    def _on_scan_done(self, report: SnapshotReport):
        self._report = report
        self.tree.clear()

        self.notice_label.setText(report.summary())
        tone = "danger" if not report.has_backup_destination else "secondary"
        if report.available and report.has_backup_destination:
            tone = "secondary"
        self.notice_label.setProperty("tone", tone)
        repolish(self.notice_label)

        color = Colors.DANGER if not report.has_backup_destination else Colors.INFO
        glyph = "alert" if not report.has_backup_destination else "info"
        self.notice_icon.setPixmap(icons.pixmap(glyph, color, 18))

        for snapshot in reversed(report.snapshots):
            item = QTreeWidgetItem(self.tree)
            item.setText(0, snapshot.name)
            item.setText(1, snapshot.pretty_age)
            if snapshot.is_protected:
                item.setText(2, "korunuyor")
                item.setForeground(2, Qt.GlobalColor.gray)
            else:
                item.setText(2, "silinebilir")
                item.setData(0, _ROLE_SNAPSHOT, snapshot)

        if report.available:
            self.summary.setText(
                f"{len(report.snapshots)} snapshot · "
                f"{len(report.thinnable)} tanesi inceltilebilir"
            )
        else:
            self.summary.setText(report.error or "Snapshot yok.")

        self._set_busy(False)

    # -------------------------------------------------------------- secim
    def _selected_snapshot(self) -> Snapshot | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, _ROLE_SNAPSHOT)

    @Slot()
    def _on_selection(self):
        self.delete_button.setEnabled(bool(self._selected_snapshot()))

    # ------------------------------------------------------------ inceltme
    @Slot()
    def _thin(self):
        if not self._report:
            return

        warning = ""
        if not self._report.has_backup_destination:
            warning = (
                "\n\nDIKKAT: Tanimli bir Time Machine yedek diskin yok. "
                "Bu snapshot'lar su an tek kurtarma noktan."
            )

        answer = QMessageBox.question(
            self,
            "Snapshot Inceltmeyi Onayla",
            f"macOS en eski snapshot'lardan baslayarak yaklasik "
            f"{_THIN_TARGET_GB} GB yer acacak.\n\n"
            f"{MIN_AGE_HOURS} saatten yeni olanlara dokunulmayacak.{warning}\n\n"
            "Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._set_busy(True)
        self.summary.setText("Inceltiliyor... bu islem birkac dakika surebilir.")
        stop_worker(self._worker)
        self._worker = ThinWorker(_THIN_TARGET_GB * 1024 ** 3, self)
        self._worker.done.connect(self._on_thin_done)
        self._worker.start()

    @Slot(bool, int, str)
    def _on_thin_done(self, ok: bool, freed: int, message: str):
        notify(self, message or ("Inceltme tamamlandi." if ok else "Inceltme basarisiz."),
               "success" if ok else "danger")
        if freed:
            self.summary.setText(f"{human_size(freed)} serbest birakildi.")
        self._start_scan()

    # --------------------------------------------------------------- silme
    @Slot()
    def _delete_selected(self):
        snapshot = self._selected_snapshot()
        if snapshot is None:
            return

        answer = QMessageBox.warning(
            self,
            "Snapshot Silinecek",
            f"{snapshot.name}\n({snapshot.pretty_age})\n\n"
            "Bu islem GERI ALINAMAZ. Bu snapshot'tan dosya kurtaramazsin.\n\n"
            "Genelde tek tek silmek yerine 'Yer Ac' tercih edilmeli.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        self._set_busy(True)
        stop_worker(self._worker)
        self._worker = DeleteWorker(snapshot, self)
        self._worker.done.connect(self._on_delete_done)
        self._worker.start()

    @Slot(bool, str)
    def _on_delete_done(self, ok: bool, message: str):
        notify(self, message or ("Silindi." if ok else "Silinemedi."),
               "success" if ok else "danger")
        self._start_scan()

    def closeEvent(self, event):
        # Calisan bir tmutil taramasi varken widget yok edilirse Qt abort eder.
        stop_worker(self._worker)
        super().closeEvent(event)
