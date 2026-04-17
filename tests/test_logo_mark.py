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
        "emerald_stop_0": "#2F463A",
        "emerald_stop_1": "#6E8554",
        "gold_stop_0": "#9C7A1E",
        "gold_stop_1": "#D0A444",
    }


def test_logo_palette_dark_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=True)
    assert palette == {
        "emerald_stop_0": "#6E8554",
        "emerald_stop_1": "#A8BE8A",
        "gold_stop_0": "#C9A66B",
        "gold_stop_1": "#E6CE8F",
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


def test_logo_mark_falls_back_when_template_missing(qt_app, tmp_path, monkeypatch) -> None:
    """Если файл шаблона не читается, paintEvent уходит в _paint_fallback и не крашится."""
    from ui.components.common import LogoMark
    from PySide6.QtGui import QPixmap

    widget = LogoMark(size=52)

    def _raise_oserror(self) -> bytes:
        raise OSError("simulated missing template")

    monkeypatch.setattr(LogoMark, "_load_template", _raise_oserror)

    pixmap = QPixmap(52, 52)
    pixmap.fill()
    widget.render(pixmap)
    # Just confirming no exception escaped. The content is a monochrome disc + "Т".


def test_logo_mark_theme_refresh_rebuilds_svg(qt_app) -> None:
    from ui.components.common import LogoMark
    from ui.theme import set_app_theme

    try:
        set_app_theme(qt_app, "light", "inter-style", 14)
        widget = LogoMark(size=52)
        svg_light = bytes(widget._build_svg())
        assert b"#6E8554" in svg_light  # moss light

        set_app_theme(qt_app, "dark", "inter-style", 14)
        widget.refresh_theme()
        svg_dark = bytes(widget._build_svg())
        assert b"#A8BE8A" in svg_dark  # moss dark
        assert svg_light != svg_dark
    finally:
        # Восстановить light, чтобы не зааффектить другие тесты даже при падении.
        set_app_theme(qt_app, "light", "inter-style", 14)


def test_logo_mark_svg_has_no_unresolved_placeholders(qt_app) -> None:
    from ui.components.common import LogoMark
    for size, variant in ((52, "full"), (24, "minimal")):
        widget = LogoMark(size=size)
        assert widget._variant == variant
        svg_bytes = bytes(widget._build_svg())
        assert b"{{" not in svg_bytes, f"Нерезолвленные плейсхолдеры в {variant}"
        assert b"}}" not in svg_bytes
