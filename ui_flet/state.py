"""AppState — single source of truth for the Flet UI.

Holds the AppFacade instance, current page, responsive breakpoint, dark-mode
flag, and currently selected ticket_id. Views subscribe to on_breakpoint_change
and on_theme_change; we keep it simple (no reactive framework) — views call
refresh() when they need to rebuild.
"""

from __future__ import annotations

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
    theme_listeners: list[Callable[[], None]] = field(default_factory=list)
    breakpoint_listeners: list[Callable[[str], None]] = field(default_factory=list)

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

    # ---- navigation helpers ----
    def go(self, route: str) -> None:
        self.page.go(route)

    def open_training(self, ticket_id: str, mode: str = "reading") -> None:
        self.selected_ticket_id = ticket_id
        self.selected_mode = mode
        self.page.go(f"/training/{ticket_id}/{mode}")
