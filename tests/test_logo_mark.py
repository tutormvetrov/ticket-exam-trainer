from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_logo_palette_light_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=False)
    assert palette == {
        "emerald_stop_0": "#134734",
        "emerald_stop_1": "#228F64",
        "gold_stop_0": "#B9893D",
        "gold_stop_1": "#E6C478",
    }


def test_logo_palette_dark_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=True)
    assert palette == {
        "emerald_stop_0": "#165A42",
        "emerald_stop_1": "#2AA076",
        "gold_stop_0": "#D8A74E",
        "gold_stop_1": "#F4DB94",
    }


def test_logo_assets_dir_points_at_repo_assets_when_not_frozen() -> None:
    from app.paths import logo_assets_dir
    path = logo_assets_dir()
    assert path.name == "logo"
    assert path.parent.name == "assets"
    assert (path / "mark-full.svg.template").is_file()
    assert (path / "mark-minimal.svg.template").is_file()


def test_logo_mark_full_variant_for_large_sizes(qt_app) -> None:
    from ui.components.common import LogoMark
    widget = LogoMark(size=52)
    assert widget._variant == "full"
    widget_big = LogoMark(size=88)
    assert widget_big._variant == "full"


def test_logo_mark_minimal_variant_for_small_sizes(qt_app) -> None:
    from ui.components.common import LogoMark
    widget = LogoMark(size=24)
    assert widget._variant == "minimal"


def test_logo_mark_threshold_is_40(qt_app) -> None:
    from ui.components.common import LogoMark
    assert LogoMark(size=39)._variant == "minimal"
    assert LogoMark(size=40)._variant == "full"
