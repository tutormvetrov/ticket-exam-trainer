"""OrnamentalDivider — тонкий декоративный разделитель warm-minimal.

Две variants:
  * `ornamental` (default) — fading-line | «• • •» | fading-line
  * `light` — тонкий однотонный Divider без декора

Используется в onboarding и journal как маркер смысловых секций:
«здесь кончилось приветствие, начинается форма» / «здесь кончился
заголовок утра, начинается очередь дня».
"""

from __future__ import annotations

import flet as ft

from ui_flet.state import AppState
from ui_flet.theme.tokens import SPACE, palette, text_style


def build_ornamental_divider(
    state: AppState,
    *,
    variant: str = "ornamental",
    horizontal_margin: int | None = None,
) -> ft.Control:
    p = palette(state.is_dark)
    margin = SPACE["xl"] if horizontal_margin is None else horizontal_margin

    if variant == "light":
        return ft.Container(
            padding=ft.padding.symmetric(vertical=SPACE["sm"]),
            content=ft.Divider(color=p["border_soft"], thickness=1, height=1),
        )

    line_left = ft.Container(
        expand=True,
        height=1,
        bgcolor=p["border_soft"],
        margin=ft.margin.symmetric(vertical=SPACE["sm"]),
    )
    dots = ft.Container(
        padding=ft.padding.symmetric(horizontal=SPACE["md"]),
        content=ft.Text(
            "• • •",
            style=text_style("caption", color=p["text_muted"]),
        ),
    )
    line_right = ft.Container(
        expand=True,
        height=1,
        bgcolor=p["border_soft"],
        margin=ft.margin.symmetric(vertical=SPACE["sm"]),
    )

    return ft.Container(
        padding=ft.padding.symmetric(horizontal=margin, vertical=SPACE["xs"]),
        content=ft.Row(
            [line_left, dots, line_right],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )
