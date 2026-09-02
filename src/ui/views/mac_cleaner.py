"""Mac Cleaner sayfasi.

Dort sekme: kural tabanli junk taramasi, buyuk dosyalar, kopya dosyalar ve
sistem bakimi. Tarama ve silme her zaman ayri thread'de calisir.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.mac_cleaner import (
    CATEGORY_ORDER,
    RULES,
    JunkItem,
    ScanResult,
    active_rules,
    clean,
    disk_usage,
    reveal_in_finder,
    scan_all,
)
from core.mac_permissions import check_access, open_privacy_settings, prompt_native_dialogs
from core.mac_responsible import identify_responsible
from core.platform_utils import human_size
from src.ui import icons
from src.ui.settings_store import settings
from src.ui.style import repolish
from src.ui.theme import Colors, Spacing
from src.ui.toast import notify
from src.ui.views.mac_cleaner_tabs import DuplicatesTab, LargeFilesTab, MaintenanceTab
from src.ui.views.modern_button import ModernButton
from src.ui.workers import stop_worker

_ROLE_ITEM = Qt.UserRole + 1     # tek JunkItem
_ROLE_ITEMS = Qt.UserRole + 2    # "ve N oge daha" dugumu: list[JunkItem]
_ROLE_RISK = Qt.UserRole + 3
_ROLE_PATH = Qt.UserRole + 4

#: Bir kural altinda agacta gosterilecek en fazla satir. Gerisi tek dugume katlanir.
VISIBLE_PER_RULE = 250


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    finished_scan = Signal(list)
    failed = Signal(str)

    def __init__(self, deep: bool, cancel: threading.Event, parent=None):
        super().__init__(parent)
        self._deep = deep
        self._cancel = cancel

    def run(self):
        try:
            results = scan_all(
                progress_cb=lambda i, t, label: self.progress.emit(i, t, label),
                deep=self._deep,
                cancel=self._cancel,
            )
            self.finished_scan.emit(results)
        except Exception as exc:  # tarama UI'yi cokertmemeli
            self.failed.emit(str(exc))


class CleanWorker(QThread):
    progress = Signal(int, int)
    finished_clean = Signal(int, list)

    def __init__(self, items, permanent=False, cancel=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._permanent = permanent
        self._cancel = cancel

    def run(self):
        freed, errors = clean(
            self._items,
            dry_run=False,
            permanent=self._permanent,
            cancel=self._cancel,
            progress_cb=lambda i, t, _p: self.progress.emit(i, t),
        )
        self.finished_clean.emit(freed, errors)


class MacCleanerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacCleanerPage")
        self._results: list[ScanResult] = []
        self._scan_worker: ScanWorker | None = None
        self._clean_worker: CleanWorker | None = None
        self._cancel = threading.Event()
        self._build_ui()
        self._refresh_permissions()
        self._refresh_disk()

    # ------------------------------------------------------------ arayuz
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Mac Cleaner")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Onbellek, log, gelistirici artigi, buyuk ve kopya dosyalar, sistem bakimi."
        )
        subtitle.setObjectName("PageSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, stretch=1)
        header.addWidget(self._build_disk_card())
        layout.addLayout(header)

        layout.addWidget(self._build_permission_bar())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_junk_tab(), "Temizlik")
        self.large_tab = LargeFilesTab()
        self.duplicates_tab = DuplicatesTab()
        self.maintenance_tab = MaintenanceTab()
        self.tabs.addTab(self.large_tab, "Buyuk Dosyalar")
        self.tabs.addTab(self.duplicates_tab, "Kopyalar")
        self.tabs.addTab(self.maintenance_tab, "Bakim")
        layout.addWidget(self.tabs, stretch=1)

    def _build_disk_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("StatCard")
        card.setFixedWidth(300)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        inner.setSpacing(Spacing.XS)

        self.disk_label = QLabel("Disk okunuyor...")
        self.disk_label.setObjectName("CardTitle")
        self.disk_bar = QProgressBar()
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setFixedHeight(6)
        self.disk_free = QLabel("")
        self.disk_free.setObjectName("ItemMeta")

        inner.addWidget(self.disk_label)
        inner.addWidget(self.disk_bar)
        inner.addWidget(self.disk_free)
        return card

    def _build_permission_bar(self) -> QWidget:
        self.permission_bar = QFrame()
        self.permission_bar.setObjectName("PermissionBar")
        perm_layout = QHBoxLayout(self.permission_bar)
        perm_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        perm_layout.setSpacing(Spacing.MD)

        self.permission_icon = QLabel()
        self.permission_icon.setPixmap(icons.pixmap("shield", Colors.TEXT_MUTED, 18))
        self.permission_icon.setFixedWidth(20)

        self.permission_label = QLabel("Izinler kontrol ediliyor...")
        self.permission_label.setWordWrap(True)

        self.grant_button = ModernButton("Izin Ver", "ghost", "shield")
        self.grant_button.setFixedWidth(130)
        self.grant_button.clicked.connect(self._request_access)

        perm_layout.addWidget(self.permission_icon)
        perm_layout.addWidget(self.permission_label, stretch=1)
        perm_layout.addWidget(self.grant_button)
        return self.permission_bar

    def _build_junk_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, Spacing.MD, 0, 0)
        layout.setSpacing(Spacing.MD)

        bar = QHBoxLayout()
        bar.setSpacing(Spacing.SM)

        self.scan_button = ModernButton("Tara", "ghost", "search")
        self.scan_button.setFixedWidth(110)
        self.scan_button.clicked.connect(self._start_scan)

        self.stop_button = ModernButton("Durdur", "subtle", "close")
        self.stop_button.setFixedWidth(110)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_scan)

        self.deep_check = QCheckBox("Derin tarama")
        self.deep_check.setToolTip(
            "node_modules ve kaldirilmis uygulama artiklarini da arar. Daha yavastir."
        )

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrele (ornek: Chrome, Xcode, .log)")
        self.filter_edit.textChanged.connect(self._apply_filter)

        self.select_safe = ModernButton("Guvenli Sec", "ghost", "check")
        self.select_safe.setFixedWidth(140)
        self.select_safe.clicked.connect(lambda: self._bulk_select("safe"))
        self.select_all = ModernButton("Tumu", "subtle")
        self.select_all.setFixedWidth(80)
        self.select_all.clicked.connect(lambda: self._bulk_select("all"))
        self.select_none = ModernButton("Hicbiri", "subtle")
        self.select_none.setFixedWidth(90)
        self.select_none.clicked.connect(lambda: self._bulk_select("none"))

        bar.addWidget(self.scan_button)
        bar.addWidget(self.stop_button)
        bar.addWidget(self.deep_check)
        bar.addWidget(self.filter_edit, stretch=1)
        bar.addWidget(self.select_safe)
        bar.addWidget(self.select_all)
        bar.addWidget(self.select_none)
        layout.addLayout(bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Kategori / Kural / Dosya", "Boyut"])
        self.tree.setColumnWidth(0, 620)
        self.tree.setAlternatingRowColors(False)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(self._reveal_item)
        layout.addWidget(self.tree, stretch=1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.hide()
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.summary_label = QLabel("Henuz tarama yapilmadi.")
        self.summary_label.setProperty("tone", "secondary")
        self.summary_label.setWordWrap(True)

        self.clean_button = ModernButton("Cop Kutusuna Tasi", "primary", "cleaner")
        self.clean_button.setFixedWidth(200)
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(lambda: self._start_clean(permanent=False))

        self.purge_button = ModernButton("Kalici Sil", "danger", "alert")
        self.purge_button.setFixedWidth(140)
        self.purge_button.setEnabled(False)
        self.purge_button.clicked.connect(lambda: self._start_clean(permanent=True))

        bottom.addWidget(self.summary_label, stretch=1)
        bottom.addWidget(self.purge_button)
        bottom.addWidget(self.clean_button)
        layout.addLayout(bottom)
        return page

    # -------------------------------------------------------------- disk
    def _refresh_disk(self):
        total, used, free = disk_usage("/")
        if not total:
            self.disk_label.setText("Disk bilgisi alinamadi")
            return
        percent = int(used / total * 100)
        self.disk_label.setText(f"Disk %{percent} dolu")
        self.disk_bar.setValue(percent)
        tone = "danger" if percent >= 90 else "warning" if percent >= 75 else "success"
        self.disk_bar.setProperty("tone", tone)
        repolish(self.disk_bar)
        self.disk_free.setText(f"{human_size(free)} bos / {human_size(total)} toplam")

    # ------------------------------------------------------------ izinler
    def _refresh_permissions(self):
        report = check_access()
        self.permission_label.setText(report.summary())

        tone = "success" if report.is_sufficient else "warning"
        self.permission_label.setProperty("tone", tone)
        repolish(self.permission_label)

        color = Colors.SUCCESS if report.is_sufficient else Colors.WARNING
        self.permission_icon.setPixmap(icons.pixmap("shield", color, 18))
        self.grant_button.setVisible(not report.full_disk_access)

    @Slot()
    def _request_access(self):
        prompt_native_dialogs()
        self._refresh_permissions()
        if check_access().full_disk_access:
            notify(self, "Full Disk Access verildi.", "success")
            return

        open_privacy_settings("full_disk")

        # macOS izni, uygulamayi baslatan surece atar. Terminal'den calisiyorsak
        # listede 'Python' degil 'Terminal' gorunur - kullaniciya dogru adi soyle.
        responsible = identify_responsible()
        QMessageBox.information(
            self,
            "Izin Gerekiyor",
            "System Settings acildi.\n\n" + responsible.instructions(),
        )

    # ------------------------------------------------------------ tarama
    @Slot()
    def _start_scan(self):
        self._cancel = threading.Event()
        self.scan_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.clean_button.setEnabled(False)
        self.purge_button.setEnabled(False)
        self.tree.clear()

        deep = self.deep_check.isChecked()
        self.progress.setRange(0, len(active_rules(deep, RULES)))
        self.progress.setValue(0)
        self.progress.show()

        self._scan_worker = ScanWorker(deep, self._cancel, self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished_scan.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    @Slot()
    def _stop_scan(self):
        self._cancel.set()
        self.stop_button.setEnabled(False)
        self.summary_label.setText("Durduruluyor...")

    @Slot(int, int, str)
    def _on_scan_progress(self, index, total, label):
        self.progress.setValue(index)
        self.progress.setFormat(f"Taraniyor: {label} ({index}/{total})")

    @Slot(str)
    def _on_scan_failed(self, message):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.summary_label.setText(f"Tarama basarisiz: {message}")
        notify(self, f"Tarama basarisiz: {message}", "danger")

    @Slot(list)
    def _on_scan_finished(self, results):
        self._results = results
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._populate_tree(results)
        self._refresh_disk()

    def _populate_tree(self, results: list[ScanResult]):
        self.tree.blockSignals(True)
        self.tree.clear()

        by_category: dict[str, list[ScanResult]] = {}
        for result in results:
            if result.items:
                by_category.setdefault(result.rule.category, []).append(result)

        ordered = [c for c in CATEGORY_ORDER if c in by_category]
        ordered += [c for c in by_category if c not in CATEGORY_ORDER]

        grand_total = 0
        for category in ordered:
            group = by_category[category]
            category_total = sum(result.total_size for result in group)
            grand_total += category_total

            top = QTreeWidgetItem(self.tree)
            top.setText(0, category)
            top.setText(1, human_size(category_total))
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            top.setCheckState(0, Qt.Unchecked)
            top.setExpanded(True)

            for result in group:
                rule = result.rule
                node = QTreeWidgetItem(top)
                node.setText(0, f"{rule.label}  —  {rule.description}")
                node.setText(1, result.pretty_size)
                node.setFlags(node.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                node.setData(0, _ROLE_RISK, rule.risk)
                node.setForeground(0, self._risk_brush(rule.risk))
                node.setToolTip(0, f"{len(result.items)} oge · risk: {rule.risk}")

                for item in result.items[:VISIBLE_PER_RULE]:
                    child = QTreeWidgetItem(node)
                    child.setText(0, str(item.path))
                    child.setText(1, human_size(item.size))
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.Unchecked)
                    child.setData(0, _ROLE_ITEM, item)
                    child.setData(0, _ROLE_PATH, str(item.path))

                remainder = result.items[VISIBLE_PER_RULE:]
                if remainder:
                    extra = QTreeWidgetItem(node)
                    extra.setText(0, f"... ve {len(remainder)} oge daha")
                    extra.setText(1, human_size(sum(i.size for i in remainder)))
                    extra.setFlags(extra.flags() | Qt.ItemIsUserCheckable)
                    extra.setCheckState(0, Qt.Unchecked)
                    extra.setData(0, _ROLE_ITEMS, remainder)

                # varsayilan secim: kural onerisine gore
                node.setCheckState(0, Qt.Checked if rule.enabled_by_default else Qt.Unchecked)

        self.tree.blockSignals(False)
        self.tree.setSortingEnabled(False)

        if not ordered:
            self.summary_label.setText("Temiz gorunuyor - silinecek bir sey bulunamadi.")
            self.clean_button.setEnabled(False)
            self.purge_button.setEnabled(False)
            return

        self._update_summary(prefix=f"Toplam {human_size(grand_total)} aday bulundu. ")

    @staticmethod
    def _risk_brush(risk: str) -> QColor:
        return QColor(Colors.risk(risk))

    # -------------------------------------------------------------- secim
    def _bulk_select(self, mode: str):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                rule_node = top.child(j)
                risk = rule_node.data(0, _ROLE_RISK)
                if mode == "all":
                    state = Qt.Checked
                elif mode == "none":
                    state = Qt.Unchecked
                else:
                    state = Qt.Checked if risk == "safe" else Qt.Unchecked
                rule_node.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._update_summary()

    def _apply_filter(self, text: str):
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            category_visible = False
            for j in range(top.childCount()):
                rule_node = top.child(j)
                rule_text = rule_node.text(0).lower()
                rule_hit = not needle or needle in rule_text
                child_hit = False
                for k in range(rule_node.childCount()):
                    child = rule_node.child(k)
                    hit = not needle or needle in child.text(0).lower()
                    child.setHidden(not (rule_hit or hit))
                    child_hit = child_hit or hit
                visible = rule_hit or child_hit
                rule_node.setHidden(not visible)
                category_visible = category_visible or visible
            top.setHidden(not category_visible)

    @Slot(QTreeWidgetItem, int)
    def _on_item_changed(self, item, column):
        if column == 0:
            self._update_summary()

    @Slot(QTreeWidgetItem, int)
    def _reveal_item(self, item, _column):
        path = item.data(0, _ROLE_PATH)
        if path:
            reveal_in_finder(Path(path))

    def _selected_items(self) -> list[JunkItem]:
        selected: list[JunkItem] = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                rule_node = top.child(j)
                for k in range(rule_node.childCount()):
                    child = rule_node.child(k)
                    if child.checkState(0) != Qt.Checked:
                        continue
                    single = child.data(0, _ROLE_ITEM)
                    if single is not None:
                        selected.append(single)
                        continue
                    bulk = child.data(0, _ROLE_ITEMS)
                    if bulk:
                        selected.extend(bulk)
        return selected

    def _has_risky_selection(self) -> bool:
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                rule_node = top.child(j)
                if rule_node.data(0, _ROLE_RISK) != "danger":
                    continue
                if rule_node.checkState(0) in (Qt.Checked, Qt.PartiallyChecked):
                    return True
        return False

    def _update_summary(self, prefix: str = ""):
        selected = self._selected_items()
        total = sum(item.size for item in selected)
        enabled = bool(selected)
        self.clean_button.setEnabled(enabled)
        self.purge_button.setEnabled(enabled)

        if not selected:
            self.summary_label.setText(prefix + "Secili oge yok.")
        else:
            self.summary_label.setText(
                f"{prefix}{len(selected)} oge secili — {human_size(total)} kazanilacak."
            )

    # ----------------------------------------------------------- temizlik
    def _start_clean(self, permanent: bool = False):
        selected = self._selected_items()
        if not selected:
            return
        total = sum(item.size for item in selected)

        if permanent or self._has_risky_selection() or settings.get("confirm_destructive"):
            if permanent:
                body = (
                    f"{len(selected)} oge KALICI olarak silinecek ({human_size(total)}).\n\n"
                    "Cop kutusuna gitmez, geri alinamaz. Emin misin?"
                )
            else:
                body = (
                    f"{len(selected)} oge cop kutusuna tasinacak ({human_size(total)}).\n\n"
                    "Cop kutusundan geri alabilirsin. Devam edilsin mi?"
                )
            if self._has_risky_selection():
                body += "\n\nDikkat: yuksek riskli bir kategori secili (yedek/indirilenler)."

            answer = QMessageBox.question(
                self, "Kalici Silmeyi Onayla" if permanent else "Temizligi Onayla",
                body, QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        self._cancel = threading.Event()
        self.clean_button.setEnabled(False)
        self.purge_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.progress.setRange(0, len(selected))
        self.progress.setValue(0)
        self.progress.setFormat("Temizleniyor: %v/%m")
        self.progress.show()
        self.summary_label.setText("Temizleniyor...")

        self._clean_worker = CleanWorker(selected, permanent=permanent,
                                         cancel=self._cancel, parent=self)
        self._clean_worker.progress.connect(lambda i, _t: self.progress.setValue(i))
        self._clean_worker.finished_clean.connect(self._on_clean_finished)
        self._clean_worker.start()

    @Slot(int, list)
    def _on_clean_finished(self, freed, errors):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        message = f"{human_size(freed)} temizlendi."
        if errors:
            message += f" {len(errors)} oge atlandi."
        self.summary_label.setText(message)
        notify(self, message, "warning" if errors else "success")
        self.tree.clear()
        self._results = []
        self.clean_button.setEnabled(False)
        self.purge_button.setEnabled(False)
        self._refresh_disk()

        if errors:
            QMessageBox.warning(
                self, "Bazi Ogeler Atlandi",
                "\n".join(errors[:15])
                + ("\n..." if len(errors) > 15 else "")
                + "\n\nIzin hatalari icin Full Disk Access verildiginden emin ol.",
            )

    def closeEvent(self, event):
        # Tarama veya temizlik surerken widget yok edilirse Qt abort eder.
        self._cancel.set()
        stop_worker(self._scan_worker)
        stop_worker(self._clean_worker)
        for tab in (self.large_tab, self.duplicates_tab, self.maintenance_tab):
            tab.stop()
        super().closeEvent(event)
