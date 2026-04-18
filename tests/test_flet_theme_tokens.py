"""Sanity checks on the warm-minimal token set.

Ensures every component can rely on palette keys being present, TYPE tokens
having the expected shape, and SPACE/RADIUS scales being monotonic.
"""

from __future__ import annotations

import pytest


def test_palettes_have_matching_keys():
    from ui_flet.theme.tokens import COLOR_LIGHT, COLOR_DARK
    assert set(COLOR_LIGHT.keys()) == set(COLOR_DARK.keys())
    # Minimum keys every component expects
    required = {
        "bg_base", "bg_surface", "bg_elevated",
        "accent", "accent_hover", "accent_soft",
        "text_primary", "text_secondary", "text_muted",
        "border_soft", "border_medium",
        "success", "warning", "danger", "info",
    }
    assert required.issubset(COLOR_LIGHT.keys())


def test_palette_helper_returns_correct_mode():
    from ui_flet.theme.tokens import palette, COLOR_LIGHT, COLOR_DARK
    assert palette(False) is COLOR_LIGHT
    assert palette(True) is COLOR_DARK


def test_type_tokens_have_required_shape():
    from ui_flet.theme.tokens import TYPE
    required_styles = {"display", "h1", "h2", "h3", "body", "body_strong", "caption", "mono"}
    assert required_styles.issubset(TYPE.keys())
    for token, spec in TYPE.items():
        assert {"family", "size", "weight"}.issubset(spec.keys()), token


def test_space_scale_is_monotonic():
    from ui_flet.theme.tokens import SPACE
    values = [SPACE[k] for k in ("xs", "sm", "md", "lg", "xl", "2xl", "3xl")]
    assert values == sorted(values)


def test_radius_scale_is_monotonic():
    from ui_flet.theme.tokens import RADIUS
    for a, b in zip(("sm", "md", "lg"), ("md", "lg", "xl")):
        assert RADIUS[a] < RADIUS[b]


def test_text_style_returns_textstyle():
    import flet as ft
    from ui_flet.theme.tokens import text_style
    style = text_style("h1", color="#123456")
    assert isinstance(style, ft.TextStyle)
    assert style.color == "#123456"
