"""Тесты warm-minimal палитры.

Закрепляют ключевые hex-значения и наличие semantic-токенов.
Если кто-то случайно откатит цвета на старые синие — тест упадёт.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor

from ui.theme.palette import LIGHT, DARK, is_dark_palette, current_colors


def test_light_is_warm_sand_not_cold_blue() -> None:
    """Приложение выше НЕ должно иметь холодно-синюю основу."""
    app_bg = QColor(LIGHT["app_bg"])
    assert app_bg.red() > app_bg.blue(), f"LIGHT.app_bg={LIGHT['app_bg']} не тёплый"
    assert LIGHT["app_bg"] == "#F8EFE2"
    assert LIGHT["card_bg"] == "#FBF6F0"
    assert LIGHT["sidebar_bg"] == "#F1E4C9"


def test_light_accents_are_rust_moss() -> None:
    assert LIGHT["primary"] == "#A04A22"
    assert LIGHT["success"] == "#4A6150"
    assert LIGHT["warning"] == "#9B4A28"
    assert LIGHT["danger"] == "#7A2E2E"


def test_light_semantic_aliases_present() -> None:
    for key in (
        "paper", "parchment", "sand", "ink", "ink_muted", "ink_faint",
        "rust", "rust_soft", "moss", "moss_soft", "brass",
        "brick", "brick_soft", "claret", "claret_soft", "sage", "sage_soft",
    ):
        assert key in LIGHT, f"LIGHT не содержит semantic token {key!r}"


def test_dark_is_cognac_not_cold_charcoal() -> None:
    app_bg = QColor(DARK["app_bg"])
    assert app_bg.red() > app_bg.blue(), f"DARK.app_bg={DARK['app_bg']} не тёплый"
    assert DARK["app_bg"] == "#271710"
    assert DARK["card_bg"] == "#3C2518"
    assert DARK["sidebar_bg"] == "#2E1D12"


def test_dark_accents_are_warm_lit() -> None:
    assert DARK["primary"] == "#C97A57"   # rust-lit
    assert DARK["success"] == "#9EB389"   # sage-lit
    assert DARK["warning"] == "#D07A48"   # brick-lit
    assert DARK["danger"] == "#D67580"    # claret-lit
    assert DARK["moss"] == "#8BA267"      # moss-lit CTA alias


def test_dark_semantic_aliases_present() -> None:
    for key in (
        "paper", "parchment", "sand", "ink", "ink_muted", "ink_faint",
        "rust", "rust_soft", "moss", "moss_soft", "brass",
        "brick", "brick_soft", "claret", "claret_soft", "sage", "sage_soft",
    ):
        assert key in DARK, f"DARK не содержит semantic token {key!r}"


def test_shadow_is_qcolor_not_hex_string() -> None:
    """apply_shadow() requires QColor; guard against refactors that
    normalise to hex string (would break effect pipeline)."""
    assert isinstance(LIGHT["shadow"], QColor)
    assert isinstance(DARK["shadow"], QColor)


def test_semantic_aliases_identical_to_legacy_keys() -> None:
    """paper == app_bg, parchment == card_bg и т.д. — это алиасы."""
    for palette in (LIGHT, DARK):
        assert palette["paper"] == palette["app_bg"]
        assert palette["parchment"] == palette["card_bg"]
        assert palette["sand"] == palette["sidebar_bg"]
        assert palette["rust"] == palette["primary"]
        assert palette["ink"] == palette["text"]
        assert palette["ink_muted"] == palette["text_secondary"]
        assert palette["ink_faint"] == palette["text_tertiary"]
