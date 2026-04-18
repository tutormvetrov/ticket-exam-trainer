"""Reading workspace — entry point for ticket familiarization.

Shows:
  * Canonical answer summary (selectable)
  * List of knowledge atoms, color-tagged by atom_type
  * Six answer_blocks (non-missing ones) with expected content

Footer: single CTA to jump to the Plan mode — reading is meant to be
a one-off orientation, not a sticky workspace.
"""

from __future__ import annotations

import flet as ft

from ui_flet.components.training_workspace_base import build_workspace_frame
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


# Stable colour hints per atom_type — falls back to `accent` for unknown types.
_ATOM_TYPE_ACCENT = {
    "definition":   "info",
    "features":     "success",
    "examples":     "warning",
    "stages":       "accent",
    "functions":    "info",
    "causes":       "danger",
    "consequences": "danger",
    "classification": "success",
    "process_step": "accent",
    "conclusion":   "success",
}


def _atom_card(palette_map: dict, atom) -> ft.Control:
    accent_key = _ATOM_TYPE_ACCENT.get(str(atom.type), "accent")
    accent_colour = palette_map.get(accent_key, palette_map["accent"])
    type_label = str(atom.type).replace("_", " ")

    header_row: list[ft.Control] = [
        ft.Container(
            width=4,
            bgcolor=accent_colour,
            border_radius=RADIUS["sm"],
        ),
        ft.Text(
            atom.label or type_label,
            size=14,
            weight=ft.FontWeight.W_600,
            color=palette_map["text_primary"],
            expand=True,
        ),
        ft.Container(
            padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
            border_radius=RADIUS["pill"],
            bgcolor=palette_map["bg_elevated"],
            border=ft.border.all(1, accent_colour),
            content=ft.Text(type_label, size=11, color=accent_colour, weight=ft.FontWeight.W_600),
        ),
    ]

    controls: list[ft.Control] = [
        ft.Row(
            controls=header_row,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE["sm"],
        ),
    ]
    if atom.text:
        controls.append(
            ft.Text(
                atom.text,
                size=13,
                color=palette_map["text_secondary"],
                selectable=True,
            )
        )
    keywords = list(atom.keywords or [])
    if keywords:
        controls.append(
            ft.Row(
                wrap=True,
                spacing=SPACE["xs"],
                run_spacing=SPACE["xs"],
                controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
                        bgcolor=palette_map["bg_elevated"],
                        border_radius=RADIUS["pill"],
                        content=ft.Text(kw, size=11, color=palette_map["text_muted"]),
                    )
                    for kw in keywords[:8]
                ],
            )
        )

    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(spacing=SPACE["xs"], controls=controls),
    )


def _answer_block_card(palette_map: dict, block) -> ft.Control:
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(
            spacing=SPACE["xs"],
            controls=[
                ft.Text(
                    block.title or str(block.block_code),
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=palette_map["text_primary"],
                ),
                ft.Text(
                    block.expected_content,
                    size=13,
                    color=palette_map["text_secondary"],
                    selectable=True,
                ),
            ],
        ),
    )


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    summary_control = ft.Container(
        padding=SPACE["md"],
        bgcolor=p["bg_elevated"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Text(
            ticket.canonical_answer_summary or "",
            size=14,
            color=p["text_primary"],
            selectable=True,
        ),
    )

    atom_cards = [_atom_card(p, atom) for atom in (ticket.atoms or [])]
    atoms_section = (
        ft.Column(spacing=SPACE["sm"], controls=atom_cards)
        if atom_cards
        else ft.Text("—", color=p["text_muted"])
    )

    block_cards: list[ft.Control] = []
    for block in ticket.answer_blocks or []:
        if getattr(block, "is_missing", False):
            continue
        if not (block.expected_content or "").strip():
            continue
        block_cards.append(_answer_block_card(p, block))
    blocks_section = (
        ft.Column(spacing=SPACE["sm"], controls=block_cards)
        if block_cards
        else ft.Text("—", color=p["text_muted"])
    )

    body = ft.Column(
        spacing=SPACE["lg"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            ft.Text(TEXT["reading.summary"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
            summary_control,
            ft.Text(TEXT["reading.atoms"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
            atoms_section,
            ft.Text(TEXT["reading.blocks"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
            blocks_section,
        ],
    )

    actions = [
        ft.FilledButton(
            text=f"{TEXT['action.start']} — {TEXT['mode.plan.title']}",
            icon=ft.Icons.ARROW_FORWARD,
            on_click=lambda _: state.go(f"/training/{ticket.ticket_id}/plan"),
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.reading.title"],
        instruction=TEXT["mode.reading.hint"],
        content=body,
        actions=actions,
    )
