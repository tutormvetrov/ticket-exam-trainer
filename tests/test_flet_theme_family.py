"""Tests for theme family switching (warm ↔ deco).

Covers the user-visible SegmentedButton in Settings → «Стиль оформления»:

* ``set_active_family("deco")`` must actually swap the palette returned by
  ``palette(is_dark)`` and the typography returned by ``text_style``.
* Registered listeners (subscribed via ``on_family_change``) are invoked on
  every switch so the rest of the UI can re-render.
* An unknown family name is a no-op — the toggle must not silently corrupt
  the active state if a bad value sneaks in from ``settings.json``.

These tests pin the contract the SettingsView relies on — they'll fail if
somebody rewires the tokens module without preserving the switch semantics.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_active_family():
    """Each test starts on ``warm`` and restores whatever was active."""
    from ui_flet.theme import tokens

    before = tokens.get_active_family()
    # Force a known starting point without going through public API — the
    # private attribute is exactly what set_active_family flips.
    tokens._active_family = "warm"
    tokens._listeners.clear()
    try:
        yield
    finally:
        tokens._active_family = before
        tokens._listeners.clear()


def test_set_active_family_switches_palette() -> None:
    from ui_flet.theme.tokens import get_active_family, palette, set_active_family

    warm_light = palette(False)
    warm_accent = warm_light["accent"]

    set_active_family("deco")
    assert get_active_family() == "deco"

    deco_light = palette(False)
    assert deco_light["accent"] != warm_accent, (
        "warm and deco palettes must differ — otherwise the toggle is cosmetic only"
    )


def test_set_active_family_switches_typography() -> None:
    from ui_flet.theme.tokens import set_active_family, text_style

    warm_h1 = text_style("h1").font_family
    set_active_family("deco")
    deco_h1 = text_style("h1").font_family
    assert deco_h1 != warm_h1, "deco should use a different display font (Playfair Display vs Lora)"


def test_set_active_family_notifies_listeners() -> None:
    from ui_flet.theme.tokens import on_family_change, set_active_family

    hits: list[str] = []
    on_family_change(lambda name: hits.append(name))

    set_active_family("deco")
    assert hits == ["deco"]

    # Switching back also fires a notification.
    set_active_family("warm")
    assert hits == ["deco", "warm"]


def test_set_active_family_is_noop_on_same_value() -> None:
    """Re-selecting the current family should NOT fire listeners (UI-perf)."""
    from ui_flet.theme.tokens import on_family_change, set_active_family

    hits: list[str] = []
    on_family_change(lambda name: hits.append(name))

    set_active_family("warm")  # warm is already active
    assert hits == []


def test_set_active_family_rejects_unknown_name() -> None:
    """Bad values in settings.json must not crash or corrupt state."""
    from ui_flet.theme.tokens import get_active_family, set_active_family

    assert get_active_family() == "warm"
    set_active_family("goth")  # not a defined family
    assert get_active_family() == "warm", "unknown family must be ignored silently"


def test_both_families_have_complete_light_and_dark_palettes() -> None:
    """Both warm and deco must define every required palette key for both modes."""
    from ui_flet.theme.tokens import palette, set_active_family

    required = {
        "bg_base", "bg_surface", "bg_elevated",
        "accent", "accent_hover", "accent_soft",
        "text_primary", "text_secondary", "text_muted",
        "border_soft", "border_medium",
        "success", "warning", "danger", "info",
    }
    for family in ("warm", "deco"):
        set_active_family(family)
        for is_dark in (False, True):
            pal = palette(is_dark)
            missing = required - set(pal.keys())
            assert not missing, f"{family}/{'dark' if is_dark else 'light'} missing keys: {missing}"
