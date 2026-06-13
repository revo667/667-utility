from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame


class StatCard(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)


class ActionCard(QFrame):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setObjectName("ActionCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("ActionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ActionSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("Dashboard")
        header.setObjectName("PageTitle")

        subtitle = QLabel("Optimizer ve Uninstaller akışlarını buradan yönet")
        subtitle.setObjectName("PageSubtitle")

        stat_grid = QGridLayout()
        stat_grid.setHorizontalSpacing(16)
        stat_grid.setVerticalSpacing(16)
        stat_grid.addWidget(StatCard("Installed Apps", "0"), 0, 0)
        stat_grid.addWidget(StatCard("Pending Tweaks", "0"), 0, 1)
        stat_grid.addWidget(StatCard("Restore Points", "0"), 1, 0)

        section = QLabel("Hızlı Erişim")
        section.setObjectName("SectionTitle")

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(16)
        action_grid.setVerticalSpacing(16)
        action_grid.addWidget(ActionCard("Uygulama Yükle", "Winget ile hızlı kurulum"), 0, 0)
        action_grid.addWidget(ActionCard("Program Kaldır", "Kurulu uygulamaları kaldır"), 0, 1)
        action_grid.addWidget(ActionCard("Tweak Uygula", "Performans tweaklerini çalıştır"), 1, 0)
        action_grid.addWidget(ActionCard("Restore Point", "Geri dönüş noktası oluştur"), 1, 1)

        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addLayout(stat_grid)
        layout.addWidget(section)
        layout.addLayout(action_grid)