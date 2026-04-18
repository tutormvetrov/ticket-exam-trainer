"""AppState — single source of truth for the Flet UI.

Holds the AppFacade instance, current page, responsive breakpoint, dark-mode
flag, and currently selected ticket_id. Views subscribe to on_breakpoint_change
and on_theme_change; we keep it simple (no reactive framework) — views call
refresh() when they need to rebuild.

Ollama reachability is tracked as a ternary:

* ``None`` — probe not yet run. Treated as "offline" by ``is_ollama_available``
  so the UI never accidentally kicks off a 60s LLM call during the brief
  window between ``main()`` and the probe completing.
* ``True`` / ``False`` — last probe result. Listeners registered with
  ``on_ollama_change`` fire on transitions (including the first ``None →
  False/True`` flip) so badges and workspaces can rebuild.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

import flet as ft

from application.facade import AppFacade


BREAKPOINTS = {
    "compact":    (0, 1280),
    "standard":   (1280, 1920),
    "wide":       (1920, 2560),
    "ultrawide":  (2560, None),
}


def breakpoint_for_width(width: float) -> str:
    for name, (lo, hi) in BREAKPOINTS.items():
        if width >= lo and (hi is None or width < hi):
            return name
    return "standard"


@dataclass
class AppState:
    page: ft.Page
    facade: AppFacade
    is_dark: bool = False
    breakpoint: str = "standard"
    selected_ticket_id: str | None = None
    selected_mode: str = "reading"          # active workspace for training view
    ollama_online: bool | None = None       # None = not probed yet (treated as offline)
    theme_listeners: list[Callable[[], None]] = field(default_factory=list)
    breakpoint_listeners: list[Callable[[str], None]] = field(default_factory=list)
    ollama_listeners: list[Callable[[bool | None], None]] = field(default_factory=list)

    # ---- theme ----
    def toggle_dark(self) -> None:
        self.is_dark = not self.is_dark
        for cb in list(self.theme_listeners):
            try:
                cb()
            except Exception:
                pass

    def on_theme_change(self, callback: Callable[[], None]) -> None:
        self.theme_listeners.append(callback)

    # ---- breakpoint ----
    def update_breakpoint(self, width: float) -> bool:
        new_bp = breakpoint_for_width(width)
        if new_bp != self.breakpoint:
            self.breakpoint = new_bp
            for cb in list(self.breakpoint_listeners):
                try:
                    cb(new_bp)
                except Exception:
                    pass
            return True
        return False

    def on_breakpoint_change(self, callback: Callable[[str], None]) -> None:
        self.breakpoint_listeners.append(callback)

    # ---- ollama probe ----
    def on_ollama_change(self, callback: Callable[[bool | None], None]) -> None:
        self.ollama_listeners.append(callback)

    def is_ollama_available(self) -> bool:
        """Safe predicate — returns False when the probe hasn't run yet."""
        return self.ollama_online is True

    def _notify_ollama_listeners(self) -> None:
        for cb in list(self.ollama_listeners):
            try:
                cb(self.ollama_online)
            except Exception:
                pass

    def probe_ollama(self, timeout: float = 1.5) -> None:
        """Kick off a background probe of the Ollama endpoint.

        Never blocks — a daemon thread runs the probe and writes the result
        back to ``ollama_online``, then fires ``ollama_listeners``. The URL
        is taken from the facade's persisted settings so the Qt and Flet
        apps agree on which endpoint to check.
        """
        from ui_flet.ollama_probe import probe_ollama_now

        settings = getattr(self.facade, "settings", None)
        base_url = getattr(settings, "base_url", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"

        def _worker() -> None:
            try:
                ok = probe_ollama_now(base_url, timeout=timeout)
            except Exception:
                ok = False
            previous = self.ollama_online
            self.ollama_online = bool(ok)
            if previous != self.ollama_online:
                self._notify_ollama_listeners()

        threading.Thread(target=_worker, daemon=True).start()

    # ---- navigation helpers ----
    def go(self, route: str) -> None:
        """Navigate to route. If we're already on it, force a view rebuild
        (Flet's page.go is a no-op for same-route calls, which made nav chip
        clicks look broken when they happened to land on the current route)."""
        current = getattr(self.page, "route", None) or "/"
        if current == route:
            self.refresh()
            return
        self.page.go(route)

    def refresh(self) -> None:
        """Force-rebuild the current view. Used on theme toggle and when a nav
        action resolves to the current route."""
        from ui_flet.router import on_route_change
        route = getattr(self.page, "route", None) or "/tickets"
        # Synthesize a route-change event so the router rebuilds views.
        handler = self.page.on_route_change
        if handler is None:
            handler = on_route_change(self)
            self.page.on_route_change = handler

        class _FakeEvt:
            def __init__(self, r: str) -> None:
                self.route = r

        try:
            handler(_FakeEvt(route))
        except Exception:
            pass

    def open_training(self, ticket_id: str, mode: str = "reading") -> None:
        self.selected_ticket_id = ticket_id
        self.selected_mode = mode
        self.page.go(f"/training/{ticket_id}/{mode}")
