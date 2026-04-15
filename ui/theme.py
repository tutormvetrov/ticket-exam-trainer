from __future__ import annotations

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget


SPACING = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 20,
    "xl": 24,
    "2xl": 32,
}

RADII = {
    "sm": 10,
    "md": 14,
    "lg": 18,
    "xl": 22,
}

FONT_PRESETS = {
    "segoe": {
        "label": "Segoe UI",
        "description": "Нейтральный системный шрифт для долгой работы.",
        "families": ["Segoe UI", "Arial", "Helvetica Neue"],
    },
    "bahnschrift": {
        "label": "Bahnschrift",
        "description": "Более собранный и современный акцент без декоративности.",
        "families": ["Bahnschrift", "Segoe UI", "Arial"],
    },
    "trebuchet": {
        "label": "Trebuchet MS",
        "description": "Чуть более живой гуманистический гротеск.",
        "families": ["Trebuchet MS", "Segoe UI", "Arial"],
    },
    "verdana": {
        "label": "Verdana",
        "description": "Максимально читабельный вариант для плотного текста.",
        "families": ["Verdana", "Segoe UI", "Arial"],
    },
    "arial": {
        "label": "Arial",
        "description": "Классический запасной нейтральный вариант.",
        "families": ["Arial", "Segoe UI", "Helvetica Neue"],
    },
}

LIGHT = {
    "app_bg": "#EEF3F8",
    "sidebar_bg": "#F3F7FB",
    "surface_bg": "#F8FBFE",
    "card_bg": "#FFFFFF",
    "card_soft": "#F5F8FC",
    "card_muted": "#F8FAFD",
    "input_bg": "#FBFCFE",
    "primary": "#2E78E6",
    "primary_soft": "#EEF5FF",
    "primary_hover": "#246AD0",
    "success": "#18B06A",
    "success_soft": "#EAF9F1",
    "warning": "#F59A23",
    "warning_soft": "#FFF4E7",
    "danger": "#F26C7F",
    "danger_soft": "#FFF0F2",
    "violet_soft": "#F5EEFF",
    "cyan_soft": "#ECFAFE",
    "text": "#1F2A3B",
    "text_secondary": "#5F6B7A",
    "text_tertiary": "#8E99A8",
    "border": "#E4EAF2",
    "border_strong": "#D4DEEA",
    "shadow": QColor(23, 40, 74, 24),
}


DARK = {
    "app_bg": "#1D2734",
    "sidebar_bg": "#222E3B",
    "surface_bg": "#263343",
    "card_bg": "#2B394A",
    "card_soft": "#324255",
    "card_muted": "#314154",
    "input_bg": "#304052",
    "primary": "#4C94FF",
    "primary_soft": "#243A58",
    "primary_hover": "#6CA8FF",
    "success": "#37C983",
    "success_soft": "#1E4335",
    "warning": "#F5B14D",
    "warning_soft": "#4B3921",
    "danger": "#F58B98",
    "danger_soft": "#4A2830",
    "violet_soft": "#3E3558",
    "cyan_soft": "#274852",
    "text": "#F4F7FB",
    "text_secondary": "#D0D8E3",
    "text_tertiary": "#97A7BA",
    "border": "#415163",
    "border_strong": "#566679",
    "shadow": QColor(6, 12, 18, 70),
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def resolve_font_family(preset_key: str) -> str:
    preset = FONT_PRESETS.get(preset_key, FONT_PRESETS[DEFAULT_FONT_PRESET])
    available = set(QFontDatabase.families())
    for family in preset["families"]:
        if family in available:
            return family
    return QFont().defaultFamily()


def build_typography(font_preset: str, font_size: int) -> dict[str, int | str]:
    base_point = _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18)
    body_px = _clamp(round(base_point * 1.4), 13, 22)
    return {
        "family": resolve_font_family(font_preset),
        "base_point": base_point,
        "window_title": _clamp(body_px, 13, 18),
        "brand_title": _clamp(body_px + 8, 22, 34),
        "brand_subtitle": _clamp(body_px - 1, 12, 18),
        "nav_caption": _clamp(body_px - 1, 12, 17),
        "hero": _clamp(body_px + 12, 24, 34),
        "page_subtitle": _clamp(body_px, 13, 20),
        "section_title": _clamp(body_px + 2, 16, 24),
        "card_title": _clamp(body_px + 1, 15, 22),
        "body": body_px,
        "muted": _clamp(body_px - 1, 12, 18),
        "pill": _clamp(body_px - 2, 11, 16),
        "status": _clamp(body_px - 1, 12, 18),
        "search": _clamp(body_px + 1, 14, 22),
        "input": body_px,
        "button": body_px,
        "editor": body_px,
        "combo": body_px,
    }


def app_font(font_preset: str = DEFAULT_FONT_PRESET, font_size: int = DEFAULT_FONT_SIZE) -> QFont:
    font = QFont(resolve_font_family(font_preset), _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18))
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def apply_shadow(widget: QWidget, color: QColor, blur: int = 28, y_offset: int = 5) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(QPointF(0, y_offset))
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


def set_app_theme(
    app: QApplication,
    palette_name: str,
    font_preset: str = DEFAULT_FONT_PRESET,
    font_size: int = DEFAULT_FONT_SIZE,
) -> dict:
    palette = LIGHT if palette_name == "light" else DARK
    typography = build_typography(font_preset, font_size)
    app.setProperty("theme_palette_name", palette_name)
    app.setFont(app_font(font_preset, font_size))
    app.setStyleSheet(build_stylesheet(palette, typography))
    return palette


def current_palette_name() -> str:
    app = QApplication.instance()
    if app is None:
        return "light"
    value = str(app.property("theme_palette_name") or "").strip().lower()
    return "dark" if value == "dark" else "light"


def current_colors() -> dict:
    return DARK if current_palette_name() == "dark" else LIGHT


def is_dark_palette() -> bool:
    return current_palette_name() == "dark"


def alpha_color(hex_color: str, alpha: float) -> str:
    color = QColor(hex_color)
    color.setAlphaF(max(0.0, min(1.0, alpha)))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def build_stylesheet(colors: dict, typography: dict[str, int | str]) -> str:
    family = typography["family"]
    return f"""
    QWidget {{
        color: {colors["text"]};
        font-family: "{family}";
        background: transparent;
    }}
    QWidget#AppShell {{
        background: {colors["app_bg"]};
    }}
    QMessageBox {{
        background: {colors["card_bg"]};
    }}
    QMessageBox QLabel {{
        color: {colors["text"]};
        background: transparent;
        font-size: {typography["body"]}px;
    }}
    QMessageBox QPushButton {{
        min-width: 92px;
    }}
    QFrame[role="titlebar"] {{
        background: {colors["card_bg"]};
        border-bottom: 1px solid {colors["border"]};
    }}
    QFrame[role="sidebar"] {{
        background: {colors["sidebar_bg"]};
        border-right: 1px solid {colors["border"]};
    }}
    QFrame[role="search-shell"] {{
        background: {colors["input_bg"]};
        border: 1px solid {colors["border_strong"]};
        border-radius: 15px;
    }}
    QFrame[role="editor-shell"] {{
        background: {colors["input_bg"]};
        border: 1px solid {colors["border_strong"]};
        border-radius: 16px;
    }}
    QFrame[role="surface"] {{
        background: {colors["surface_bg"]};
    }}
    QFrame[role="card"] {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["border"]};
        border-radius: 20px;
    }}
    QFrame[role="subtle-card"] {{
        background: {colors["card_soft"]};
        border: 1px solid {colors["border"]};
        border-radius: 16px;
    }}
    QFrame[role="mode-card"] {{
        border-radius: 16px;
        border: 1px solid {colors["border"]};
        background: {colors["card_bg"]};
    }}
    QFrame[role="document-item"] {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["border"]};
        border-radius: 18px;
    }}
    QFrame[role="document-item"][selected="true"] {{
        background: {colors["primary_soft"]};
        border: 1px solid {colors["primary"]};
    }}
    QFrame[role="table-row"] {{
        background: {colors["card_bg"]};
        border-bottom: 1px solid {colors["border"]};
    }}
    QLabel[role="window-title"] {{
        font-size: {typography["window_title"]}px;
        font-weight: 700;
    }}
    QLabel[role="brand-title"] {{
        font-size: {typography["brand_title"]}px;
        font-weight: 800;
        color: {colors["text"]};
    }}
    QLabel[role="brand-subtitle"] {{
        color: {colors["text_secondary"]};
        font-size: {typography["brand_subtitle"]}px;
    }}
    QLabel[role="nav-caption"] {{
        color: {colors["text_tertiary"]};
        font-size: {typography["nav_caption"]}px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel[role="hero"] {{
        font-size: {typography["hero"]}px;
        font-weight: 800;
        color: {colors["text"]};
    }}
    QLabel[role="page-subtitle"] {{
        color: {colors["text_secondary"]};
        font-size: {typography["page_subtitle"]}px;
    }}
    QLabel[role="section-title"] {{
        font-size: {typography["section_title"]}px;
        font-weight: 700;
        color: {colors["text"]};
    }}
    QLabel[role="card-title"] {{
        font-size: {typography["card_title"]}px;
        font-weight: 700;
    }}
    QLabel[role="body"] {{
        color: {colors["text_secondary"]};
        font-size: {typography["body"]}px;
    }}
    QLabel[role="muted"] {{
        color: {colors["text_tertiary"]};
        font-size: {typography["muted"]}px;
    }}
    QLabel[role="pill"] {{
        background: {colors["card_soft"]};
        color: {colors["text_secondary"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: {typography["pill"]}px;
        font-weight: 600;
    }}
    QLabel[role="status-ok"] {{
        color: {colors["success"]};
        font-size: {typography["status"]}px;
        font-weight: 600;
    }}
    QLineEdit[role="search"] {{
        background: {colors["input_bg"]};
        border: 1px solid {colors["border_strong"]};
        border-radius: 14px;
        padding: 12px 14px;
        font-size: {typography["search"]}px;
    }}
    QLineEdit[role="search-plain"] {{
        background: transparent;
        border: none;
        padding: 0 14px 0 0;
        font-size: {typography["search"]}px;
    }}
    QLineEdit[role="search"]:focus,
    QLineEdit[role="form-input"]:focus {{
        border: 1px solid {colors["primary"]};
    }}
    QLineEdit[role="form-input"] {{
        background: {colors["input_bg"]};
        color: {colors["text"]};
        border: 1px solid {colors["border_strong"]};
        border-radius: 12px;
        padding: 10px 12px;
        font-size: {typography["input"]}px;
        min-height: 20px;
    }}
    QTextEdit[role="editor"] {{
        background: transparent;
        color: {colors["text"]};
        border: none;
        padding: 4px 6px;
        font-size: {typography["editor"]}px;
        line-height: 1.4;
    }}
    QTextEdit[role="editor"]:focus {{
        border: none;
    }}
    QComboBox {{
        background: {colors["input_bg"]};
        color: {colors["text"]};
        border: 1px solid {colors["border_strong"]};
        border-radius: 12px;
        padding: 9px 12px;
        min-height: 20px;
        font-size: {typography["combo"]}px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["border"]};
        selection-background-color: {colors["primary_soft"]};
        selection-color: {colors["text"]};
        padding: 6px;
    }}
    QPushButton {{
        border-radius: 14px;
        border: 1px solid {colors["border"]};
        background: {colors["card_bg"]};
        padding: 11px 16px;
        font-size: {typography["button"]}px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        border-color: {colors["border_strong"]};
    }}
    QPushButton[variant="primary"] {{
        background: {colors["primary"]};
        color: white;
        border: 1px solid {colors["primary"]};
        padding: 11px 18px;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {colors["primary_hover"]};
        border-color: {colors["primary_hover"]};
    }}
    QPushButton[variant="secondary"] {{
        background: {colors["card_soft"]};
        color: {colors["text_secondary"]};
    }}
    QPushButton[variant="toolbar"] {{
        background: {colors["card_muted"]};
        padding: 10px 16px;
        color: {colors["text"]};
    }}
    QPushButton[variant="toolbar-ghost"] {{
        background: {colors["card_muted"]};
        padding: 10px 12px;
        min-width: 20px;
    }}
    QPushButton[variant="outline"] {{
        background: {colors["card_bg"]};
        color: {colors["text_secondary"]};
        padding: 11px 18px;
    }}
    QPushButton[variant="nav"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {colors["text"]};
        text-align: left;
        padding: 12px 16px;
        font-size: {typography["button"]}px;
        font-weight: 600;
    }}
    QPushButton[variant="nav"]:hover {{
        background: {colors["card_muted"]};
        border-color: {colors["border"]};
    }}
    QPushButton[variant="nav"]:checked {{
        background: {colors["primary"]};
        color: white;
        border-color: {colors["primary"]};
    }}
    QPushButton[variant="tab"] {{
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 12px 2px 10px 2px;
        color: {colors["text_secondary"]};
        font-size: {typography["body"]}px;
        font-weight: 600;
    }}
    QPushButton[variant="tab"]:checked {{
        color: {colors["primary"]};
        border-bottom: 2px solid {colors["primary"]};
    }}
    QPushButton[variant="settings-nav"] {{
        background: transparent;
        border: none;
        border-left: 4px solid transparent;
        border-radius: 0;
        text-align: left;
        padding: 14px 18px;
        color: {colors["text"]};
    }}
    QPushButton[variant="settings-nav"]:checked {{
        background: {colors["primary_soft"]};
        border-left: 4px solid {colors["primary"]};
    }}
    QLabel[debugText="true"] {{
        background: rgba(3, 199, 126, 0.08);
        border-radius: 5px;
    }}
    QPushButton[debugText="true"],
    QLineEdit[debugText="true"],
    QComboBox[debugText="true"] {{
        border: 1px dashed #03C77E;
    }}
    QToolButton {{
        border: none;
        background: transparent;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 10px;
        margin: 4px 0 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {colors["border_strong"]};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """
