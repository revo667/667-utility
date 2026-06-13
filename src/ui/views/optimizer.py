from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame


class OptimizerView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("OptimizerView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title_label = QLabel("Optimizer")
        title_label.setObjectName("PageTitle")

        subtitle_label = QLabel("Choose Tweaks")
        subtitle_label.setObjectName("PageSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        