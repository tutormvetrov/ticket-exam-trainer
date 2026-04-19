"""AttemptCard — карточка одной попытки в ленте Дневника.

Показывает: title билета, режим, балл, дельту vs прошлая попытка,
confidence-иконку (если задана). Рендерится только в Journal-view.
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


def build_attempt_card(state, attempt: DigestAttemptCard) -> ft.Control:
    p = palette(state.is_dark)
    mode_key = _MODE_LABELS.get(attempt.mode_key)
    mode_label = TEXT.get(mode_key, attempt.mode_key) if mode_key else attempt.mode_key

    header = ft.Row(
        [
            ft.Text(
                attempt.ticket_title,
                style=text_style("body_strong", color=p["text_primary"]),
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"{attempt.score_percent}%",
                style=text_style("h3", color=_score_color(attempt.score_percent, p)),
            ),
        ],
        spacing=SPACE["sm"],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    meta_parts: list[ft.Control] = [
        ft.Text(mode_label, style=text_style("caption", color=p["text_muted"])),
    ]
    delta_label = _delta_label(attempt)
    if delta_label:
        meta_parts.append(
            ft.Text(
                delta_label,
                style=text_style(
                    "caption",
                    color=_delta_color(attempt.delta_percent, p),
                ),
            )
        )
    if attempt.confidence:
        icon = _CONFIDENCE_ICONS.get(attempt.confidence, "")
        if icon:
            meta_parts.append(ft.Text(icon, size=12))

    meta_row = ft.Row(meta_parts, spacing=SPACE["sm"], tight=True)

    return ft.Container(
        content=ft.Column([header, meta_row], spacing=SPACE["xs"], tight=True),
        padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["sm"]),
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["md"],
    )


def _score_color(score_percent: int, p: dict) -> str:
    if score_percent >= 75:
        return p["success"]
    if score_percent >= 50:
        return p["warning"]
    return p["danger"]


def _delta_label(attempt: DigestAttemptCard) -> str | None:
    if attempt.delta_percent is None:
        return TEXT["journal.day.attempt_first"]
    if attempt.delta_percent > 0:
        return TEXT["journal.day.attempt_delta_up"].format(delta=attempt.delta_percent)
    if attempt.delta_percent < 0:
        return TEXT["journal.day.attempt_delta_down"].format(delta=-attempt.delta_percent)
    return "±0"


def _delta_color(delta: int | None, p: dict) -> str:
    if delta is None:
        return p["text_muted"]
    if delta > 0:
        return p["success"]
    if delta < 0:
        return p["danger"]
    return p["text_muted"]
