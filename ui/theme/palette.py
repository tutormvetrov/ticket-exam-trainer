from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


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
            "emerald_stop_0": "#165A42",
            "emerald_stop_1": "#2AA076",
            "gold_stop_0": "#D8A74E",
            "gold_stop_1": "#F4DB94",
        }
    return {
        "emerald_stop_0": "#134734",
        "emerald_stop_1": "#228F64",
        "gold_stop_0": "#B9893D",
        "gold_stop_1": "#E6C478",
    }
