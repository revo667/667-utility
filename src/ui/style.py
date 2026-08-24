from src.ui.theme import Colors

FONT_STACK = (
    "'JetBrainsMono Nerd Font', 'JetBrains Mono', 'SF Mono', "
    "'Menlo', 'Consolas', monospace"
)


def get_stylesheet() -> str:
    return f"""
    QWidget {{
        color: {Colors.TEXT_PRIMARY};
        font-family: {FONT_STACK};
        font-size: 14px;
    }}

    QMainWindow, #RootWidget {{
        background: rgba(12, 8, 24, 0.75);
    }}

    #SidebarContainer {{
        background: transparent;
    }}

    #Sidebar {{
        background: rgba(12, 8, 30, 0.75);
        border: 1px solid {Colors.BORDER};
        border-radius: 16px;
        padding: 10px;
        margin: 8px;
    }}

    QListWidget::item {{
        border-radius: 10px;
        padding: 10px 12px;
        color: #CDBDF3;
    }}

    QListWidget::item:selected {{
        background: rgba(168, 85, 247, 0.25);
        border: 1px solid {Colors.BORDER_STRONG};
        color: {Colors.TEXT_PRIMARY};
    }}

    QListWidget::item:disabled {{
        color: {Colors.TEXT_MUTED};
    }}

    #SidebarFooter {{
        font-size: 11px;
        padding: 4px 4px 12px 4px;
        background: transparent;
    }}

    #PageTitle {{
        font-size: 42px;
        font-weight: 700;
        color: {Colors.TEXT_PRIMARY};
    }}

    #PageSubtitle {{
        font-size: 15px;
        color: {Colors.TEXT_SECONDARY};
        margin-bottom: 6px;
    }}

    #SectionTitle {{
        font-size: 18px;
        font-weight: 600;
        color: #E9DDFD;
        margin-top: 8px;
    }}

    #StatCard {{
        background: {Colors.CARD};
        border: 1px solid {Colors.BORDER};
        border-radius: 16px;
    }}

    #StatCard:hover {{
        background: {Colors.CARD_HOVER};
        border: 1px solid {Colors.BORDER_STRONG};
    }}

    #CardTitle {{
        font-size: 13px;
        color: {Colors.TEXT_SECONDARY};
    }}

    #CardValue {{
        font-size: 32px;
        font-weight: 700;
        color: {Colors.TEXT_PRIMARY};
    }}

    QProgressBar {{
        background: rgba(167, 139, 250, 0.15);
        border: none;
        border-radius: 3px;
    }}

    QProgressBar::chunk {{
        background: {Colors.ACCENT};
        border-radius: 3px;
    }}

    QLineEdit {{
        background: rgba(20, 14, 38, 0.85);
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px 12px;
        color: {Colors.TEXT_PRIMARY};
    }}

    QLineEdit:focus {{
        border: 1px solid {Colors.ACCENT};
    }}

    QListWidget, QTreeWidget, QTextEdit {{
        background: rgba(16, 11, 32, 0.7);
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        padding: 6px;
    }}

    QHeaderView::section {{
        background: transparent;
        color: {Colors.TEXT_SECONDARY};
        border: none;
        padding: 6px;
    }}

    QCheckBox {{
        color: {Colors.TEXT_SECONDARY};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}

    QScrollBar::handle:vertical {{
        background: rgba(167, 139, 250, 0.35);
        border-radius: 4px;
    }}

    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0px;
    }}
    """
