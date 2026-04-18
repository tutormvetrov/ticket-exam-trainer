from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QBoxLayout

from ui.views.dialogue_view import DialogueView
from ui.views.tickets_view import TicketsView


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_tickets_view_collapses_to_vertical_on_narrow_width(qt_app) -> None:
    view = TicketsView(shadow_color=None)
    view.resize(900, 720)
    view._apply_responsive_layout()
    assert view.body_layout.direction() == QBoxLayout.Direction.TopToBottom
    # В узком режиме список билетов не должен быть зажат в 360px.
    assert view.left_card.maximumWidth() > 1000


def test_tickets_view_uses_side_by_side_on_wide_width(qt_app) -> None:
    view = TicketsView(shadow_color=None)
    view.resize(1440, 900)
    view._apply_responsive_layout()
    assert view.body_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert view.left_card.minimumWidth() == 320
    assert view.left_card.maximumWidth() == 396


def test_dialogue_view_prefers_long_scroll_layout_on_regular_width(qt_app) -> None:
    view = DialogueView(shadow_color=None)
    view.resize(1500, 900)
    view._apply_responsive_layout()
    assert view.body_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert view.left_column.maximumWidth() > 1000
    assert view.right_column.maximumWidth() > 1000


def test_dialogue_view_uses_columns_only_on_very_wide_width(qt_app) -> None:
    view = DialogueView(shadow_color=None)
    view.resize(1920, 1080)
    view._apply_responsive_layout()
    assert view.body_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert view.left_column.maximumWidth() == 396
    assert view.right_column.maximumWidth() == 420
