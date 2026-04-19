"""AttemptCard — карточка одной попытки в ленте Дневника.

Warm-minimal:
  * Тонкая accent-kromка слева (3px), как в reading-workspace atom-card.
  * Score ≥75 — rust-цвет + W_600; <75 — text_secondary, regular.
  * Delta — стрелка ↑/↓ c иконкой в success/danger; `~` для `±0`.
  * Padding md → lg, чтобы карточка дышала.
"""

from __future__ import annotations

import flet as ft

from application.daily_digest import AttemptCard as DigestAttemptCard
from ui_flet.i18n.ru import TEXT
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


_MODE_LABELS = {
    "reading": "mode.reading.title",
    "plan": "mode.plan.title",
    "cloze": "mode.cloze.title",
    "active-recall": "mode.active_recall.title",
    "state-exam-full": "mode.state_exam_full.title",
    "review": "mode.review.title",
}

_CONFIDENCE_ICONS = {
    "guess": "🤷",
    "idea": "🤔",
    "sure": "💡",
}

_MASTERED_SCORE = 75


def build_attempt_card(state, attempt: DigestAttemptCard) -> ft.Control:
    p = palette(state.is_dark)
    mode_key = _MODE_LABELS.get(attempt.mode_key)
    mode_label = TEXT.get(mode_key, attempt.mode_key) if mode_key else attempt.mode_key

    is_mastered = attempt.score_percent >= _MASTERED_SCORE
    score_color = p["accent"] if is_mastered else p["text_secondary"]
    score_style = text_style("h3", color=score_color) if is_mastered else text_style(
        "body_strong", color=score_color
    )

    header = ft.Row(
        [
            ft.Text(
                attempt.ticket_title,
                style=text_style("body_strong", color=p["text_primary"]),
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(f"{attempt.score_percent}%", style=score_style),
        ],
        spacing=SPACE["sm"],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    meta_parts: list[ft.Control] = [
        ft.Text(mode_label, style=text_style("caption", color=p["text_muted"])),
    ]
    delta_control = _delta_control(p, attempt)
    if delta_control is not None:
        meta_parts.append(delta_control)
    if attempt.confidence:
        icon = _CONFIDENCE_ICONS.get(attempt.confidence, "")
        if icon:
            meta_parts.append(ft.Text(icon, size=12))

    meta_row = ft.Row(meta_parts, spacing=SPACE["sm"], tight=True)

    accent_kromka = ft.Container(
        width=3,
        bgcolor=p["accent"] if is_mastered else p["border_medium"],
        border_radius=RADIUS["sm"],
    )

    card_body = ft.Container(
        content=ft.Column([header, meta_row], spacing=SPACE["xs"], tight=True, expand=True),
        padding=ft.padding.symmetric(horizontal=SPACE["lg"], vertical=SPACE["md"]),
        expand=True,
    )

    return ft.Container(
        content=ft.Row(
            [accent_kromka, card_body],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["md"],
    )


def _delta_control(p: dict, attempt: DigestAttemptCard) -> ft.Control | None:
    if attempt.delta_percent is None:
        return ft.Text(
            TEXT["journal.day.attempt_first"],
            style=text_style("caption", color=p["text_muted"]),
        )
    if attempt.delta_percent == 0:
        return ft.Text("~", style=text_style("caption", color=p["text_muted"]))
    is_up = attempt.delta_percent > 0
    color = p["success"] if is_up else p["danger"]
    icon = ft.Icons.ARROW_UPWARD if is_up else ft.Icons.ARROW_DOWNWARD
    magnitude = abs(attempt.delta_percent)
    return ft.Row(
        [
            ft.Icon(icon, size=12, color=color),
            ft.Text(f"{magnitude}", style=text_style("caption", color=color)),
        ],
        spacing=SPACE["xs"],
        tight=True,
    )
