from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame


class UninstallerView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("UninstallerView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title_label = QLabel("Uninstall Tool")
        title_label.setObjectName("PageTitle")

        subtitle_label = QLabel("Uninstall selected programs from your computer")
        subtitle_label.setObjectName("PageSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)