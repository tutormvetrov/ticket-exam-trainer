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

from pathlib import Path
from typing import Callable

import flet as ft

from ui_flet.components.chip import Chip
from ui_flet.components.decorative import thin_top_border
from ui_flet.components.feedback import show_snackbar
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import SPACE, get_active_family, palette, text_style

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _brand_icon_path() -> str:
    """Путь к brand-иконке для текущего семейства тем."""
    if get_active_family() == "deco":
        return str(_REPO_ROOT / "assets" / "logo" / "tezis-deco.png")
    return str(_REPO_ROOT / "assets" / "icon.png")


def _course_short_title(state: AppState) -> str | None:
    """Короткое название активного курса из COURSE_CATALOG (для подзаголовка)."""
    from application.user_profile import COURSE_CATALOG

    eid = getattr(state, "active_exam_id", None)
    if not eid:
        return None
    for course in COURSE_CATALOG:
        if course.get("exam_id") == eid:
            return course.get("short_title")
    return None


# Ordered nav entries: (i18n_key, route, icon)
_NAV_ITEMS = [
    ("nav.dashboard", "/dashboard", ft.Icons.DASHBOARD_OUTLINED),
    ("nav.journal",   "/journal",   ft.Icons.BOOK_OUTLINED),
    ("nav.tickets",   "/tickets",   ft.Icons.LIBRARY_BOOKS_OUTLINED),
    ("nav.training",  "/training",  ft.Icons.EDIT_NOTE_OUTLINED),
    ("nav.settings",  "/settings",  ft.Icons.SETTINGS_OUTLINED),
]


def _resolve_active_nav(route: str) -> str:
    """Match the current page.route against a nav root."""
    route = (route or "/").lower()
    if route.startswith("/dashboard"):
        return "/dashboard"
    if route.startswith("/journal"):
        return "/journal"
    if route.startswith("/training"):
        return "/training"
    if route.startswith("/settings"):
        return "/settings"
    if route.startswith("/tickets"):
        return "/tickets"
    return "/dashboard"


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
            return
        # Training tab без выбранного билета ведёт в каталог и тихо
        # подсказывает «сначала выбери билет», чтобы клик чувствовался
        # намеренным и дружелюбным, а не молчаливым.
        if route == "/training" and not state.selected_ticket_id:
            show_snackbar(state, TEXT["nav.training.needs_ticket"])
            state.go("/tickets")
            return
        if route == "/training" and state.selected_ticket_id:
            state.open_training(state.selected_ticket_id, state.selected_mode or "reading")
            return
        state.go(route)

    # Brand: иконка слева + двухстрочный текст «Тезис / подзаголовок».
    # Подзаголовок динамичный: для пользователя с активным курсом — короткое
    # «название курса», иначе общий «Подготовка к письменному госэкзамену».
    brand_title = ft.Text(
        TEXT["app_title"],
        style=text_style("h2", color=p["text_primary"]),
    )
    subtitle_text = _course_short_title(state) or TEXT["app_subtitle"]
    brand_subtitle = ft.Text(
        subtitle_text,
        style=text_style("caption", color=p["text_muted"]),
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    brand_text_col = ft.Column(
        [brand_title, brand_subtitle],
        spacing=0,
        tight=True,
        alignment=ft.MainAxisAlignment.CENTER,
    )
    brand_icon = ft.Image(
        src=_brand_icon_path(),
        width=44, height=44,
        fit=ft.ImageFit.CONTAIN,
    )
    brand_row = ft.Row(
        [brand_icon, brand_text_col],
        spacing=SPACE["sm"],
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    brand = ft.Container(content=brand_row, padding=ft.padding.only(right=SPACE["xl"]))

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

    right_items: list[ft.Control] = []
    profile = getattr(state, "user_profile", None)
    if profile is not None:
        profile_chip = ft.Container(
            content=ft.Row(
                [
                    ft.Text(profile.avatar_emoji, size=16),
                    ft.Text(
                        profile.name,
                        style=text_style("caption", color=p["text_secondary"]),
                    ),
                ],
                spacing=SPACE["xs"],
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
        )
        right_items.append(profile_chip)
    right_items.extend([_load_ollama_badge(state), theme_btn])

    right_cluster = ft.Row(
        right_items,
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

    # Декоративная нижняя граница TopBar — двойная линия для deco,
    # azulejo-точки для warm. Заменяет простую линию для большего вкуса.
    bar_block = ft.Container(
        content=bar_row,
        padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
        bgcolor=p["bg_sidebar"],
    )
    return ft.Column(
        [bar_block, thin_top_border(state)],
        spacing=0,
        tight=True,
    )
