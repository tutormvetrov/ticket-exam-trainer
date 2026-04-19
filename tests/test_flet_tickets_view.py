from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from ui_flet.components.ticket_card import _ticket_number
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette
from ui_flet.views.tickets_view import _build_filters_block, build_tickets_view


class _MockPage:
    def __init__(self) -> None:
        self.route = "/tickets"
        self.views: list[ft.View] = []
        self.on_route_change = None

    def go(self, route: str) -> None:
        self.route = route

    def update(self) -> None:
        pass


def _make_state(*, breakpoint: str = "standard") -> AppState:
    connection = SimpleNamespace(
        execute=lambda *args, **kwargs: SimpleNamespace(fetchall=lambda: []),
    )
    facade = SimpleNamespace(
        load_ticket_maps=lambda exam_id=None: [],
        load_mastery_breakdowns=lambda: {},
        load_training_snapshot=lambda tickets=None: SimpleNamespace(queue_items=[]),
        connection=connection,
        settings=SimpleNamespace(),
        save_settings=lambda settings: None,
        queries=SimpleNamespace(load_ticket_map=lambda _ticket_id: None),
    )
    return AppState(page=_MockPage(), facade=facade, breakpoint=breakpoint)


def _collect_texts(control: ft.Control | None) -> list[str]:
    if control is None:
        return []
    values: list[str] = []
    for attr in ("text", "value", "label", "hint_text", "tooltip"):
        raw = getattr(control, attr, None)
        if isinstance(raw, str) and raw:
            values.append(raw)
    content = getattr(control, "content", None)
    if content is not None:
        values.extend(_collect_texts(content))
    controls = getattr(control, "controls", None)
    if isinstance(controls, list):
        for child in controls:
            values.extend(_collect_texts(child))
    return values


def test_filters_stack_vertically_on_compact() -> None:
    block, search_field, section_dd, difficulty_dd = _build_filters_block(
        breakpoint="compact",
        palette_map=palette(False),
        section_choices=[("all", "Все")],
        search_value="",
        active_section_value="all",
        active_difficulty_value="all",
        on_search=lambda _e: None,
        on_section_change=lambda _e: None,
        on_difficulty_change=lambda _e: None,
    )

    assert isinstance(block, ft.Column)
    assert not search_field.expand
    assert section_dd.width is None
    assert difficulty_dd.width is None


def test_filters_use_non_wrapping_row_on_wide_breakpoints() -> None:
    block, search_field, section_dd, difficulty_dd = _build_filters_block(
        breakpoint="wide",
        palette_map=palette(False),
        section_choices=[("all", "Все")],
        search_value="",
        active_section_value="all",
        active_difficulty_value="all",
        on_search=lambda _e: None,
        on_section_change=lambda _e: None,
        on_difficulty_change=lambda _e: None,
    )

    assert isinstance(block, ft.Row)
    assert block.wrap is False
    assert search_field.expand == 1
    assert section_dd.width == 240
    assert difficulty_dd.width == 160


def test_tickets_view_registers_breakpoint_listener_once() -> None:
    state = _make_state()

    build_tickets_view(state)
    build_tickets_view(state)
    build_tickets_view(state)

    assert len(state.breakpoint_listeners) == 1


def test_ticket_number_prefers_catalog_position_over_ticket_id_digits() -> None:
    assert _ticket_number("doc-demo-728037", 8) == "#008"
    assert _ticket_number("ticket-042", None) == "#042"


def test_tickets_view_shows_error_state_when_ticket_load_fails() -> None:
    state = _make_state()
    state.facade.load_ticket_maps = lambda exam_id=None: (_ for _ in ()).throw(RuntimeError("db down"))

    view = build_tickets_view(state)
    text_blob = " ".join(_collect_texts(view))

    assert TEXT["tickets.load_failed"] in text_blob
