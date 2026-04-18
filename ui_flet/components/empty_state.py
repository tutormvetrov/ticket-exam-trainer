"""EmptyState — centered placeholder with emoji + title + hint.

Used when a list is empty (no matches for filters) or no item is selected
(tickets detail panel before a ticket is chosen). Stays quiet visually — no
loud colours, just muted text and a soft emoji glyph.
"""

from __future__ import annotations

import flet as ft

from ui_flet.state import AppState
from ui_flet.theme.tokens import SPACE, palette, text_style


def build_empty_state(
    state: AppState,
    *,
    title: str,
    hint: str = "",
    icon: str = "📄",
    action: ft.Control | None = None,
) -> ft.Control:
    """Build a centered empty-state placeholder.

    Parameters
    ----------
    state:  AppState (for palette).
    title:  main message.
    hint:   secondary muted sentence.
    icon:   emoji shown above the title. Default: document glyph.
    action: optional control (e.g. a button) shown below the hint.
    """
    p = palette(state.is_dark)

    parts: list[ft.Control] = [
        ft.Text(icon, size=48, color=p["text_muted"], text_align=ft.TextAlign.CENTER),
        ft.Text(
            title,
            style=text_style("h3", color=p["text_secondary"]),
            text_align=ft.TextAlign.CENTER,
        ),
    ]
    if hint:
        parts.append(
            ft.Text(
                hint,
                style=text_style("caption", color=p["text_muted"]),
                text_align=ft.TextAlign.CENTER,
                max_lines=3,
            )
        )
    if action is not None:
        parts.append(ft.Container(content=action, padding=ft.padding.only(top=SPACE["sm"])))

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=SPACE["xl"],
        content=ft.Column(
            parts,
            spacing=SPACE["sm"],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
    )
