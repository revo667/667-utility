"""Merkezi QSS.

Kural: widget'lar inline setStyleSheet() cagirmaz. Gorunum farki gerekiyorsa
Qt property'si set edilir (ornek: setProperty("variant", "danger")) ve secici
buraya yazilir. Boylece tum renkler tek dosyada kalir ve tema degistirmek
tek noktadan mumkun olur.

Property degistiginde Qt otomatik yeniden boyamaz - repolish() cagir.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from src.ui.theme import Colors, Radius, Spacing, Type


def repolish(widget: QWidget) -> None:
    """Property degistikten sonra stilin yeniden uygulanmasini saglar."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def get_stylesheet() -> str:
    c, r, s, t = Colors, Radius, Spacing, Type

    return f"""
    /* ============================================================ temel */
    QWidget {{
        color: {c.TEXT_PRIMARY};
        font-family: {t.UI_STACK};
        font-size: {t.BODY}px;
    }}

    QMainWindow, #RootWidget {{
        background: {c.BG_BASE};
    }}

    #ContentArea {{
        background: transparent;
    }}

    /* ========================================================== sidebar */
    #SidebarContainer {{
        background: {c.BG_SURFACE};
        border-right: 1px solid {c.BORDER};
    }}

    #BrandName {{
        font-size: {t.HEADING}px;
        font-weight: 700;
        color: {c.TEXT_PRIMARY};
        letter-spacing: 0.4px;
    }}

    #BrandMeta {{
        font-size: {t.CAPTION}px;
        color: {c.TEXT_MUTED};
    }}

    #SidebarSection {{
        font-size: {t.CAPTION}px;
        font-weight: 600;
        color: {c.TEXT_MUTED};
        letter-spacing: 1.1px;
        padding: {s.MD}px {s.MD}px {s.XS}px {s.MD}px;
    }}

    #Sidebar {{
        background: transparent;
        border: none;
        outline: none;
        padding: 0px {s.SM}px;
    }}

    #Sidebar::item {{
        border-radius: {r.MD}px;
        padding: {s.MD}px {s.MD}px;
        margin: 2px 0px;
        color: {c.TEXT_SECONDARY};
    }}

    #Sidebar::item:hover {{
        background: {c.CARD_HOVER};
        color: {c.TEXT_PRIMARY};
    }}

    #Sidebar::item:selected {{
        background: {c.ACCENT_SOFT};
        color: {c.TEXT_PRIMARY};
        font-weight: 600;
    }}

    #Sidebar::item:disabled {{
        color: {c.TEXT_MUTED};
    }}

    #SidebarFooter {{
        font-size: {t.CAPTION}px;
        color: {c.TEXT_MUTED};
        padding: {s.MD}px;
        background: transparent;
        border-top: 1px solid {c.BORDER};
    }}

    /* ====================================================== tipografi */
    #PageTitle {{
        font-size: {t.DISPLAY}px;
        font-weight: 700;
        color: {c.TEXT_PRIMARY};
        letter-spacing: -0.5px;
    }}

    #PageSubtitle {{
        font-size: {t.BODY}px;
        color: {c.TEXT_SECONDARY};
    }}

    #SectionTitle {{
        font-size: {t.HEADING}px;
        font-weight: 600;
        color: {c.TEXT_PRIMARY};
    }}

    #Caption, QLabel[role="caption"] {{
        font-size: {t.CAPTION}px;
        color: {c.TEXT_MUTED};
    }}

    QLabel[tone="secondary"] {{ color: {c.TEXT_SECONDARY}; }}
    QLabel[tone="muted"]     {{ color: {c.TEXT_MUTED}; }}
    QLabel[tone="success"]   {{ color: {c.SUCCESS}; }}
    QLabel[tone="warning"]   {{ color: {c.WARNING}; }}
    QLabel[tone="danger"]    {{ color: {c.DANGER}; }}
    QLabel[mono="true"]      {{ font-family: {t.MONO_STACK}; }}

    /* =========================================================== kartlar */
    #StatCard, #Card, #OptimizerCard, #AppRow, #PermissionBar {{
        background: {c.CARD};
        border: 1px solid {c.BORDER};
        border-radius: {r.LG}px;
    }}

    #StatCard:hover, #Card:hover, #OptimizerCard:hover, #AppRow:hover {{
        background: {c.CARD_HOVER};
        border: 1px solid {c.BORDER_HOVER};
    }}

    #CardTitle {{
        font-size: {t.CAPTION}px;
        font-weight: 600;
        color: {c.TEXT_MUTED};
        letter-spacing: 0.8px;
    }}

    #CardValue {{
        font-size: 26px;
        font-weight: 700;
        color: {c.TEXT_PRIMARY};
        font-family: {t.MONO_STACK};
    }}

    #ItemTitle {{
        font-size: {t.BODY}px;
        font-weight: 600;
        color: {c.TEXT_PRIMARY};
    }}

    #ItemMeta {{
        font-size: {t.CAPTION}px;
        color: {c.TEXT_SECONDARY};
    }}

    /* Risk seridi - kartin solundaki ince renk cizgisi */
    #RiskStripe[risk="safe"]    {{ background: {c.SUCCESS}; border-radius: 2px; }}
    #RiskStripe[risk="warning"] {{ background: {c.WARNING}; border-radius: 2px; }}
    #RiskStripe[risk="danger"]  {{ background: {c.DANGER};  border-radius: 2px; }}

    /* =========================================================== butonlar */
    QPushButton {{
        border-radius: {r.SM}px;
        padding: 0px {s.LG}px;
        font-size: {t.BODY}px;
        font-weight: 600;
        min-height: 34px;
    }}

    QPushButton[variant="primary"] {{
        background: {c.ACCENT};
        color: #FFFFFF;
        border: 1px solid {c.ACCENT};
    }}
    QPushButton[variant="primary"]:hover {{
        background: {c.ACCENT_HOVER};
        border: 1px solid {c.ACCENT_HOVER};
    }}
    QPushButton[variant="primary"]:pressed {{
        background: {c.ACCENT_PRESSED};
        border: 1px solid {c.ACCENT_PRESSED};
    }}

    QPushButton[variant="ghost"] {{
        background: transparent;
        color: {c.TEXT_SECONDARY};
        border: 1px solid {c.BORDER};
    }}
    QPushButton[variant="ghost"]:hover {{
        background: {c.ACCENT_SOFT};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER_HOVER};
    }}
    QPushButton[variant="ghost"]:pressed {{
        background: {c.CARD_ACTIVE};
    }}

    QPushButton[variant="danger"] {{
        background: transparent;
        color: {c.DANGER};
        border: 1px solid rgba(248, 113, 113, 0.45);
    }}
    QPushButton[variant="danger"]:hover {{
        background: {c.DANGER_SOFT};
        border: 1px solid {c.DANGER};
    }}

    QPushButton[variant="subtle"] {{
        background: transparent;
        color: {c.TEXT_MUTED};
        border: none;
        font-weight: 500;
    }}
    QPushButton[variant="subtle"]:hover {{
        color: {c.TEXT_PRIMARY};
        background: {c.CARD_HOVER};
    }}

    QPushButton:disabled {{
        background: rgba(120, 100, 160, 0.10);
        color: {c.TEXT_MUTED};
        border: 1px solid transparent;
    }}

    /* Pencere kontrol butonlari (frameless baslik) */
    #WindowButton {{
        background: transparent;
        border: none;
        border-radius: {r.SM}px;
        min-height: 28px;
        min-width: 34px;
        padding: 0px;
    }}
    #WindowButton:hover {{ background: {c.CARD_HOVER}; }}
    #WindowButton[variant="close"]:hover {{ background: rgba(248, 113, 113, 0.85); }}

    #TitleBar {{
        background: transparent;
        border-bottom: 1px solid {c.BORDER};
    }}
    #TitleBarText {{
        font-size: {t.CAPTION}px;
        color: {c.TEXT_MUTED};
        font-weight: 600;
        letter-spacing: 0.6px;
    }}

    /* ============================================================ girisler */
    QLineEdit {{
        background: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        border-radius: {r.SM}px;
        padding: {s.SM}px {s.MD}px;
        color: {c.TEXT_PRIMARY};
        selection-background-color: {c.ACCENT};
        min-height: 20px;
    }}
    QLineEdit:focus {{
        border: 1px solid {c.ACCENT};
        background: {c.CARD_ACTIVE};
    }}
    QLineEdit:disabled {{
        color: {c.TEXT_MUTED};
        background: rgba(120, 100, 160, 0.06);
    }}

    QCheckBox {{
        color: {c.TEXT_SECONDARY};
        spacing: {s.SM}px;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 5px;
        border: 1px solid {c.BORDER_HOVER};
        background: transparent;
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {c.ACCENT};
    }}
    QCheckBox::indicator:checked {{
        background: {c.ACCENT};
        border: 1px solid {c.ACCENT};
    }}

    QSpinBox {{
        background: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        border-radius: {r.SM}px;
        padding: {s.XS}px {s.SM}px;
        color: {c.TEXT_PRIMARY};
        min-height: 24px;
    }}
    QSpinBox:focus {{ border: 1px solid {c.ACCENT}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 14px; border: none; }}

    /* ============================================================ listeler */
    QListWidget, QTreeWidget, QTextEdit, QPlainTextEdit {{
        background: {c.BG_SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {r.MD}px;
        padding: {s.XS}px;
        outline: none;
    }}

    QTreeWidget::item, QListWidget::item {{
        padding: {s.XS}px {s.SM}px;
        border-radius: {r.SM}px;
        color: {c.TEXT_SECONDARY};
    }}
    QTreeWidget::item:selected, QListWidget::item:selected {{
        background: {c.ACCENT_SOFT};
        color: {c.TEXT_PRIMARY};
    }}
    QTreeWidget::item:hover, QListWidget::item:hover {{
        background: {c.CARD_HOVER};
    }}

    QHeaderView::section {{
        background: transparent;
        color: {c.TEXT_MUTED};
        border: none;
        border-bottom: 1px solid {c.BORDER};
        padding: {s.SM}px {s.XS}px;
        font-size: {t.CAPTION}px;
        font-weight: 600;
        letter-spacing: 0.6px;
    }}

    /* =============================================================== tabs */
    QTabBar::tab {{
        background: transparent;
        color: {c.TEXT_MUTED};
        padding: {s.SM}px {s.LG}px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: {t.BODY}px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        color: {c.TEXT_PRIMARY};
        border-bottom: 2px solid {c.ACCENT};
    }}
    QTabBar::tab:hover {{ color: {c.TEXT_SECONDARY}; }}

    /* ========================================================== ilerleme */
    QProgressBar {{
        background: rgba(167, 139, 250, 0.12);
        border: none;
        border-radius: 3px;
        text-align: center;
        color: {c.TEXT_SECONDARY};
        font-size: {t.CAPTION}px;
    }}
    QProgressBar::chunk {{
        background: {c.ACCENT};
        border-radius: 3px;
    }}
    QProgressBar[tone="success"]::chunk {{ background: {c.SUCCESS}; }}
    QProgressBar[tone="warning"]::chunk {{ background: {c.WARNING}; }}
    QProgressBar[tone="danger"]::chunk  {{ background: {c.DANGER}; }}

    /* ============================================================ rozetler */
    #Badge {{
        border-radius: {r.PILL}px;
        padding: 3px {s.MD}px;
        font-size: {t.CAPTION}px;
        font-weight: 600;
    }}
    #Badge[tone="success"] {{ background: {c.SUCCESS_SOFT}; color: {c.SUCCESS}; }}
    #Badge[tone="warning"] {{ background: {c.WARNING_SOFT}; color: {c.WARNING}; }}
    #Badge[tone="danger"]  {{ background: {c.DANGER_SOFT};  color: {c.DANGER}; }}
    #Badge[tone="accent"]  {{ background: {c.ACCENT_SOFT};  color: {c.ACCENT}; }}

    /* ============================================================== toast */
    #Toast {{
        background: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER_HOVER};
        border-radius: {r.MD}px;
    }}
    #Toast[tone="success"] {{ border-left: 3px solid {c.SUCCESS}; }}
    #Toast[tone="warning"] {{ border-left: 3px solid {c.WARNING}; }}
    #Toast[tone="danger"]  {{ border-left: 3px solid {c.DANGER}; }}
    #Toast[tone="info"]    {{ border-left: 3px solid {c.INFO}; }}
    #ToastText {{
        color: {c.TEXT_PRIMARY};
        font-size: {t.BODY}px;
        background: transparent;
    }}

    /* =========================================================== dialoglar */
    QMessageBox {{
        background: {c.BG_SURFACE};
    }}
    QMessageBox QLabel {{
        color: {c.TEXT_PRIMARY};
    }}

    /* =========================================================== kaydirma */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(167, 139, 250, 0.28);
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(167, 139, 250, 0.48);
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(167, 139, 250, 0.28);
        border-radius: 4px;
        min-width: 28px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0px;
        width: 0px;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}

    /* ============================================================ ayirici */
    #Divider {{
        background: {c.BORDER};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}

    QToolTip {{
        background: {c.BG_ELEVATED};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER_HOVER};
        border-radius: {r.SM}px;
        padding: {s.XS}px {s.SM}px;
    }}
    """
