from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.theme import LIGHT, DARK, mastery_band_color, set_app_theme


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_bands_use_light_theme_colors(qt_app) -> None:
    set_app_theme(qt_app, "light", "inter-style", 14)
    assert mastery_band_color(10) == LIGHT["danger"]
    assert mastery_band_color(30) == LIGHT["danger"]
    assert mastery_band_color(45) == LIGHT["warning"]
    assert mastery_band_color(60) == LIGHT["warning"]
    # 61..80 → промежуточный между warning и success.
    mid = mastery_band_color(70)
    assert mid not in {LIGHT["warning"], LIGHT["success"]}
    assert mastery_band_color(85) == LIGHT["success"]
    assert mastery_band_color(100) == LIGHT["success"]


def test_bands_switch_with_dark_theme(qt_app) -> None:
    set_app_theme(qt_app, "dark", "inter-style", 14)
    assert mastery_band_color(10) == DARK["danger"]
    assert mastery_band_color(100) == DARK["success"]
    # Тёмные варианты отличаются от светлых — это главный смысл фикса.
    set_app_theme(qt_app, "light", "inter-style", 14)
    assert mastery_band_color(100) == LIGHT["success"]


def test_out_of_range_is_clamped(qt_app) -> None:
    set_app_theme(qt_app, "light", "inter-style", 14)
    assert mastery_band_color(-50) == LIGHT["danger"]
    assert mastery_band_color(200) == LIGHT["success"]
