"""ReviewVerdictWidget — renders a domain ReviewVerdict.

Displays thesis verdicts (covered / partial / missing) with color-coded
pills, followed by Strengths, Recommendations, and an overall score.

Public helper:
    build_review_verdict(state, verdict) -> ft.Control
"""

from __future__ import annotations

from typing import Iterable

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette

_STATUS_LABEL_KEY = {
    "covered": "result.covered",
    "partial": "result.partial",
    "missing": "result.missing",
}


def _status_colors(palette_map: dict, status: str) -> tuple[str, str]:
    """Return (background, foreground) for a thesis status pill."""
    if status == "covered":
        return palette_map["success"], palette_map["bg_elevated"]
    if status == "partial":
        return palette_map["warning"], palette_map["bg_elevated"]
    return palette_map["danger"], palette_map["bg_elevated"]


def _status_pill(palette_map: dict, status: str) -> ft.Control:
    bg, fg = _status_colors(palette_map, status)
    label = TEXT.get(_STATUS_LABEL_KEY.get(status, "result.missing"), status)
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
        bgcolor=bg,
        border_radius=RADIUS["pill"],
        content=ft.Text(label, size=11, color=fg, weight=ft.FontWeight.W_600),
    )


def _thesis_card(palette_map: dict, verdict) -> ft.Control:
    """Build a single thesis row: label + pill + comment + excerpt."""
    controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Text(
                    verdict.thesis_label or "—",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=palette_map["text_primary"],
                    expand=True,
                ),
                _status_pill(palette_map, verdict.status),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE["sm"],
        ),
    ]
    if verdict.comment:
        controls.append(
            ft.Text(
                verdict.comment,
                size=13,
                color=palette_map["text_secondary"],
                selectable=True,
            )
        )
    if verdict.student_excerpt:
        controls.append(
            ft.Container(
                padding=SPACE["sm"],
                bgcolor=palette_map["bg_elevated"],
                border_radius=RADIUS["sm"],
                border=ft.border.all(1, palette_map["border_soft"]),
                content=ft.Text(
                    f"“{verdict.student_excerpt}”",
                    size=12,
                    color=palette_map["text_muted"],
                    italic=True,
                    selectable=True,
                ),
            )
        )

    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(spacing=SPACE["xs"], controls=controls),
    )


def _bullet_block(palette_map: dict, heading: str, items: Iterable[str]) -> ft.Control | None:
    values = [text for text in (items or []) if text]
    if not values:
        return None
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(
            spacing=SPACE["xs"],
            controls=[
                ft.Text(heading, size=14, weight=ft.FontWeight.W_600, color=palette_map["text_primary"]),
                *[
                    ft.Row(
                        spacing=SPACE["xs"],
                        controls=[
                            ft.Icon(ft.Icons.CIRCLE, size=6, color=palette_map["accent"]),
                            ft.Text(
                                text,
                                size=13,
                                color=palette_map["text_secondary"],
                                selectable=True,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                    for text in values
                ],
            ],
        ),
    )


def _overall_card(palette_map: dict, verdict) -> ft.Control:
    score = int(getattr(verdict, "overall_score", 0) or 0)
    comment = getattr(verdict, "overall_comment", "") or ""
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["accent_soft"],
        border_radius=RADIUS["md"],
        content=ft.Column(
            spacing=SPACE["xs"],
            controls=[
                ft.Row(
                    spacing=SPACE["sm"],
                    controls=[
                        ft.Icon(ft.Icons.GRADE, color=palette_map["accent"], size=18),
                        ft.Text(
                            f"{TEXT['result.score']}: {score}",
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=palette_map["text_primary"],
                        ),
                    ],
                ),
                *(
                    [
                        ft.Text(
                            comment,
                            size=13,
                            color=palette_map["text_secondary"],
                            selectable=True,
                        )
                    ]
                    if comment
                    else []
                ),
            ],
        ),
    )


def build_review_verdict(state: AppState, verdict) -> ft.Control:
    """Render a ReviewVerdict. `verdict` may be None → short fallback."""
    p = palette(state.is_dark)

    if verdict is None:
        return ft.Container(
            padding=SPACE["md"],
            bgcolor=p["bg_surface"],
            border_radius=RADIUS["md"],
            border=ft.border.all(1, p["border_soft"]),
            content=ft.Text(
                TEXT["result.review_fallback"],
                size=13,
                color=p["text_muted"],
            ),
        )

    sections: list[ft.Control] = []
    sections.append(_overall_card(p, verdict))

    # Per-thesis verdicts
    thesis_verdicts = list(getattr(verdict, "thesis_verdicts", []) or [])
    if thesis_verdicts:
        sections.append(
            ft.Text(
                TEXT["result.per_thesis"],
                size=14,
                weight=ft.FontWeight.W_600,
                color=p["text_primary"],
            )
        )
        sections.append(
            ft.Column(
                spacing=SPACE["sm"],
                controls=[_thesis_card(p, tv) for tv in thesis_verdicts],
            )
        )

    strengths_block = _bullet_block(p, TEXT["result.strengths"], getattr(verdict, "strengths", []))
    if strengths_block is not None:
        sections.append(strengths_block)

    recommendations_block = _bullet_block(p, TEXT["result.recommendations"], getattr(verdict, "recommendations", []))
    if recommendations_block is not None:
        sections.append(recommendations_block)

    return ft.Column(spacing=SPACE["md"], controls=sections)
