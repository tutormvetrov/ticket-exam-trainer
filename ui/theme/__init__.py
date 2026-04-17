"""ui.theme — публичный API темы.

Пакет разбит на модули (palette, typography, spacing, materiality,
stylesheet). Здесь re-export'ятся все символы, чтобы существующие
импорты вида `from ui.theme import X` продолжали работать без правок.
"""
from __future__ import annotations

from ui.theme.palette import (
    LIGHT,
    DARK,
    current_palette_name,
    current_colors,
    is_dark_palette,
    alpha_color,
    mastery_band_color,
    logo_palette,
)
from ui.theme.typography import (
    FONT_PRESETS,
    resolve_font_family,
    resolve_ui_font,
    build_typography,
    app_font,
)
from ui.theme.spacing import SPACING, RADII, ELEVATION, shadow_color
from ui.theme.materiality import apply_shadow
from ui.theme.stylesheet import build_stylesheet, set_app_theme

__all__ = [
    "LIGHT",
    "DARK",
    "FONT_PRESETS",
    "SPACING",
    "RADII",
    "ELEVATION",
    "shadow_color",
    "current_palette_name",
    "current_colors",
    "is_dark_palette",
    "alpha_color",
    "mastery_band_color",
    "logo_palette",
    "resolve_font_family",
    "resolve_ui_font",
    "build_typography",
    "app_font",
    "apply_shadow",
    "build_stylesheet",
    "set_app_theme",
]
