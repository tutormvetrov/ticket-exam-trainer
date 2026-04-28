"""Plan workspace — recover the 6-block answer order.

We show 6 cards (INTRO / THEORY / SKILLS / PRACTICE / EXTRA / CONCLUSION)
in a shuffled starting order. The user reorders via up/down buttons on
each card (numbered-list reorder is more reliable than Flet's unstable
DnD). On "Проверить":
  * compute correct-position count against canonical order
    INTRO → THEORY → PRACTICE → SKILLS → CONCLUSION → EXTRA
  * submit answer_text = "\n".join(current_order_block_codes)
    to facade.evaluate_answer(ticket_id, "plan", answer_text)
"""

from __future__ import annotations

import logging
import random
from typing import List

import flet as ft

from ui_flet.components.training_workspace_base import build_workspace_frame, safe_update
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette

_LOG = logging.getLogger(__name__)

_CANONICAL_ORDER: List[str] = ["intro", "theory", "practice", "skills", "conclusion", "extra"]

_BLOCK_TEXT_KEY = {
    "intro":      "block.intro",
    "theory":     "block.theory",
    "practice":   "block.practice",
    "skills":     "block.skills",
    "conclusion": "block.conclusion",
    "extra":      "block.extra",
}


def _label_for(code: str, ticket) -> str:
    """Prefer ticket's own block title; fall back to canonical TEXT key."""
    for block in ticket.answer_blocks or []:
        if str(block.block_code) == code and (block.title or "").strip():
            return block.title
    return TEXT.get(_BLOCK_TEXT_KEY.get(code, ""), code.title())


def _expected_excerpt(code: str, ticket, limit: int = 140) -> str:
    for block in ticket.answer_blocks or []:
        if str(block.block_code) == code:
            snippet = (block.expected_content or "").strip()
            if not snippet:
                return ""
            if len(snippet) <= limit:
                return snippet
            return snippet[: limit - 1].rstrip() + "…"
    return ""


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    # Initial shuffled order (stable per build; reshuffled on full view rebuild).
    rng = random.Random(hash((ticket.ticket_id, "plan")) & 0xFFFFFFFF)
    initial = _CANONICAL_ORDER[:]
    rng.shuffle(initial)
    while initial == _CANONICAL_ORDER and len(initial) > 1:
        rng.shuffle(initial)

    order: list[str] = list(initial)

    # Slot rebuilt on every move; we mutate `list_column.controls` in place.
    list_column = ft.Column(spacing=SPACE["sm"])
    result_box = ft.Column(spacing=SPACE["sm"], visible=False)

    def _render_rows() -> None:
        rows: list[ft.Control] = []
        for idx, code in enumerate(order):
            is_first = idx == 0
            is_last = idx == len(order) - 1
            expected_excerpt = _expected_excerpt(code, ticket)
            rows.append(_row_card(p, idx, code, ticket, is_first, is_last, expected_excerpt, _move_handlers))
        list_column.controls = rows

    def _move_up(idx: int) -> None:
        if idx <= 0:
            return
        order[idx - 1], order[idx] = order[idx], order[idx - 1]
        _render_rows()
        safe_update(list_column)

    def _move_down(idx: int) -> None:
        if idx >= len(order) - 1:
            return
        order[idx + 1], order[idx] = order[idx], order[idx + 1]
        _render_rows()
        safe_update(list_column)

    _move_handlers = {"up": _move_up, "down": _move_down}

    def _on_check(_evt) -> None:
        correct = sum(1 for i, code in enumerate(order) if _CANONICAL_ORDER[i] == code)
        answer_text = "\n".join(order)
        try:
            result = state.facade.evaluate_answer(ticket.ticket_id, "plan", answer_text)
        except Exception:  # noqa: BLE001
            _LOG.exception("evaluate_answer failed mode=plan ticket=%s", ticket.ticket_id)
            result_box.controls = [
                ft.Text(TEXT["result.failed"], color=p["danger"]),
            ]
            result_box.visible = True
            safe_update(result_box)
            return

        score_percent = getattr(result, "score_percent", 0)
        feedback = getattr(result, "feedback", "") or ""
        weak_points = list(getattr(result, "weak_points", []) or [])

        result_box.controls = [
            ft.Text(
                f"{TEXT['result.positions_correct']}: {correct} из {len(_CANONICAL_ORDER)}",
                size=14,
                weight=ft.FontWeight.W_600,
                color=p["text_primary"],
            ),
            ft.Text(
                f"{TEXT['result.score']}: {score_percent}%",
                size=14,
                color=p["text_secondary"],
            ),
            *([ft.Markdown(feedback, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)] if feedback else []),
            *(
                [
                    ft.Text(TEXT["result.weak_points"], size=13, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                    ft.Column(
                        spacing=SPACE["xs"],
                        controls=[ft.Text(f"• {text}", size=13, color=p["text_secondary"]) for text in weak_points],
                    ),
                ]
                if weak_points
                else []
            ),
        ]
        result_box.visible = True
        safe_update(result_box)

    _render_rows()

    body_controls: list[ft.Control] = []
    if state.ticket_quality_cache.verdict_for(ticket).plan_skeleton_weak:
        body_controls.append(
            ft.Container(
                padding=SPACE["md"],
                bgcolor=p["bg_elevated"],
                border=ft.border.all(1, p["warning"]),
                border_radius=RADIUS["md"],
                content=ft.Row(
                    spacing=SPACE["sm"],
                    controls=[
                        ft.Container(
                            width=8,
                            height=8,
                            margin=ft.margin.only(top=6),
                            border_radius=4,
                            bgcolor=p["warning"],
                        ),
                        ft.Text(
                            TEXT["skeleton.weak.warning"],
                            size=13,
                            color=p["text_secondary"],
                            expand=True,
                            selectable=True,
                            no_wrap=False,
                            overflow=ft.TextOverflow.VISIBLE,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            )
        )
    body_controls.extend(
        [
            list_column,
            ft.Container(
                padding=SPACE["md"],
                bgcolor=p["bg_elevated"],
                border_radius=RADIUS["md"],
                border=ft.border.all(1, p["border_soft"]),
                content=result_box,
                visible=True,
            ),
        ]
    )

    body = ft.Column(
        spacing=SPACE["md"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=body_controls,
    )

    actions = [
        ft.FilledButton(
            text=TEXT["action.check"],
            icon=ft.Icons.CHECK,
            on_click=_on_check,
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.plan.title"],
        instruction=TEXT["mode.plan.hint"],
        content=body,
        actions=actions,
    )


def _row_card(
    palette_map: dict,
    idx: int,
    code: str,
    ticket,
    is_first: bool,
    is_last: bool,
    excerpt: str,
    handlers: dict,
) -> ft.Control:
    label = _label_for(code, ticket)
    up_btn = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD,
        tooltip=TEXT["plan.move_up"],
        disabled=is_first,
        on_click=lambda _e, i=idx: handlers["up"](i),
    )
    down_btn = ft.IconButton(
        icon=ft.Icons.ARROW_DOWNWARD,
        tooltip=TEXT["plan.move_down"],
        disabled=is_last,
        on_click=lambda _e, i=idx: handlers["down"](i),
    )

    text_block: list[ft.Control] = [
        ft.Text(label, size=14, weight=ft.FontWeight.W_600, color=palette_map["text_primary"]),
    ]
    if excerpt:
        text_block.append(
            ft.Markdown(excerpt, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
        )

    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Row(
            spacing=SPACE["md"],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    bgcolor=palette_map["accent_soft"],
                    border_radius=RADIUS["pill"],
                    alignment=ft.alignment.center,
                    content=ft.Text(
                        str(idx + 1),
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=palette_map["accent"],
                    ),
                ),
                ft.Column(spacing=SPACE["xs"], controls=text_block, expand=True),
                ft.Row(spacing=0, controls=[up_btn, down_btn]),
            ],
        ),
    )
