"""Three-route router for Flet page navigation.

Routes:
    /                    → /tickets  (redirect)
    /tickets             → TicketsView (catalog)
    /training/<id>/<mode> → TrainingView (selected ticket + mode workspace)
    /settings            → SettingsView

We rebuild the view each time the route changes — this is the simplest and
avoids stale state between navigations. Views are cheap to construct.
"""

from __future__ import annotations

import flet as ft

from ui_flet.state import AppState
from ui_flet.views.tickets_view import build_tickets_view
from ui_flet.views.training_view import build_training_view
from ui_flet.views.settings_view import build_settings_view


def on_route_change(state: AppState) -> callable:
    def _handler(event: ft.RouteChangeEvent) -> None:
        page = state.page
        route = event.route or "/"
        if route in ("/", ""):
            page.go("/tickets")
            return

        page.views.clear()
        page.views.append(_build_view(state, route))
        page.update()

    return _handler


def _build_view(state: AppState, route: str) -> ft.View:
    parts = [p for p in route.strip("/").split("/") if p]
    head = parts[0] if parts else "tickets"

    if head == "tickets":
        body = build_tickets_view(state)
    elif head == "training" and len(parts) >= 2:
        ticket_id = parts[1]
        mode = parts[2] if len(parts) >= 3 else state.selected_mode
        state.selected_ticket_id = ticket_id
        state.selected_mode = mode
        body = build_training_view(state, ticket_id=ticket_id, mode_key=mode)
    elif head == "settings":
        body = build_settings_view(state)
    else:
        body = ft.Text(f"Неизвестный маршрут: {route}")

    return ft.View(
        route=route,
        padding=0,
        bgcolor=ft.Colors.TRANSPARENT,
        controls=[body],
    )
