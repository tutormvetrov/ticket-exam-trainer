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
    ui_family = typography["ui_family"]
    is_dark = colors["app_bg"] == DARK["app_bg"]
    page_title_size = typography.get("page_title", typography.get("hero", typography["section_title"]))
    chrome_title_size = max(int(typography["section_title"]), int(page_title_size) - 2)
    chrome_subtitle_size = max(int(typography["muted"]), int(typography["subtitle"]) - 1)
    paper = colors.get("paper", colors["app_bg"])
    sand = colors.get("sand", colors.get("sidebar_bg", colors["card_soft"]))
    rust = colors.get("rust", colors["primary"])
    rust_soft = colors.get("rust_soft", colors["primary_soft"])
    ink_muted = colors.get("ink_muted", colors["text_secondary"])
    moss = colors.get("moss", colors.get("success", colors["primary"]))
    moss_soft = colors.get("moss_soft", colors.get("success_soft", colors["primary_soft"]))
    claret = colors.get("claret", colors.get("danger", colors["primary"]))
    claret_soft = colors.get("claret_soft", colors.get("danger_soft", colors["primary_soft"]))
    brick = colors.get("brick", colors.get("warning", colors["primary"]))
    brick_soft = colors.get("brick_soft", colors.get("warning_soft", colors["primary_soft"]))
    primary_pressed = QColor(colors["primary"]).darker(120 if is_dark else 114).name()
    card_pressed = QColor(colors["card_bg"]).darker(108 if is_dark else 102).name()
    secondary_hover = alpha_color(colors["primary"], 0.12 if is_dark else 0.08)
    secondary_pressed = alpha_color(colors["primary"], 0.2 if is_dark else 0.14)
    toolbar_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.06)
    toolbar_pressed = alpha_color(colors["primary"], 0.18 if is_dark else 0.12)
    nav_pressed = alpha_color(colors["primary"], 0.22 if is_dark else 0.12)
    muted_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.05)
    chrome_titlebar_bg = alpha_color(colors["card_bg"], 0.72 if is_dark else 0.9)
    chrome_titlebar_border = alpha_color(colors["border"], 0.86 if is_dark else 1.0)
    chrome_card_bg = alpha_color(colors["card_bg"], 0.4 if is_dark else 0.56)
    chrome_card_border = alpha_color(colors["border"], 0.9 if is_dark else 0.8)
    chrome_card_hover = alpha_color(colors["card_bg"], 0.5 if is_dark else 0.7)
    nav_hover = alpha_color(colors["card_bg"], 0.5 if is_dark else 0.76)
    nav_active = alpha_color(colors["primary"], 0.18 if is_dark else 0.08)
    nav_active_hover = alpha_color(colors["primary"], 0.24 if is_dark else 0.11)
    nav_active_border = alpha_color(colors["primary"], 0.35 if is_dark else 0.22)
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
    QWidget[role="titlebar"],
    QFrame[role="titlebar"] {{
        background: {chrome_titlebar_bg};
        border-bottom: 1px solid {chrome_titlebar_border};
    }}
    QWidget[role="sidebar"],
    QFrame[role="sidebar"] {{
        background: {colors["sidebar_bg"]};
        border-right: 1px solid {colors["border"]};
    }}
    QFrame[role="sidebar-brand"] {{
        background: transparent;
        border: none;
    }}
    QFrame[role="chrome-divider"] {{
        background: {alpha_color(colors["border"], 0.58 if is_dark else 0.92)};
        border: none;
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
    QFrame[role="chrome-card"] {{
        background: {chrome_card_bg};
        border: 1px solid {chrome_card_border};
        border-radius: 14px;
    }}
    QFrame[role="chrome-card"]:hover {{
        background: {chrome_card_hover};
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
        font-family: "{ui_family}";
        font-size: {typography["nav_caption"]}px;
        font-weight: 700;
        letter-spacing: 2px;
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
    QLabel[role="page-title-serif"] {{
        font-family: "{family}";
        font-size: {page_title_size}px;
        font-weight: 600;
        color: {colors["ink"]};
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
    QLabel[role="chrome-status-dot"] {{
        color: {colors["text_tertiary"]};
        font-size: 12px;
    }}
    QLabel[role="chrome-status-dot"][tone="success"] {{
        color: {colors["success"]};
    }}
    QLabel[role="chrome-status-dot"][tone="warning"] {{
        color: {colors["warning"]};
    }}
    QLabel[role="chrome-status-dot"][tone="danger"] {{
        color: {colors["danger"]};
    }}
    QLabel[role="chrome-status"] {{
        color: {colors["text_secondary"]};
        font-family: "{ui_family}";
        font-size: {typography["body"]}px;
        font-weight: 700;
    }}
    QLabel[role="chrome-status"][tone="success"] {{
        color: {colors["success"]};
    }}
    QLabel[role="chrome-status"][tone="warning"] {{
        color: {colors["warning"]};
    }}
    QLabel[role="chrome-status"][tone="danger"] {{
        color: {colors["danger"]};
    }}
    QLabel[role="chrome-readiness"] {{
        color: {colors["text_tertiary"]};
        font-family: "{ui_family}";
        font-size: {typography["muted"]}px;
        font-weight: 600;
    }}
    QLabel[role="chrome-meta"] {{
        color: {colors["text_secondary"]};
        font-family: "{ui_family}";
        font-size: {typography["muted"]}px;
    }}
    QLabel[role="chrome-version"] {{
        color: {colors["text_tertiary"]};
        font-family: "{ui_family}";
        font-size: {typography["muted"]}px;
        letter-spacing: 0.4px;
    }}
    QLabel[role="pill"] {{
        background: {colors["card_soft"]};
        color: {colors["text_secondary"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: {typography["pill"]}px;
        font-weight: 600;
    }}
    QLabel[role="promo-title"] {{
        color: {colors["text"]};
        font-family: "{ui_family}";
        font-size: {typography["card_title"]}px;
        font-weight: 700;
    }}
    QLabel[role="promo-body"] {{
        color: {colors["text_secondary"]};
        font-family: "{ui_family}";
        font-size: {typography["body"]}px;
        font-weight: 500;
    }}
    QLabel[role="promo-meta"] {{
        color: {colors["text_secondary"]};
        font-family: "{ui_family}";
        font-size: {typography["muted"]}px;
        font-weight: 500;
    }}
    QLabel[role="promo-pill"] {{
        background: {colors["card_soft"]};
        color: {colors["text_secondary"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-family: "{ui_family}";
        font-size: {typography["pill"]}px;
        font-weight: 700;
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
    QProgressBar[role="warm-progress"] {{
        background: {sand};
        border: none;
        border-radius: 2px;
        max-height: 4px;
    }}
    QProgressBar[role="warm-progress"]::chunk {{
        background: {rust};
        border-radius: 2px;
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
        border-left: 3px solid transparent;
        border-radius: 12px;
        color: {colors["text_secondary"]};
        text-align: left;
        padding: 10px 12px;
        font-family: "{ui_family}";
        font-size: {typography["body"]}px;
        font-weight: 600;
    }}
    QPushButton[variant="nav"]:hover {{
        background: {nav_hover};
        border-color: {chrome_card_border};
        color: {colors["text"]};
    }}
    QPushButton[variant="nav"]:pressed {{
        background: {nav_pressed};
        border-color: {nav_active_border};
        color: {colors["text"]};
    }}
    QPushButton[variant="nav"]:checked {{
        background: {nav_active};
        border-color: {nav_active_border};
        border-left: 3px solid {rust};
        color: {rust};
    }}
    QPushButton[variant="nav"]:checked:hover,
    QPushButton[variant="nav"]:checked:pressed {{
        background: {nav_active_hover};
        border-color: {nav_active_border};
        border-left: 3px solid {rust};
        color: {rust};
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
    QPushButton[variant="tab"][segmented="true"] {{
        background: transparent;
        border: none;
        border-bottom: none;
        border-radius: 10px;
        padding: 8px 12px;
        color: {ink_muted};
        font-family: "{typography["ui_family"]}";
        font-size: {typography["eyebrow"]}px;
        font-weight: 700;
    }}
    QPushButton[variant="tab"][segmented="true"]:hover {{
        background: {rust_soft};
        color: {rust};
        border-bottom: none;
    }}
    QPushButton[variant="tab"][segmented="true"]:pressed,
    QPushButton[variant="tab"][segmented="true"]:checked {{
        background: {rust_soft};
        color: {rust};
        border-bottom: none;
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
    QFrame[role="atelier-card"]:hover {{
        border: 1px solid {colors["rust"]};
        background: {colors["rust_soft"]};
    }}
    QFrame[role="atelier-card"][selected="true"] {{
        border: 1px solid {colors["rust"]};
        background: {colors["rust_soft"]};
    }}
    QFrame[role="atelier-card"][answer-state="correct"] {{
        border: 1px solid {moss};
        background: {moss_soft};
    }}
    QFrame[role="atelier-card"][answer-state="incorrect"] {{
        border: 1px solid {claret};
        background: {claret_soft};
    }}
    QFrame[role="atelier-card"][answer-state="partial"] {{
        border: 1px solid {brick};
        background: {brick_soft};
    }}
    QFrame[role="paper-card"] {{
        background: {paper};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
    }}
    QFrame[role="paper-card"][surface="sand"] {{
        background: {sand};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
    }}
    QLabel[role="eyebrow"] {{
        font-family: "{ui_family}";
        font-size: {typography["eyebrow"]}px;
        color: {colors["rust"]};
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
    }}
    QLabel[role="metric-value"] {{
        font-family: "{ui_family}";
        font-size: {typography["metric_value"]}px;
        color: {colors["moss"]};
        font-weight: 700;
    }}
    QLabel[role="metric-label"] {{
        font-family: "{ui_family}";
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
    QWidget[role="titlebar"] QLabel[role="page-title-serif"],
    QFrame[role="titlebar"] QLabel[role="page-title-serif"] {{
        font-size: {chrome_title_size}px;
        color: {colors["text"]};
    }}
    QWidget[role="titlebar"] QLabel[role="subtitle-italic"],
    QFrame[role="titlebar"] QLabel[role="subtitle-italic"] {{
        font-size: {chrome_subtitle_size}px;
        color: {colors["text_secondary"]};
    }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {colors["ink_muted"]};
        padding: 7px 12px;
        font-family: "{ui_family}";
        border-radius: 12px;
    }}
    QPushButton[variant="ghost"]:hover {{
        color: {colors["rust"]};
        background: {alpha_color(colors["primary"], 0.1 if is_dark else 0.06)};
        border-color: {alpha_color(colors["border"], 0.65 if is_dark else 0.4)};
    }}
    QPushButton[variant="ghost"]:pressed {{
        background: {alpha_color(colors["primary"], 0.16 if is_dark else 0.1)};
        color: {colors["rust_hover"]};
    }}
    QPushButton[variant="danger"] {{
        background: {colors["claret"]};
        border: 1px solid {colors["claret"]};
        color: {colors["parchment"]};
        padding: 9px 16px;
        font-family: "{ui_family}";
        font-weight: 600;
    }}
    QPushButton[variant="danger"]:hover {{
        background: {QColor(colors["claret"]).darker(110).name()};
    }}
    QPushButton[variant="nav"][active-warm="true"] {{
        background: {nav_active};
        border: 1px solid {nav_active_border};
        border-left: 3px solid {rust};
        color: {rust};
        font-family: "{ui_family}";
        font-size: {typography["body"]}px;
        font-weight: 600;
        padding-left: 10px;
    }}
    QPushButton[variant="nav"][active-warm="true"]:hover,
    QPushButton[variant="nav"][active-warm="true"]:pressed {{
        background: {nav_active_hover};
        border: 1px solid {nav_active_border};
        border-left: 3px solid {rust};
        color: {rust};
        padding-left: 10px;
    }}
    QPushButton#topbar-settings {{
        color: {colors["text_secondary"]};
        font-size: {typography["muted"]}px;
        font-weight: 600;
    }}
    """
