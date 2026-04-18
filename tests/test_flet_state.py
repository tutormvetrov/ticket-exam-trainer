"""AppState breakpoint logic + theme toggle + listener semantics."""

from __future__ import annotations

from types import SimpleNamespace


class _MockPage:
    def __init__(self):
        self.route = "/"
    def go(self, route: str) -> None:
        self.route = route
    def update(self) -> None:
        pass


def _make_state():
    from ui_flet.state import AppState
    page = _MockPage()
    facade = SimpleNamespace()
    return AppState(page=page, facade=facade)


def test_breakpoint_for_width_covers_full_range():
    from ui_flet.state import breakpoint_for_width
    assert breakpoint_for_width(800) == "compact"
    assert breakpoint_for_width(1280) == "standard"
    assert breakpoint_for_width(1600) == "standard"
    assert breakpoint_for_width(1920) == "wide"
    assert breakpoint_for_width(2200) == "wide"
    assert breakpoint_for_width(2560) == "ultrawide"
    assert breakpoint_for_width(3840) == "ultrawide"


def test_toggle_dark_fires_listeners_once():
    state = _make_state()
    hits = {"count": 0}
    state.on_theme_change(lambda: hits.__setitem__("count", hits["count"] + 1))
    assert state.is_dark is False
    state.toggle_dark()
    assert state.is_dark is True
    assert hits["count"] == 1


def test_update_breakpoint_fires_listeners_only_on_change():
    state = _make_state()
    hits: list[str] = []
    state.on_breakpoint_change(lambda bp: hits.append(bp))
    state.update_breakpoint(1200.0)  # compact
    state.update_breakpoint(1250.0)  # still compact, no fire
    state.update_breakpoint(1500.0)  # standard, fires
    state.update_breakpoint(3000.0)  # ultrawide, fires
    assert hits == ["compact", "standard", "ultrawide"]


def test_open_training_updates_selection_and_route():
    state = _make_state()
    state.open_training("tkt-042", mode="plan")
    assert state.selected_ticket_id == "tkt-042"
    assert state.selected_mode == "plan"
    assert state.page.route == "/training/tkt-042/plan"


def test_listener_exception_does_not_break_chain():
    state = _make_state()
    hits: list[str] = []
    state.on_theme_change(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    state.on_theme_change(lambda: hits.append("ok"))
    state.toggle_dark()
    assert hits == ["ok"]
