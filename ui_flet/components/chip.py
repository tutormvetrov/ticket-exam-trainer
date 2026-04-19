"""Chip — compact pill-shaped button used for filters and navigation.

Visual: small ft.Container with border + padding + radius. Active state uses
the accent colour; inactive chips are borderless-on-surface with muted text.
Toggles on click.

Usage:
    Chip(state, "Все", active=True, on_click=lambda: ...)
    Chip(state, "Раздел I", active=False, on_click=lambda key: select(key), value="sec-1")
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, RADIUS, SPACE


class Chip(ft.Container):
    """A small, rounded, clickable pill.

    Parameters
    ----------
    state:
        AppState — used to resolve current palette.
    label:
        Text displayed inside the chip.
    active:
        If True — rendered with accent bg + contrast text.
    on_click:
        Called with (value,) if value is set, else with no args.
    value:
        Optional key passed to on_click callback. Useful for filter chips.
    icon:
        Optional ft.Icons.* glyph shown on the leading side.
    compact:
        If True — smaller horizontal padding (used for navigation chips in top bar).
    """

    def __init__(
        self,
        state: AppState,
        label: str,
        *,
        active: bool = False,
        on_click: Callable[..., None] | None = None,
        value: str | None = None,
        icon: str | None = None,
        compact: bool = False,
    ) -> None:
        self._state = state
        self._label = label
        self._active = active
        self._on_click_cb = on_click
        self._value = value
        self._icon = icon
        self._compact = compact

        super().__init__()
        self._rebuild()

    # ---- public API ----
    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._rebuild()
        if self.page:
            self.update()

    # ---- internal ----
    def _rebuild(self) -> None:
        p = palette(self._state.is_dark)
        bg = p["accent"] if self._active else p["bg_surface"]
        fg = p["bg_surface"] if self._active else p["text_secondary"]
        border_color = p["accent"] if self._active else p["border_soft"]

        children: list[ft.Control] = []
        if self._icon:
            children.append(ft.Icon(self._icon, size=14, color=fg))
        children.append(
            ft.Text(
                self._label,
                size=12,
                weight=ft.FontWeight.W_600 if self._active else ft.FontWeight.W_500,
                color=fg,
            )
        )
        row = ft.Row(children, spacing=SPACE["xs"], tight=True, alignment=ft.MainAxisAlignment.CENTER)

        self.content = row
        self.bgcolor = bg
        self.border = ft.border.all(1, border_color)
        self.border_radius = RADIUS["pill"]
        self.padding = ft.padding.symmetric(
            horizontal=SPACE["sm"] if self._compact else SPACE["md"],
            vertical=SPACE["xs"] if self._compact else SPACE["sm"] - 2,
        )
        self.on_click = self._handle_click if self._on_click_cb else None
        self.ink = True
        self.tooltip = self._label if self._compact else None

    def _handle_click(self, _event: ft.ControlEvent) -> None:
        if not self._on_click_cb:
            return
        if self._value is not None:
            self._on_click_cb(self._value)
        else:
            self._on_click_cb()
