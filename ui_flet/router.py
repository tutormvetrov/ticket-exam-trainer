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

import logging
from pathlib import Path

import flet as ft

from app.runtime_logging import get_log_path
from ui_flet.state import AppState
from ui_flet.views.dashboard_view import build_dashboard_view
from ui_flet.views.journal_view import build_journal_view
from ui_flet.views.onboarding_view import build_onboarding_view
from ui_flet.views.settings_view import build_settings_view
from ui_flet.views.tickets_view import build_tickets_view
from ui_flet.views.training_view import build_training_view

_LOG = logging.getLogger(__name__)


def on_route_change(state: AppState) -> callable:
    def _handler(event: ft.RouteChangeEvent) -> None:
        page = state.page
        route = event.route or "/"
        _LOG.info("Route change start route=%s", route)
        if state.user_profile is None and route != "/onboarding":
            page.go("/onboarding")
            return
        if route in ("/", ""):
            default_route = "/dashboard" if state.user_profile is not None else "/onboarding"
            page.go(default_route)
            return

        page.views.clear()
        try:
            page.views.append(_build_view(state, route))
        except Exception as exc:
            _LOG.exception("Route build failed route=%s", route)
            page.views.append(_build_error_view(state, route, exc))
        page.update()
        _LOG.info("Route change done route=%s views=%s", route, len(page.views))

    return _handler


def _build_view(state: AppState, route: str) -> ft.View:
    parts = [p for p in route.strip("/").split("/") if p]
    head = parts[0] if parts else "tickets"

    if head == "onboarding":
        body = build_onboarding_view(state)
    elif head == "dashboard":
        body = build_dashboard_view(state)
    elif head == "journal":
        body = build_journal_view(state)
    elif head == "tickets":
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
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[body],
    )


def _build_error_view(state: AppState, route: str, exc: Exception) -> ft.View:
    workspace_root = Path(getattr(state.facade, "workspace_root", Path(".")))
    log_path = get_log_path(workspace_root)
    body = ft.Container(
        expand=True,
        padding=32,
        content=ft.Column(
            [
                ft.Text(
                    "Не удалось открыть экран",
                    size=24,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(f"Маршрут: {route}", selectable=True),
                ft.Text(
                    f"{type(exc).__name__}: {exc}",
                    selectable=True,
                    color=ft.Colors.RED_700,
                ),
                ft.Text(
                    f"Смотрите лог: {log_path}",
                    selectable=True,
                ),
            ],
            spacing=12,
        ),
    )
    return ft.View(
        route=route,
        padding=0,
        bgcolor=ft.Colors.TRANSPARENT,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[body],
    )
