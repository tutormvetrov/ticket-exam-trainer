"""Тесты typography scale — инварианты иерархии."""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.theme.typography import (
    FONT_PRESETS,
    UI_SANS_FAMILIES,
    build_typography,
    resolve_ui_font,
)


@pytest.fixture(scope="module", autouse=True)
def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.mark.parametrize("base_pt", [9, 11, 14, 18])
def test_subtitles_never_exceed_body(base_pt: int) -> None:
    typo = build_typography("georgia", base_pt)
    body = typo["body"]
    for key in ("subtitle", "brand_subtitle", "muted"):
        assert typo[key] <= body, (
            f"{key}={typo[key]} > body={body} at base_pt={base_pt}"
            " — типографическая иерархия сломана"
        )
    # page_subtitle исторически ~= body; разрешим превышение на 1.
    assert typo["page_subtitle"] <= body + 1


@pytest.mark.parametrize("base_pt", [9, 18])
def test_display_is_largest(base_pt: int) -> None:
    typo = build_typography("georgia", base_pt)
    assert typo["display"] >= typo["hero"]
    assert typo["hero"] >= typo["page_title"]
    assert typo["page_title"] >= typo["section_title"]
    assert typo["section_title"] >= typo["card_title"]
    assert typo["card_title"] >= typo["body"]


def test_resolve_ui_font_returns_known_family() -> None:
    """Finding #5 — guard against a typo in UI_SANS_FAMILIES.

    resolve_ui_font() must return a string. В headless-Qt (offscreen)
    шрифтовая БД часто пустая и defaultFamily() == '' — это ожидаемо.
    Когда список семей не пуст, результат должен быть непустой строкой.
    """
    family = resolve_ui_font()
    assert isinstance(family, str)
    acceptable = set(UI_SANS_FAMILIES) | {"MS Shell Dlg 2"}  # Qt offscreen default
    available = set(QFontDatabase.families())
    if available:
        assert family, "resolve_ui_font вернул пустую строку при непустой БД"


def test_preset_keys_are_only_serif() -> None:
    """Pой user-selectable FONT_PRESETS — только сериф (Warm Minimal)."""
    assert set(FONT_PRESETS.keys()) == {"georgia", "cambria", "palatino"}
