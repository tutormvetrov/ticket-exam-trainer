"""TicketCard - item cell in the tickets catalog.

Shows:
- number badge (#042)
- title (truncated to 2 lines)
- section (small, muted)
- lecturer (optional, muted)
- difficulty pill (1-5, colour-coded)
- mastery pill (percent, colour-coded)
- optional warning badge ("generated") when the backing ticket has
  `source_missing_in_conspect` in its `warnings` attr.

Hover highlight + click handler are wired on the outer container.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette


_DIFFICULTY_COLORS = {
    1: "success",
    2: "success",
    3: "info",
    4: "warning",
    5: "danger",
}


def _ticket_number(ticket_id: str, display_number: int | None = None) -> str:
    """Build the visible ticket number."""
    if display_number is not None:
        return f"#{int(display_number):03d}"

    digits = ""
    for ch in reversed(ticket_id):
        if ch.isdigit():
            digits = ch + digits
        elif digits:
            break
    if digits:
        return f"#{int(digits):03d}"
    short = ticket_id[-5:] if len(ticket_id) > 5 else ticket_id
    return f"#{short}"


def _pill(
    label: str,
    *,
    bg: str,
    fg: str,
    border: str | None = None,
) -> ft.Control:
    return ft.Container(
        content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=fg),
        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=2),
        bgcolor=bg,
        border=ft.border.all(1, border) if border else None,
        border_radius=RADIUS["pill"],
    )


class TicketCard(ft.Container):
    """Clickable ticket cell - rebuildable on theme / selection change."""

    def __init__(
        self,
        state: AppState,
        *,
        ticket_id: str,
        title: str,
        section_title: str,
        lecturer_name: str = "",
        display_number: int | None = None,
        difficulty: int = 1,
        mastery: float = 0.0,
        has_warning: bool = False,
        plan_skeleton_weak: bool = False,
        selected: bool = False,
        on_click: Callable[[str], None] | None = None,
    ) -> None:
        self._state = state
        self._ticket_id = ticket_id
        self._title = title
        self._section_title = section_title
        self._lecturer_name = lecturer_name
        self._display_number = display_number
        self._difficulty = max(1, min(5, int(difficulty or 1)))
        self._mastery = max(0.0, min(1.0, float(mastery or 0.0)))
        self._has_warning = bool(has_warning)
        self._plan_skeleton_weak = bool(plan_skeleton_weak)
        self._selected = bool(selected)
        self._on_click_cb = on_click
        self._hover = False

        super().__init__()
        self._rebuild()

    @property
    def ticket_id(self) -> str:
        return self._ticket_id

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = bool(selected)
        self._rebuild()
        if self.page:
            self.update()

    def _rebuild(self) -> None:
        p = palette(self._state.is_dark)

        number_badge = ft.Container(
            content=ft.Text(
                _ticket_number(self._ticket_id, self._display_number),
                size=12,
                weight=ft.FontWeight.W_700,
                color=p["text_secondary"],
                font_family="JetBrains Mono",
            ),
            padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=2),
            bgcolor=p["bg_sidebar"],
            border_radius=RADIUS["sm"],
        )

        diff_color_key = _DIFFICULTY_COLORS.get(self._difficulty, "info")
        diff_pill = _pill(
            f"●" * self._difficulty,
            bg=p["bg_sidebar"],
            fg=p[diff_color_key],
            border=p["border_soft"],
        )

        mastery_pct = int(round(self._mastery * 100))
        if mastery_pct >= 80:
            mas_fg = p["success"]
        elif mastery_pct >= 40:
            mas_fg = p["info"]
        elif mastery_pct > 0:
            mas_fg = p["warning"]
        else:
            mas_fg = p["text_muted"]
        mastery_pill = _pill(
            f"{mastery_pct}%",
            bg=p["bg_sidebar"],
            fg=mas_fg,
            border=p["border_soft"],
        )

        header_row = ft.Row(
            [number_badge, diff_pill, mastery_pill],
            spacing=SPACE["sm"],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if self._plan_skeleton_weak:
            skeleton_badge = ft.Container(
                content=ft.Text("🔶", size=12),
                padding=ft.padding.symmetric(horizontal=SPACE["xs"], vertical=2),
                bgcolor=p["bg_sidebar"],
                border=ft.border.all(1, p["border_soft"]),
                border_radius=RADIUS["pill"],
                tooltip=TEXT["skeleton.weak.tooltip"],
            )
            header_row.controls.append(skeleton_badge)

        if self._has_warning:
            warning_badge = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=12, color=p["info"]),
                        ft.Text(
                            "сгенерирован",
                            size=10,
                            weight=ft.FontWeight.W_500,
                            color=p["info"],
                        ),
                    ],
                    spacing=SPACE["xs"],
                    tight=True,
                ),
                padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=2),
                bgcolor=p["bg_sidebar"],
                border=ft.border.all(1, p["border_soft"]),
                border_radius=RADIUS["pill"],
                tooltip="Атомы догенерированы: нет полного исходного материала в конспекте",
            )
            header_row.controls.append(warning_badge)

        title_text = ft.Text(
            self._title or "—",
            size=14,
            weight=ft.FontWeight.W_600,
            color=p["text_primary"],
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        meta_parts: list[ft.Control] = []
        if self._section_title:
            meta_parts.append(
                ft.Text(
                    self._section_title,
                    size=12,
                    color=p["text_secondary"],
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )
        if self._lecturer_name:
            meta_parts.append(
                ft.Text(
                    self._lecturer_name,
                    size=11,
                    color=p["text_muted"],
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        body = ft.Column(
            [header_row, title_text] + meta_parts,
            spacing=SPACE["xs"],
            tight=True,
        )

        self.content = body
        self.padding = SPACE["md"]
        self.border_radius = RADIUS["md"]
        self.ink = True
        self.tooltip = TEXT["tickets.open"]

        if self._selected:
            self.bgcolor = p["accent_soft"]
            self.border = ft.border.all(1, p["accent"])
        elif self._hover:
            self.bgcolor = p["bg_elevated"]
            self.border = ft.border.all(1, p["border_medium"])
        else:
            self.bgcolor = p["bg_surface"]
            self.border = ft.border.all(1, p["border_soft"])

        self.animate = ft.Animation(150, ft.AnimationCurve.EASE_OUT)
        self.on_click = self._handle_click if self._on_click_cb else None
        self.on_hover = self._handle_hover

    def _handle_click(self, _event: ft.ControlEvent) -> None:
        if self._on_click_cb:
            self._on_click_cb(self._ticket_id)

    def _handle_hover(self, event: ft.HoverEvent) -> None:
        self._hover = event.data == "true"
        p = palette(self._state.is_dark)
        if self._selected:
            return
        if self._hover:
            self.bgcolor = p["bg_elevated"]
            self.border = ft.border.all(1, p["border_medium"])
        else:
            self.bgcolor = p["bg_surface"]
            self.border = ft.border.all(1, p["border_soft"])
        if self.page:
            self.update()
