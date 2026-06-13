from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget
from src.ui.views.dashboard import DashboardView
from src.ui.style import get_stylesheet
from src.ui.views.optimizer import OptimizerView
from src.ui.views.uninstaller import UninstallerView
from src.ui.views.installer import InstallerView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("667 Utility")
        self.resize(1100, 700)

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)

        self.sidebar = QListWidget()
        self.sidebar.addItems(["Dashboard", "Optimizer", "Installer", "Uninstaller"])
        self.sidebar.setFixedWidth(220)

        self.pages = QStackedWidget()
        self.dashboard = DashboardView()
        self.optimizer = OptimizerView()
        self.installer = InstallerView()
        self.uninstaller = UninstallerView()
        self.pages.addWidget(self.dashboard)
        self.pages.addWidget(self.optimizer)
        self.pages.addWidget(self.installer)
        self.pages.addWidget(self.uninstaller)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        self.setStyleSheet(get_stylesheet())