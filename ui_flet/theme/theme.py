"""Build ft.Theme from warm tokens. Apply to ft.Page without restart.

Flet 0.27 represents M3 theme data in ft.Theme with color_scheme_seed or
a full ColorScheme. We construct an explicit ColorScheme from tokens so
the warm palette survives Material 3 defaulting.
"""

from __future__ import annotations

import flet as ft

from ui_flet.theme.tokens import COLOR_LIGHT, COLOR_DARK, TYPE


def _color_scheme(p: dict[str, str], is_dark: bool) -> ft.ColorScheme:
    return ft.ColorScheme(
        primary=p["accent"],
        on_primary=p["bg_surface"] if not is_dark else p["text_primary"],
        primary_container=p["accent_soft"],
        on_primary_container=p["text_primary"],
        secondary=p["info"],
        on_secondary=p["bg_surface"] if not is_dark else p["text_primary"],
        surface=p["bg_surface"],
        on_surface=p["text_primary"],
        surface_variant=p["bg_elevated"],
        on_surface_variant=p["text_secondary"],
        background=p["bg_base"],
        on_background=p["text_primary"],
        error=p["danger"],
        on_error=p["bg_surface"],
        outline=p["border_medium"],
        outline_variant=p["border_soft"],
    )


def build_theme(is_dark: bool) -> ft.Theme:
    p = COLOR_DARK if is_dark else COLOR_LIGHT
    return ft.Theme(
        color_scheme=_color_scheme(p, is_dark),
        font_family=TYPE["body"]["family"],
        use_material3=True,
        visual_density=ft.VisualDensity.STANDARD,
        page_transitions=ft.PageTransitionsTheme(
            windows=ft.PageTransitionTheme.FADE_UPWARDS,
        ),
    )


def apply_theme(page: ft.Page, is_dark: bool) -> None:
    """Switch page theme in-place. Caller is responsible for page.update()."""
    page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
    page.theme = build_theme(False)
    page.dark_theme = build_theme(True)
    p = COLOR_DARK if is_dark else COLOR_LIGHT
    page.bgcolor = p["bg_base"]
