from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

from ui.theme.materiality import apply_shadow
from ui.theme.palette import LIGHT, DARK


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_apply_shadow_md_light(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "md", LIGHT)
    effect = widget.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    assert effect.blurRadius() == 22
    assert effect.yOffset() == 10
    color = effect.color()
    # warm brown tint — red > blue
    assert color.red() > color.blue()
    assert color.alpha() == 45


def test_apply_shadow_lg_dark(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "lg", DARK)
    effect = widget.graphicsEffect()
    assert effect.blurRadius() == 28
    assert effect.yOffset() == 14
    assert effect.color().alpha() == 140


def test_apply_shadow_sm_barely_visible(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "sm", LIGHT)
    effect = widget.graphicsEffect()
    assert effect.blurRadius() == 4
    assert effect.color().alpha() == 15


def test_apply_shadow_rejects_invalid_level(qt_app) -> None:
    widget = QWidget()
    with pytest.raises(KeyError):
        apply_shadow(widget, "invalid", LIGHT)
