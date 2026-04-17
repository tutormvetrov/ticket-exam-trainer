from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from ui.theme.palette import LIGHT, DARK, alpha_color
from ui.theme.typography import app_font, build_typography


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


def build_stylesheet(colors: dict, typography: dict[str, int | str]) -> str:
    family = typography["family"]
    is_dark = colors["app_bg"] == DARK["app_bg"]
    primary_pressed = QColor(colors["primary"]).darker(120 if is_dark else 114).name()
    card_pressed = QColor(colors["card_bg"]).darker(108 if is_dark else 102).name()
    secondary_hover = alpha_color(colors["primary"], 0.12 if is_dark else 0.08)
    secondary_pressed = alpha_color(colors["primary"], 0.2 if is_dark else 0.14)
    toolbar_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.06)
    toolbar_pressed = alpha_color(colors["primary"], 0.18 if is_dark else 0.12)
    nav_pressed = alpha_color(colors["primary"], 0.22 if is_dark else 0.12)
    muted_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.05)
    brass = colors.get("brass", colors.get("border_strong", colors["primary"]))
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
    QFrame[role="empty-icon-shell"] {{
        background: {colors["primary_soft"]};
        border: 1px solid {alpha_color(colors["primary"], 0.18 if is_dark else 0.1)};
        border-radius: 18px;
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
    QLabel[role="brass-dot"] {{
        color: {brass};
        font-size: 16px;
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
        background: {muted_hover};
    }}
    QPushButton:pressed {{
        background: {card_pressed};
        border-color: {colors["border_strong"]};
    }}
    QPushButton:focus {{
        border-color: {colors["primary"]};
    }}
    QPushButton:disabled {{
        background: {colors["card_muted"]};
        color: {colors["text_tertiary"]};
        border-color: {colors["border"]};
    }}
    QPushButton[variant="primary"] {{
        background: {colors["primary"]};
        color: {colors["parchment"]};
        border: 1px solid {colors["primary"]};
        padding: 11px 18px;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {colors["primary_hover"]};
        border-color: {colors["primary_hover"]};
    }}
    QPushButton[variant="primary"]:pressed {{
        background: {primary_pressed};
        border-color: {primary_pressed};
    }}
    QPushButton[variant="primary"]:focus {{
        border-color: {QColor("#CFE1FF" if not is_dark else "#9CC3FF").name()};
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {colors["border_strong"]};
        border-color: {colors["border_strong"]};
        color: {colors["card_bg"]};
    }}
    QPushButton[variant="secondary"] {{
        background: {colors["card_soft"]};
        color: {colors["text_secondary"]};
    }}
    QPushButton[variant="secondary"]:hover {{
        background: {secondary_hover};
        border-color: {colors["border_strong"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="secondary"]:pressed {{
        background: {secondary_pressed};
        border-color: {colors["primary"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="toolbar"] {{
        background: {colors["card_muted"]};
        padding: 10px 16px;
        color: {colors["text"]};
    }}
    QPushButton[variant="toolbar"]:hover,
    QPushButton[variant="toolbar-ghost"]:hover {{
        background: {toolbar_hover};
        border-color: {colors["border_strong"]};
    }}
    QPushButton[variant="toolbar"]:pressed,
    QPushButton[variant="toolbar-ghost"]:pressed {{
        background: {toolbar_pressed};
        border-color: {colors["primary"]};
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
    QPushButton[variant="outline"]:hover {{
        background: {secondary_hover};
        border-color: {colors["primary"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="outline"]:pressed {{
        background: {secondary_pressed};
        border-color: {colors["primary"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="nav"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {colors["text_secondary"]};
        text-align: left;
        padding: 12px 16px;
        font-family: "{typography["ui_family"]}";
        font-size: {typography["button"]}px;
        font-weight: 600;
    }}
    QPushButton[variant="nav"]:hover {{
        background: {colors["card_muted"]};
        border-color: {colors["border"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="nav"]:pressed {{
        background: {nav_pressed};
        border-color: {colors["primary"]};
        color: {colors["text"]};
    }}
    QPushButton[variant="nav"]:checked {{
        background: {colors["primary"]};
        color: {colors["parchment"]};
        border-color: {colors["primary"]};
    }}
    QPushButton[variant="nav"]:checked:hover,
    QPushButton[variant="nav"]:checked:pressed {{
        background: {primary_pressed};
        border-color: {primary_pressed};
        color: {colors["parchment"]};
    }}
    QPushButton[variant="nav"]:disabled {{
        background: transparent;
        border-color: transparent;
        color: {colors["text_tertiary"]};
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
    QPushButton[variant="tab"]:hover {{
        color: {colors["text"]};
        border-bottom: 2px solid {colors["border_strong"]};
    }}
    QPushButton[variant="tab"]:pressed {{
        color: {colors["primary"]};
        border-bottom: 2px solid {colors["primary"]};
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
    QPushButton[variant="settings-nav"]:hover {{
        background: {colors["card_muted"]};
        border-left: 4px solid {colors["border_strong"]};
    }}
    QPushButton[variant="settings-nav"]:pressed {{
        background: {secondary_pressed};
        border-left: 4px solid {colors["primary"]};
    }}
    QPushButton[variant="settings-nav"]:checked {{
        background: {colors["primary_soft"]};
        border-left: 4px solid {colors["primary"]};
    }}
    QPushButton[variant="settings-nav"]:disabled,
    QPushButton[variant="tab"]:disabled {{
        color: {colors["text_tertiary"]};
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
    QFrame[role="folio-card"] {{
        background: transparent;
        border: none;
    }}
    QFrame[role="atelier-card"] {{
        background: {colors["parchment"]};
        border: 1px solid {colors["border"]};
        border-radius: 12px;
    }}
    QFrame[role="paper-card"] {{
        background: {colors["paper"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
    }}
    QLabel[role="eyebrow"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["eyebrow"]}px;
        color: {colors["rust"]};
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
    }}
    QLabel[role="metric-value"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["metric_value"]}px;
        color: {colors["moss"]};
        font-weight: 700;
    }}
    QLabel[role="metric-label"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["metric_label"]}px;
        color: {colors["ink_muted"]};
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}
    QLabel[role="subtitle-italic"] {{
        font-family: "{family}";
        font-size: {typography["subtitle"]}px;
        font-style: italic;
        color: {colors["ink_muted"]};
    }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {colors["ink_muted"]};
        padding: 9px 16px;
        font-family: "{typography["ui_family"]}";
    }}
    QPushButton[variant="ghost"]:hover {{
        color: {colors["rust"]};
        background: {colors["rust_soft"]};
    }}
    QPushButton[variant="ghost"]:pressed {{
        background: {colors["rust_soft"]};
        color: {colors["rust_hover"]};
    }}
    QPushButton[variant="danger"] {{
        background: {colors["claret"]};
        border: 1px solid {colors["claret"]};
        color: {colors["parchment"]};
        padding: 9px 16px;
        font-family: "{typography["ui_family"]}";
        font-weight: 600;
    }}
    QPushButton[variant="danger"]:hover {{
        background: {QColor(colors["claret"]).darker(110).name()};
    }}
    QPushButton[variant="nav"][active-warm="true"] {{
        background: transparent;
        border: none;
        border-left: 3px solid {colors["rust"]};
        color: {colors["ink"]};
        font-family: "{family}";
        font-size: {typography["nav_caption"]}px;
        font-weight: 600;
        padding-left: 13px;
    }}
    QPushButton[variant="nav"][active-warm="true"]:hover,
    QPushButton[variant="nav"][active-warm="true"]:pressed {{
        background: transparent;
        border: none;
        border-left: 3px solid {colors["rust"]};
        color: {colors["ink"]};
        padding-left: 13px;
    }}
    """
