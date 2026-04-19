from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.views.dashboard_view import build_dashboard_view
from ui_flet.views.training_view import build_training_view


class _MockPage:
    def __init__(self, route: str) -> None:
        self.route = route
        self.views: list[ft.View] = []
        self.on_route_change = None
        self.dialog = None

    def go(self, route: str) -> None:
        self.route = route

    def update(self) -> None:
        pass


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


def test_dashboard_shows_error_state_when_tickets_fail() -> None:
    facade = SimpleNamespace(
        load_ticket_maps=lambda exam_id=None: (_ for _ in ()).throw(RuntimeError("broken")),
        load_mastery_breakdowns=lambda: {},
        load_training_snapshot=lambda tickets=None: SimpleNamespace(queue_items=[]),
        load_readiness_score=lambda tickets=None, mastery=None: SimpleNamespace(percent=0, tickets_practiced=0),
        settings=SimpleNamespace(),
    )
    state = AppState(page=_MockPage("/dashboard"), facade=facade)

    view = build_dashboard_view(state)
    text_blob = " ".join(_collect_texts(view))

    assert TEXT["dashboard.load_failed"] in text_blob


def test_training_shows_error_state_when_ticket_load_fails() -> None:
    facade = SimpleNamespace(
        queries=SimpleNamespace(load_ticket_map=lambda ticket_id: (_ for _ in ()).throw(RuntimeError("missing db"))),
        load_mastery_breakdowns=lambda: {},
        connection=SimpleNamespace(execute=lambda *args, **kwargs: SimpleNamespace(fetchone=lambda: None)),
        settings=SimpleNamespace(),
    )
    state = AppState(page=_MockPage("/training/ticket-1/reading"), facade=facade)

    view = build_training_view(state, ticket_id="ticket-1", mode_key="reading")
    text_blob = " ".join(_collect_texts(view))

    assert TEXT["training.load_failed"] in text_blob
