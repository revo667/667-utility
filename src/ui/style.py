def get_stylesheet() -> str:
    return """
    QWidget {
        color: #F5F2FF;
        font-family: 'Segoe UI';
        font-size: 14px;
    }

    QMainWindow, #RootWidget {
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 #0B0714,
            stop: 1 #1A1033
        );
    }

    #Sidebar {
        background: rgba(12, 8, 24, 0.75);
        border: 1px solid rgba(167, 139, 250, 0.2);
        border-radius: 16px;
        padding: 10px;
        margin: 8px;
    }

    QListWidget::item {
        border-radius: 10px;
        padding: 10px 12px;
        color: #CDBDF3;
    }

    QListWidget::item:selected {
        background: rgba(168, 85, 247, 0.25);
        border: 1px solid rgba(168, 85, 247, 0.45);
        color: #F5F2FF;
    }

    #PageTitle {
        font-size: 42px;
        font-weight: 700;
        color: #F5F2FF;
    }

    #PageSubtitle {
        font-size: 15px;
        color: #B7A9D6;
        margin-bottom: 6px;
    }

    #SectionTitle {
        font-size: 18px;
        font-weight: 600;
        color: #E9DDFD;
        margin-top: 8px;
    }

    #StatCard {
        background: rgba(20, 14, 38, 0.78);
        border: 1px solid rgba(167, 139, 250, 0.26);
        border-radius: 16px;
        padding: 14px;
    }

    #StatCard:hover {
        background: rgba(31, 21, 56, 0.9);
        border: 1px solid rgba(168, 85, 247, 0.45);
    }

    #CardTitle {
        font-size: 13px;
        color: #B7A9D6;
    }

    #CardValue {
        font-size: 36px;
        font-weight: 700;
        color: #F5F2FF;
    }

    #ActionCard {
        background: rgba(20, 14, 38, 0.72);
        border: 1px solid rgba(167, 139, 250, 0.24);
        border-radius: 14px;
        padding: 12px;
    }

    #ActionCard:hover {
        background: rgba(31, 21, 56, 0.88);
        border: 1px solid rgba(168, 85, 247, 0.48);
    }

    #ActionTitle {
        font-size: 15px;
        font-weight: 600;
        color: #F5F2FF;
    }

    #ActionSubtitle {
        font-size: 12px;
        color: #B7A9D6;
    }
    """