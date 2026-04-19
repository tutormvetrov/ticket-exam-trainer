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


def _make_state(*, with_profile: bool = True):
    from ui_flet.state import AppState
    from application.user_profile import UserProfile
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
    state = AppState(page=_MockPage(), facade=facade)
    if with_profile:
        state.user_profile = UserProfile(name="Миша", avatar_emoji="🦉", created_at="2026-04-19T22:00:00")
    return state


def test_root_redirects_to_journal_when_profile_exists():
    from ui_flet.router import on_route_change
    state = _make_state(with_profile=True)
    handler = on_route_change(state)

    class _Evt:
        route = "/"

    handler(_Evt())
    assert state.page.route == "/journal"


def test_root_redirects_to_onboarding_when_no_profile():
    from ui_flet.router import on_route_change
    state = _make_state(with_profile=False)
    handler = on_route_change(state)

    class _Evt:
        route = "/"

    handler(_Evt())
    assert state.page.route == "/onboarding"


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


def test_route_build_failure_renders_error_view(monkeypatch):
    import ui_flet.router as router

    state = _make_state()
    handler = router.on_route_change(state)

    def _boom(_state):
        raise RuntimeError("tickets blew up")

    monkeypatch.setattr(router, "build_tickets_view", _boom)

    class _Evt:
        route = "/tickets"

    handler(_Evt())

    assert len(state.page.views) == 1
    assert state.page.views[0].route == "/tickets"
    assert state.page.update_called == 1
