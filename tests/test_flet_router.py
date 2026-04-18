"""Router: three canonical routes + redirect + training URL parse."""

from __future__ import annotations

from types import SimpleNamespace


class _MockPage:
    def __init__(self):
        self.route = "/"
        self.views: list = []
        self.update_called = 0

    def go(self, route):
        self.route = route

    def update(self):
        self.update_called += 1


def _make_state():
    from ui_flet.state import AppState
    facade = SimpleNamespace(
        load_ticket_maps=lambda: [],
        connection=SimpleNamespace(execute=lambda *a, **kw: SimpleNamespace(fetchall=lambda: [])),
        load_mastery_breakdowns=lambda: {},
        load_training_snapshot=lambda: SimpleNamespace(queue_items=[]),
        load_sections_overview=lambda: [],
        queries=SimpleNamespace(load_ticket_map=lambda _id: None),
        _settings=SimpleNamespace(),
        _settings_store=SimpleNamespace(workspace_root="."),
        build_ollama_service=lambda: SimpleNamespace(),
    )
    return AppState(page=_MockPage(), facade=facade)


def test_root_redirects_to_tickets():
    from ui_flet.router import on_route_change
    state = _make_state()
    handler = on_route_change(state)

    class _Evt:
        route = "/"

    handler(_Evt())
    assert state.page.route == "/tickets"


def test_training_route_sets_state():
    from ui_flet.router import on_route_change
    state = _make_state()
    handler = on_route_change(state)

    class _Evt:
        route = "/training/tkt-001/plan"

    handler(_Evt())
    assert state.selected_ticket_id == "tkt-001"
    assert state.selected_mode == "plan"


def test_settings_route_builds_view():
    from ui_flet.router import on_route_change
    state = _make_state()
    handler = on_route_change(state)

    class _Evt:
        route = "/settings"

    handler(_Evt())
    # Exactly one view pushed
    assert len(state.page.views) == 1
    assert state.page.views[0].route == "/settings"
