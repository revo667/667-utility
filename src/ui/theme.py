"""Tek renk/olcu kaynagi.

Kural: hicbir widget kendi rengini string olarak yazmaz. Buradan alir.
Inline setStyleSheet() gormek istemiyoruz - style.py merkezi QSS'i uretir.
"""

from __future__ import annotations


class Colors:
    # -- zemin katmanlari (arkadan one dogru)
    BG_BASE = "#0B0713"
    BG_SURFACE = "#120C21"
    BG_ELEVATED = "#1A1130"

    # -- yuzeyler
    CARD = "rgba(24, 17, 44, 0.72)"
    CARD_HOVER = "rgba(36, 25, 64, 0.88)"
    CARD_ACTIVE = "rgba(46, 32, 80, 0.95)"

    # -- kenarlar
    BORDER = "rgba(167, 139, 250, 0.16)"
    BORDER_HOVER = "rgba(167, 139, 250, 0.32)"
    BORDER_STRONG = "rgba(168, 85, 247, 0.55)"

    # -- metin
    TEXT_PRIMARY = "#F4F1FF"
    TEXT_SECONDARY = "#A99BC9"
    TEXT_MUTED = "#6E6191"

    # -- vurgu
    ACCENT = "#A855F7"
    ACCENT_SOFT = "rgba(168, 85, 247, 0.14)"
    ACCENT_HOVER = "#BE7DF9"
    ACCENT_PRESSED = "#8B3FD6"
    ACCENT_2 = "#EC4899"

    # -- durum
    SUCCESS = "#34D399"
    SUCCESS_SOFT = "rgba(52, 211, 153, 0.12)"
    WARNING = "#FBBF24"
    WARNING_SOFT = "rgba(251, 191, 36, 0.12)"
    DANGER = "#F87171"
    DANGER_SOFT = "rgba(248, 113, 113, 0.12)"
    INFO = "#60A5FA"

    #: Risk seviyesi -> renk. Kartlar ve kurallar ayni sozlugu kullanir.
    RISK = {
        "safe": SUCCESS,
        "warning": WARNING,
        "danger": DANGER,
    }

    @classmethod
    def risk(cls, level: str) -> str:
        return cls.RISK.get(level, cls.ACCENT)


class Radius:
    SM = 8
    MD = 12
    LG = 16
    XL = 22
    PILL = 999


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 20
    XL = 28
    XXL = 40


class Motion:
    """Animasyon sureleri (ms). Tek yerden ayarlanir ki ritim tutarli olsun."""

    FAST = 120
    NORMAL = 200
    SLOW = 320
    TOAST_LIFE = 3600


class Type:
    """Tipografi olcegi."""

    DISPLAY = 30
    TITLE = 20
    HEADING = 15
    BODY = 13
    CAPTION = 11

    UI_STACK = (
        "'Inter', 'SF Pro Text', 'Segoe UI Variable', 'Segoe UI', "
        "'Helvetica Neue', system-ui, sans-serif"
    )
    MONO_STACK = (
        "'JetBrainsMono Nerd Font', 'JetBrains Mono', 'SF Mono', "
        "'Cascadia Code', 'Menlo', 'Consolas', monospace"
    )
