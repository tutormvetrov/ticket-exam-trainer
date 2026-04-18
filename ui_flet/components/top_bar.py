"""TopBar — persistent chrome at the top of every route.

Composition (left → right):
- serif brand title «Тезис» + caption subtitle
- chip-style navigation (Билеты / Тренировка / Настройки), active one highlighted
- spacer
- OllamaStatusBadge (optional — imported lazily from a sibling module written
  by another agent; tolerates its absence gracefully)
- theme switcher (sun/moon icon button)

The TopBar rebuilds itself in-place on theme changes so the whole page doesn't
need a full re-layout just for a colour swap.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from ui_flet.components.chip import Chip
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


# Ordered nav entries: (i18n_key, route, icon)
_NAV_ITEMS = [
    ("nav.tickets", "/tickets", ft.Icons.LIBRARY_BOOKS_OUTLINED),
    ("nav.training", "/training", ft.Icons.EDIT_NOTE_OUTLINED),
    ("nav.settings", "/settings", ft.Icons.SETTINGS_OUTLINED),
]


def _resolve_active_nav(route: str) -> str:
    """Match the current page.route against a nav root."""
    route = (route or "/").lower()
    if route.startswith("/training"):
        return "/training"
    if route.startswith("/settings"):
        return "/settings"
    return "/tickets"


def _load_ollama_badge(state: AppState) -> ft.Control:
    """Try to import OllamaStatusBadge written by the sibling agent.

    If the module isn't there yet or has a different factory signature, return
    an invisible placeholder so the layout doesn't break.
    """
    try:
        from ui_flet.components.ollama_status_badge import (  # type: ignore
            build_ollama_status_badge,
        )
    except Exception:
        return ft.Container(width=0, height=0)

    try:
        return build_ollama_status_badge(state)
    except Exception:
        return ft.Container(width=0, height=0)


def build_top_bar(
    state: AppState,
    *,
    on_nav: Callable[[str], None] | None = None,
) -> ft.Control:
    """Construct a TopBar aware of current route + theme.

    Parameters
    ----------
    state: AppState — reads is_dark, page.route.
    on_nav: optional hook if the caller wants to intercept navigation. If None,
            we call state.go(route) directly.
    """
    p = palette(state.is_dark)
    active_route = _resolve_active_nav(getattr(state.page, "route", "/tickets") or "/tickets")

    def _navigate(route: str) -> None:
        if on_nav is not None:
            on_nav(route)
        else:
            # Training tab without a selected ticket shouldn't dead-end — send
            # the user to the catalog so they can pick one first.
            if route == "/training" and not state.selected_ticket_id:
                state.go("/tickets")
                return
            if route == "/training" and state.selected_ticket_id:
                state.open_training(state.selected_ticket_id, state.selected_mode or "reading")
                return
            state.go(route)

    # Brand
    brand_title = ft.Text(
        TEXT["app_title"],
        style=text_style("h2", color=p["text_primary"]),
    )
    brand_subtitle = ft.Text(
        TEXT["app_subtitle"],
        style=text_style("caption", color=p["text_muted"]),
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    brand_col = ft.Column(
        [brand_title, brand_subtitle],
        spacing=0,
        tight=True,
        alignment=ft.MainAxisAlignment.CENTER,
    )
    brand = ft.Container(content=brand_col, padding=ft.padding.only(right=SPACE["xl"]))

    # Navigation chips
    nav_chips: list[ft.Control] = []
    for key, route, icon in _NAV_ITEMS:
        nav_chips.append(
            Chip(
                state,
                TEXT[key],
                active=(route == active_route),
                icon=icon,
                on_click=lambda _r=route: _navigate(_r),
                compact=True,
            )
        )
    nav_row = ft.Row(nav_chips, spacing=SPACE["sm"], tight=True)

    # Right-side cluster: ollama + theme
    theme_icon = ft.Icons.DARK_MODE_OUTLINED if not state.is_dark else ft.Icons.LIGHT_MODE_OUTLINED
    theme_btn = ft.IconButton(
        icon=theme_icon,
        tooltip=TEXT["action.toggle_theme"],
        icon_color=p["text_secondary"],
        on_click=lambda _e: state.toggle_dark(),
    )

    right_cluster = ft.Row(
        [_load_ollama_badge(state), theme_btn],
        spacing=SPACE["sm"],
        tight=True,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    bar_row = ft.Row(
        [
            brand,
            nav_row,
            ft.Container(expand=True),
            right_cluster,
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=SPACE["md"],
    )

    return ft.Container(
        content=bar_row,
        padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
        bgcolor=p["bg_sidebar"],
        border=ft.border.only(bottom=ft.BorderSide(1, p["border_soft"])),
        border_radius=ft.border_radius.only(bottom_left=0, bottom_right=0),
    )
