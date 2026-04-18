"""Training workspace base frame.

Common chrome for all six training workspaces: a surface container with
a header (title + instruction), optional timer slot, a scrollable content
area, and a footer row with action buttons. All visual tokens come from
`ui_flet.theme.tokens` — no hardcoded colors/sizes.
"""

from __future__ import annotations

from typing import Iterable

import flet as ft

from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


def build_workspace_frame(
    state: AppState,
    *,
    title: str,
    instruction: str = "",
    content: ft.Control | None = None,
    actions: Iterable[ft.Control] | None = None,
    timer: ft.Control | None = None,
) -> ft.Control:
    """Return a Container wrapping a workspace body.

    Layout (top → bottom):
      header   — title (h2) + optional instruction (body, muted)
      timer    — optional (state-exam-full, active-recall)
      content  — scrollable main area (card, text field, etc.)
      actions  — button row (flush-right)
    """
    p = palette(state.is_dark)
    rows: list[ft.Control] = []

    rows.append(
        ft.Column(
            spacing=SPACE["xs"],
            controls=[
                ft.Text(title, size=20, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                *(
                    [ft.Text(instruction, size=13, color=p["text_secondary"])]
                    if instruction
                    else []
                ),
            ],
        )
    )

    if timer is not None:
        rows.append(timer)

    if content is not None:
        rows.append(
            ft.Container(
                content=content,
                padding=ft.padding.only(top=SPACE["sm"]),
                expand=True,
            )
        )

    action_list = list(actions or [])
    if action_list:
        rows.append(
            ft.Row(
                controls=action_list,
                alignment=ft.MainAxisAlignment.END,
                spacing=SPACE["sm"],
            )
        )

    return ft.Container(
        padding=SPACE["xl"],
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["md"],
            controls=rows,
            expand=True,
        ),
        expand=True,
    )
