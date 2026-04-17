from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


LIGHT = {
    # Поверхности (legacy keys)
    "app_bg": "#F8EFE2",          # paper
    "sidebar_bg": "#F1E4C9",      # sand (кожаный обрез)
    "surface_bg": "#FBF6F0",      # parchment surface
    "card_bg": "#FBF6F0",         # parchment
    "card_soft": "#F4E9D6",       # soft parchment
    "card_muted": "#EFE2CC",      # muted sand
    "input_bg": "#FDFAF4",        # самый светлый paper
    # Семантические акценты (legacy keys)
    "primary": "#A04A22",         # rust
    "primary_soft": "#E9D5BE",    # rust_soft
    "primary_hover": "#8A3D1A",   # rust darker
    "success": "#4A6150",         # sage
    "success_soft": "#DFE5D4",    # sage_soft
    "warning": "#9B4A28",         # brick
    "warning_soft": "#F3DDC7",    # brick_soft
    "danger": "#7A2E2E",          # claret
    "danger_soft": "#F3D9D3",     # claret_soft
    # back-compat: тоны violet/cyan нейтрализованы в warm-гамму, чтобы
    # старые call-sites (tone='violet' / 'cyan') не «выпадали» холодным пятном.
    "violet_soft": "#EAE0D4",
    "cyan_soft": "#DCE5D6",
    # Текст
    "text": "#2C2520",            # ink
    "text_secondary": "#4E3E35",  # ink_muted
    "text_tertiary": "#8A7064",   # ink_faint
    # Границы
    "border": "#E0CBA8",
    "border_strong": "#C89A55",   # латунная рамка folio
    "shadow": QColor(90, 55, 25, 45),  # warm brown shadow @ level=md

    # === Semantic aliases (новый пласт имён, дублируют legacy) ===
    "paper": "#F8EFE2",
    "parchment": "#FBF6F0",
    "sand": "#F1E4C9",
    "ink": "#2C2520",
    "ink_muted": "#4E3E35",
    "ink_faint": "#8A7064",
    "rust": "#A04A22",
    "rust_soft": "#E9D5BE",
    # Not in spec §3 — extrapolated to match rust/rust_soft/rust_hover triplet
    # for QSS primary:hover; remove if spec ever drops primary_hover as well.
    "rust_hover": "#8A3D1A",
    "moss": "#3D4E2A",
    "moss_soft": "#DCDDBC",
    "brass": "#9C7A1E",
    "brick": "#9B4A28",
    "brick_soft": "#F3DDC7",
    "claret": "#7A2E2E",
    "claret_soft": "#F3D9D3",
    "sage": "#4A6150",
    "sage_soft": "#DFE5D4",
}


DARK = {
    "app_bg": "#271710",          # cognac
    "sidebar_bg": "#2E1D12",      # sand dark — глубже чем app_bg
    "surface_bg": "#3C2518",      # parchment-as-surface
    "card_bg": "#3C2518",
    "card_soft": "#4A2F1F",
    "card_muted": "#381E12",
    "input_bg": "#3C2518",
    "primary": "#C97A57",         # rust-lit
    "primary_soft": "#5C3220",    # rust_soft dark (opaque fallback)
    "primary_hover": "#E08A63",
    "success": "#9EB389",         # sage-lit
    "success_soft": "#2F3A28",
    "warning": "#D07A48",         # brick-lit
    "warning_soft": "#452A1A",
    "danger": "#D67580",          # claret-lit
    "danger_soft": "#46211F",
    # back-compat: тоны violet/cyan нейтрализованы в warm-гамму, чтобы
    # старые call-sites (tone='violet' / 'cyan') не «выпадали» холодным пятном.
    "violet_soft": "#3A2C22",
    "cyan_soft": "#2A3028",
    "text": "#F0DDB2",            # parchment text
    "text_secondary": "#C0A68A",  # linen
    "text_tertiary": "#8A7560",
    "border": "#4A3225",
    "border_strong": "#7A5A32",
    "shadow": QColor(0, 0, 0, 140),

    # === Semantic aliases ===
    "paper": "#271710",
    "parchment": "#3C2518",
    "sand": "#2E1D12",
    "ink": "#F0DDB2",
    "ink_muted": "#C0A68A",
    "ink_faint": "#8A7560",
    "rust": "#C97A57",
    "rust_soft": "#5C3220",
    # Not in spec §3 — extrapolated to match rust/rust_soft/rust_hover triplet
    # for QSS primary:hover; remove if spec ever drops primary_hover as well.
    "rust_hover": "#E08A63",
    "moss": "#8BA267",            # moss-lit (CTA)
    "moss_soft": "#2E3826",
    "brass": "#C9A66B",
    "brick": "#D07A48",
    "brick_soft": "#452A1A",
    "claret": "#D67580",
    "claret_soft": "#46211F",
    "sage": "#9EB389",
    "sage_soft": "#2F3A28",
}


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


def mastery_band_color(percent: int) -> str:
    """Цвет для категорий владения материалом (0..100%).

    Использует семантические цвета темы (danger/warning/success), чтобы
    одинаково работать в light и dark: в тёмной теме свои более мягкие
    оттенки. Раньше эти пороги были хардкод HEX'ами и плохо смотрелись
    на dark палитре.
    """
    colors = current_colors()
    p = max(0, min(100, int(percent)))
    if p <= 30:
        return colors["danger"]
    if p <= 60:
        return colors["warning"]
    if p <= 80:
        # Промежуточный «тёплый» тон — между warning и success.
        warning = QColor(colors["warning"])
        success = QColor(colors["success"])
        mid = QColor(
            (warning.red() + success.red()) // 2,
            (warning.green() + success.green()) // 2,
            (warning.blue() + success.blue()) // 2,
        )
        return mid.name()
    return colors["success"]


def logo_palette(is_dark: bool) -> dict[str, str]:
    """Палитра бренд-медальона для подстановки в SVG-шаблон.

    Ключи словаря совпадают с плейсхолдерами `{{name}}` в шаблонах
    `assets/logo/mark-*.svg.template`. Значения зафиксированы отдельно
    от LIGHT/DARK, потому что изумруд и золото — брендовые константы,
    а не семантические цвета UI (success/warning/danger).
    """
    if is_dark:
        return {
            "emerald_stop_0": "#6E8554",
            "emerald_stop_1": "#A8BE8A",
            "gold_stop_0": "#C9A66B",
            "gold_stop_1": "#E6CE8F",
        }
    return {
        "emerald_stop_0": "#2F463A",
        "emerald_stop_1": "#6E8554",
        "gold_stop_0": "#9C7A1E",
        "gold_stop_1": "#D0A444",
    }
