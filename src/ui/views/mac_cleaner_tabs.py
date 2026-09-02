"""Mac Cleaner'in yan sekmeleri: buyuk dosyalar, kopyalar ve bakim."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.mac_cleaner import (
    GB,
    MB,
    DuplicateGroup,
    JunkItem,
    clean,
    find_duplicates,
    find_large_files,
    path_age_days,
    reveal_in_finder,
)
from core.mac_maintenance import TASKS, MaintenanceTask, TaskResult, run_task
from core.platform_utils import HOME, human_size
from src.ui.settings_store import settings
from src.ui.theme import Radius, Spacing
from src.ui.toast import notify
from src.ui.views.modern_button import ModernButton
from src.ui.workers import stop_worker

_ROLE_ITEM = Qt.UserRole + 1
_ROLE_PATH = Qt.UserRole + 2

SIZE_CHOICES: tuple[tuple[str, int], ...] = (
    ("100 MB uzeri", 100 * MB),
    ("250 MB uzeri", 250 * MB),
    ("500 MB uzeri", 500 * MB),
    ("1 GB uzeri", GB),
    ("5 GB uzeri", 5 * GB),
)

DUP_SIZE_CHOICES: tuple[tuple[str, int], ...] = (
    ("1 MB uzeri", MB),
    ("5 MB uzeri", 5 * MB),
    ("20 MB uzeri", 20 * MB),
    ("100 MB uzeri", 100 * MB),
)


# ------------------------------------------------------------------- isciler
class LargeFilesWorker(QThread):
    found = Signal(list)
    failed = Signal(str)

    def __init__(self, min_size: int, cancel: threading.Event, parent=None):
        super().__init__(parent)
        self._min_size = min_size
        self._cancel = cancel

    def run(self):
        try:
            self.found.emit(find_large_files(min_size=self._min_size, cancel=self._cancel))
        except Exception as exc:
            self.failed.emit(str(exc))


class DuplicatesWorker(QThread):
    found = Signal(list)
    failed = Signal(str)

    def __init__(self, min_size: int, cancel: threading.Event, parent=None):
        super().__init__(parent)
        self._min_size = min_size
        self._cancel = cancel

    def run(self):
        try:
            self.found.emit(find_duplicates(min_size=self._min_size, cancel=self._cancel))
        except Exception as exc:
            self.failed.emit(str(exc))


class TrashWorker(QThread):
    done = Signal(int, list)

    def __init__(self, items: list[JunkItem], parent=None):
        super().__init__(parent)
        self._items = items

    def run(self):
        freed, errors = clean(self._items, dry_run=False, permanent=False)
        self.done.emit(freed, errors)


class MaintenanceWorker(QThread):
    done = Signal(str, bool, str)

    def __init__(self, task: MaintenanceTask, parent=None):
        super().__init__(parent)
        self._task = task

    def run(self):
        result: TaskResult = run_task(self._task)
        self.done.emit(self._task.label, result.ok, result.message)


# --------------------------------------------------------------- ortak taban
class _ListTabBase(QWidget):
    """Tarayan + secip cop kutusuna tasiyan sekmeler icin ortak iskelet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_worker: QThread | None = None
        self._trash_worker: TrashWorker | None = None
        self._cancel = threading.Event()

    def _make_tree(self, headers: list[str], widths: list[int]) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        for index, width in enumerate(widths):
            tree.setColumnWidth(index, width)
        tree.setAlternatingRowColors(False)
        tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        tree.itemDoubleClicked.connect(self._reveal_item)
        return tree

    @Slot(QTreeWidgetItem, int)
    def _reveal_item(self, item: QTreeWidgetItem, _column: int):
        path = item.data(0, _ROLE_PATH)
        if path:
            reveal_in_finder(Path(path))

    def _checked_items(self, tree: QTreeWidget) -> list[JunkItem]:
        found: list[JunkItem] = []
        stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        while stack:
            node = stack.pop()
            if node is None:
                continue
            data = node.data(0, _ROLE_ITEM)
            if data is not None and node.checkState(0) == Qt.Checked:
                found.append(data)
            stack.extend(node.child(i) for i in range(node.childCount()))
        return found

    def _confirm_and_trash(self, items: list[JunkItem], on_done) -> bool:
        if not items:
            return False
        total = sum(item.size for item in items)
        if settings.get("confirm_destructive"):
            answer = QMessageBox.question(
                self, "Onayla",
                f"{len(items)} oge cop kutusuna tasinacak ({human_size(total)}).\n\n"
                "Cop kutusundan geri alabilirsin. Devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False

        self._trash_worker = TrashWorker(items, self)
        self._trash_worker.done.connect(on_done)
        self._trash_worker.start()
        return True

    def stop(self):
        self._cancel.set()
        stop_worker(self._scan_worker)
        stop_worker(self._trash_worker)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


# -------------------------------------------------------------- buyuk dosyalar
class LargeFilesTab(_ListTabBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.MD, 0, 0)
        layout.setSpacing(Spacing.MD)

        info = QLabel(
            "Ev dizinindeki en buyuk dosyalar. Cift tiklayarak Finder'da acabilirsin."
        )
        info.setProperty("tone", "secondary")
        layout.addWidget(info)

        bar = QHBoxLayout()
        bar.setSpacing(Spacing.SM)
        self.size_box = QComboBox()
        for label, _value in SIZE_CHOICES:
            self.size_box.addItem(label)
        self.size_box.setCurrentIndex(1)
        self.size_box.setFixedWidth(170)

        self.scan_button = ModernButton("Tara", "ghost", "search")
        self.scan_button.setFixedWidth(110)
        self.scan_button.clicked.connect(self._start_scan)

        bar.addWidget(QLabel("Esik:"))
        bar.addWidget(self.size_box)
        bar.addWidget(self.scan_button)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.tree = self._make_tree(["Dosya", "Boyut", "Son Degisiklik"], [560, 110, 130])
        layout.addWidget(self.tree, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.summary = QLabel("Henuz tarama yapilmadi.")
        self.summary.setProperty("tone", "secondary")
        self.reveal_button = ModernButton("Finder'da Goster", "ghost", "search")
        self.reveal_button.setFixedWidth(170)
        self.reveal_button.clicked.connect(self._reveal_selected)
        self.trash_button = ModernButton("Cop Kutusuna Tasi", "primary", "cleaner")
        self.trash_button.setFixedWidth(200)
        self.trash_button.setEnabled(False)
        self.trash_button.clicked.connect(self._trash_selected)

        bottom.addWidget(self.summary, stretch=1)
        bottom.addWidget(self.reveal_button)
        bottom.addWidget(self.trash_button)
        layout.addLayout(bottom)

        self.tree.itemChanged.connect(lambda *_: self._update_summary())

    @Slot()
    def _start_scan(self):
        self._cancel = threading.Event()
        self.tree.clear()
        self.progress.show()
        self.scan_button.setEnabled(False)
        self.summary.setText("Taraniyor... (buyuk dizinlerde bir dakika surebilir)")

        min_size = SIZE_CHOICES[self.size_box.currentIndex()][1]
        self._scan_worker = LargeFilesWorker(min_size, self._cancel, self)
        self._scan_worker.found.connect(self._on_found)
        self._scan_worker.failed.connect(self._on_failed)
        self._scan_worker.start()

    @Slot(str)
    def _on_failed(self, message):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.summary.setText(f"Tarama basarisiz: {message}")

    @Slot(list)
    def _on_found(self, items: list[JunkItem]):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.tree.blockSignals(True)
        self.tree.clear()

        for item in items:
            node = QTreeWidgetItem(self.tree)
            try:
                shown = str(item.path.relative_to(HOME))
            except ValueError:
                shown = str(item.path)
            node.setText(0, shown)
            node.setText(1, human_size(item.size))
            node.setText(2, f"{path_age_days(item.path):.0f} gun once")
            node.setFlags(node.flags() | Qt.ItemIsUserCheckable)
            node.setCheckState(0, Qt.Unchecked)
            node.setData(0, _ROLE_ITEM, item)
            node.setData(0, _ROLE_PATH, str(item.path))
            node.setToolTip(0, str(item.path))

        self.tree.blockSignals(False)
        total = sum(item.size for item in items)
        self.summary.setText(
            f"{len(items)} dosya bulundu — toplam {human_size(total)}."
            if items else "Bu esigin uzerinde dosya yok."
        )

    def _update_summary(self):
        checked = self._checked_items(self.tree)
        self.trash_button.setEnabled(bool(checked))
        if checked:
            total = sum(item.size for item in checked)
            self.summary.setText(f"{len(checked)} secili — {human_size(total)}.")

    @Slot()
    def _reveal_selected(self):
        for node in self.tree.selectedItems():
            path = node.data(0, _ROLE_PATH)
            if path:
                reveal_in_finder(Path(path))
                break

    @Slot()
    def _trash_selected(self):
        items = self._checked_items(self.tree)
        if self._confirm_and_trash(items, self._on_trashed):
            self.trash_button.setEnabled(False)

    @Slot(int, list)
    def _on_trashed(self, freed, errors):
        message = f"{human_size(freed)} cop kutusuna tasindi."
        if errors:
            message += f" {len(errors)} oge atlandi."
        self.summary.setText(message + " Listeyi yenilemek icin tekrar tara.")
        notify(self, message, "warning" if errors else "success")
        self.tree.clear()
        self.trash_button.setEnabled(False)


# ------------------------------------------------------------------ kopyalar
class DuplicatesTab(_ListTabBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[DuplicateGroup] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.MD, 0, 0)
        layout.setSpacing(Spacing.MD)

        info = QLabel(
            "Downloads, Documents, Desktop, Movies ve Music icinde birebir ayni dosyalar. "
            "Icerik hash'i ile karsilastirilir - ad benzerligi yeterli degildir."
        )
        info.setProperty("tone", "secondary")
        info.setWordWrap(True)
        layout.addWidget(info)

        bar = QHBoxLayout()
        bar.setSpacing(Spacing.SM)
        self.size_box = QComboBox()
        for label, _value in DUP_SIZE_CHOICES:
            self.size_box.addItem(label)
        self.size_box.setCurrentIndex(1)
        self.size_box.setFixedWidth(170)

        self.scan_button = ModernButton("Tara", "ghost", "search")
        self.scan_button.setFixedWidth(110)
        self.scan_button.clicked.connect(self._start_scan)

        self.auto_button = ModernButton("En Yenisini Birak", "ghost", "check")
        self.auto_button.setFixedWidth(180)
        self.auto_button.setEnabled(False)
        self.auto_button.clicked.connect(self._auto_select)

        bar.addWidget(QLabel("Esik:"))
        bar.addWidget(self.size_box)
        bar.addWidget(self.scan_button)
        bar.addWidget(self.auto_button)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.tree = self._make_tree(["Dosya", "Boyut", "Son Degisiklik"], [560, 110, 130])
        layout.addWidget(self.tree, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.summary = QLabel("Henuz tarama yapilmadi.")
        self.summary.setProperty("tone", "secondary")
        self.trash_button = ModernButton("Cop Kutusuna Tasi", "primary", "cleaner")
        self.trash_button.setFixedWidth(200)
        self.trash_button.setEnabled(False)
        self.trash_button.clicked.connect(self._trash_selected)

        bottom.addWidget(self.summary, stretch=1)
        bottom.addWidget(self.trash_button)
        layout.addLayout(bottom)

        self.tree.itemChanged.connect(lambda *_: self._update_summary())

    @Slot()
    def _start_scan(self):
        self._cancel = threading.Event()
        self.tree.clear()
        self.progress.show()
        self.scan_button.setEnabled(False)
        self.auto_button.setEnabled(False)
        self.summary.setText("Dosya icerikleri karsilastiriliyor...")

        min_size = DUP_SIZE_CHOICES[self.size_box.currentIndex()][1]
        self._scan_worker = DuplicatesWorker(min_size, self._cancel, self)
        self._scan_worker.found.connect(self._on_found)
        self._scan_worker.failed.connect(self._on_failed)
        self._scan_worker.start()

    @Slot(str)
    def _on_failed(self, message):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.summary.setText(f"Tarama basarisiz: {message}")

    @Slot(list)
    def _on_found(self, groups: list[DuplicateGroup]):
        self._groups = groups
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.auto_button.setEnabled(bool(groups))
        self.tree.blockSignals(True)
        self.tree.clear()

        for group in groups:
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{group.paths[0].name}  ({len(group.paths)} kopya)")
            parent.setText(1, human_size(group.size))
            parent.setText(2, f"{human_size(group.wasted)} bosa gidiyor")
            parent.setForeground(2, Qt.gray)

            for path in group.paths:
                child = QTreeWidgetItem(parent)
                try:
                    shown = str(path.relative_to(HOME))
                except ValueError:
                    shown = str(path)
                child.setText(0, shown)
                child.setText(1, human_size(group.size))
                child.setText(2, f"{path_age_days(path):.0f} gun once")
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, _ROLE_ITEM, JunkItem(path=path, size=group.size,
                                                      rule_key="duplicate"))
                child.setData(0, _ROLE_PATH, str(path))
                child.setToolTip(0, str(path))
            parent.setExpanded(len(groups) <= 12)

        self.tree.blockSignals(False)
        wasted = sum(group.wasted for group in groups)
        self.summary.setText(
            f"{len(groups)} kopya grubu — {human_size(wasted)} bosa gidiyor."
            if groups else "Kopya dosya bulunamadi."
        )

    @Slot()
    def _auto_select(self):
        """Her grupta en yeni dosyayi birak, digerlerini isaretle."""
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            children = [parent.child(j) for j in range(parent.childCount())]
            if len(children) < 2:
                continue
            newest = max(children, key=lambda node: -path_age_days(
                Path(node.data(0, _ROLE_PATH))
            ))
            for child in children:
                child.setCheckState(0, Qt.Unchecked if child is newest else Qt.Checked)
        self.tree.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        checked = self._checked_items(self.tree)
        self.trash_button.setEnabled(bool(checked))
        if checked:
            total = sum(item.size for item in checked)
            self.summary.setText(f"{len(checked)} kopya secili — {human_size(total)} kazanilacak.")

    @Slot()
    def _trash_selected(self):
        items = self._checked_items(self.tree)
        if self._confirm_and_trash(items, self._on_trashed):
            self.trash_button.setEnabled(False)

    @Slot(int, list)
    def _on_trashed(self, freed, errors):
        message = f"{human_size(freed)} cop kutusuna tasindi."
        if errors:
            message += f" {len(errors)} oge atlandi."
        self.summary.setText(message)
        notify(self, message, "warning" if errors else "success")
        self.tree.clear()
        self.trash_button.setEnabled(False)


# --------------------------------------------------------------------- bakim
class MaintenanceCard(QFrame):
    def __init__(self, task: MaintenanceTask, on_run, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._task = task

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.MD)

        stripe = QFrame()
        stripe.setObjectName("RiskStripe")
        stripe.setProperty("risk", task.risk)
        stripe.setFixedWidth(4)
        layout.addWidget(stripe)

        text = QVBoxLayout()
        text.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.SM)
        title = QLabel(task.label)
        title.setObjectName("ItemTitle")
        title_row.addWidget(title)
        if task.needs_admin:
            badge = QLabel("yonetici")
            badge.setObjectName("Badge")
            badge.setProperty("tone", "warning")
            title_row.addWidget(badge)
        title_row.addStretch(1)

        desc = QLabel(task.description)
        desc.setObjectName("ItemMeta")
        desc.setWordWrap(True)

        text.addLayout(title_row)
        text.addWidget(desc)
        layout.addLayout(text, stretch=1)

        variant = "danger" if task.risk == "danger" else "ghost"
        self.run_button = ModernButton("Calistir", variant, "check")
        self.run_button.setFixedWidth(120)
        self.run_button.clicked.connect(lambda: on_run(task, self.run_button))
        layout.addWidget(self.run_button)


class MaintenanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: MaintenanceWorker | None = None
        self._active_button: ModernButton | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.MD, 0, 0)
        layout.setSpacing(Spacing.MD)

        info = QLabel(
            "Dosya silmeyen sistem islemleri. Yonetici rozetli olanlar macOS'un "
            "kendi parola penceresini acar - parola uygulamaya girilmez."
        )
        info.setProperty("tone", "secondary")
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, Spacing.SM, 0)
        inner.setSpacing(Spacing.SM)

        for task in TASKS:
            inner.addWidget(MaintenanceCard(task, self._run_task))
        inner.addStretch(1)

        scroll.setWidget(holder)
        layout.addWidget(scroll, stretch=1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(110)
        self.log.setPlaceholderText("Islem ciktilari burada gorunur.")
        self.log.setStyleSheet(f"border-radius: {Radius.SM}px;")
        layout.addWidget(self.log)

    def _run_task(self, task: MaintenanceTask, button: ModernButton):
        if self._worker is not None and self._worker.isRunning():
            notify(self, "Baska bir bakim islemi suruyor.", "warning")
            return

        if task.risk != "safe" and settings.get("confirm_destructive"):
            answer = QMessageBox.question(
                self, task.label,
                f"{task.description}\n\nDevam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        button.setEnabled(False)
        button.setText("Calisiyor")
        self._active_button = button
        self.log.appendPlainText(f"> {task.label}")

        self._worker = MaintenanceWorker(task, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    @Slot(str, bool, str)
    def _on_done(self, label, ok, message):
        if self._active_button is not None:
            self._active_button.setEnabled(True)
            self._active_button.setText("Calistir")
            self._active_button = None

        text = message.strip() or ("Tamamlandi." if ok else "Basarisiz.")
        self.log.appendPlainText(f"  {'OK' if ok else 'HATA'}: {text}")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        notify(self, f"{label}: {text[:80]}", "success" if ok else "danger")

    def stop(self):
        stop_worker(self._worker)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


__all__ = ["DuplicatesTab", "LargeFilesTab", "MaintenanceTab"]
