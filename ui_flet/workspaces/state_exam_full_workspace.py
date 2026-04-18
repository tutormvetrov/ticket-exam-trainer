"""State-exam-full workspace — full written-exam simulation.

UI:
  * count-DOWN timer with 20 / 30 / 40 min presets
  * 6 multiline TextField (intro / theory / practice / skills / conclusion / extra)
  * Submit → combine as "\n\n[Блок]\n\n..." → facade.evaluate_answer

Result panel: overall score, per-block progress bars, criterion_scores,
review verdict widget, weak points.
"""

from __future__ import annotations

import flet as ft

from ui_flet.components.review_verdict_widget import build_review_verdict
from ui_flet.components.timer_widget import TimerWidget
from ui_flet.components.training_workspace_base import build_workspace_frame
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


_BLOCKS = [
    ("intro",      "block.intro"),
    ("theory",     "block.theory"),
    ("practice",   "block.practice"),
    ("skills",     "block.skills"),
    ("conclusion", "block.conclusion"),
    ("extra",      "block.extra"),
]


def _criterion_label(code: str) -> str:
    key = f"criterion.{code}"
    if key in TEXT:
        return TEXT[key]
    return code.replace("_", " ").title()


def _progress_row(palette_map: dict, label: str, percent: int) -> ft.Control:
    percent_clamped = max(0, min(100, int(percent)))
    return ft.Column(
        spacing=SPACE["xs"],
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(label, size=13, color=palette_map["text_primary"]),
                    ft.Text(f"{percent_clamped}%", size=13, color=palette_map["text_secondary"]),
                ],
            ),
            ft.ProgressBar(
                value=percent_clamped / 100.0,
                color=palette_map["accent"],
                bgcolor=palette_map["bg_elevated"],
                height=6,
            ),
        ],
    )


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    fields: dict[str, ft.TextField] = {}
    field_cards: list[ft.Control] = []
    for code, text_key in _BLOCKS:
        title = TEXT.get(text_key, code.title())
        field = ft.TextField(
            multiline=True,
            min_lines=4,
            max_lines=10,
            hint_text=f"{title} {TEXT['state_exam_full.placeholder_suffix']}",
            border_color=p["border_medium"],
            focused_border_color=p["accent"],
            text_size=13,
        )
        fields[code] = field
        field_cards.append(
            ft.Container(
                padding=SPACE["md"],
                bgcolor=p["bg_surface"],
                border_radius=RADIUS["md"],
                border=ft.border.all(1, p["border_soft"]),
                content=ft.Column(
                    spacing=SPACE["xs"],
                    controls=[
                        ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                        field,
                    ],
                ),
            )
        )

    # Count-down timer (default 30 min) + preset chips.
    timer = TimerWidget(state.page, is_dark=state.is_dark, mode="count_down", initial_seconds=30 * 60)

    def _preset(seconds: int) -> ft.Control:
        label = {
            20 * 60: TEXT["timer.suggested_20"],
            30 * 60: TEXT["timer.suggested_30"],
            40 * 60: TEXT["timer.suggested_40"],
        }.get(seconds, f"{seconds // 60} мин")
        return ft.OutlinedButton(
            text=label,
            on_click=lambda _e, s=seconds: timer.set_initial(s),
        )

    preset_row = ft.Row(
        spacing=SPACE["sm"],
        controls=[
            _preset(20 * 60),
            _preset(30 * 60),
            _preset(40 * 60),
        ],
    )

    timer_block = ft.Column(
        spacing=SPACE["xs"],
        controls=[timer.control, preset_row],
    )

    result_box = ft.Column(spacing=SPACE["md"], visible=False)

    def _combine_text() -> str:
        parts: list[str] = []
        for code, text_key in _BLOCKS:
            title = TEXT.get(text_key, code.title())
            value = (fields[code].value or "").strip()
            if not value:
                continue
            parts.append(f"[{title}]\n\n{value}")
        return "\n\n".join(parts)

    def _on_submit(_evt) -> None:
        combined = _combine_text()
        try:
            result = state.facade.evaluate_answer(ticket.ticket_id, "state-exam-full", combined)
        except Exception as exc:  # noqa: BLE001
            result_box.controls = [ft.Text(str(exc), color=p["danger"])]
            result_box.visible = True
            result_box.update()
            return

        timer.pause()
        score_percent = getattr(result, "score_percent", 0)
        feedback = getattr(result, "feedback", "") or ""
        block_scores = dict(getattr(result, "block_scores", {}) or {})
        criterion_scores = dict(getattr(result, "criterion_scores", {}) or {})
        review_verdict = getattr(result, "review", None)
        weak_points = list(getattr(result, "weak_points", []) or [])
        error = getattr(result, "error", "") or ""

        controls: list[ft.Control] = [
            ft.Container(
                padding=SPACE["md"],
                bgcolor=p["accent_soft"],
                border_radius=RADIUS["md"],
                content=ft.Row(
                    spacing=SPACE["sm"],
                    controls=[
                        ft.Icon(ft.Icons.GRADE, color=p["accent"], size=18),
                        ft.Text(
                            f"{TEXT['result.score']}: {score_percent}%",
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=p["text_primary"],
                        ),
                    ],
                ),
            ),
        ]
        if feedback:
            controls.append(ft.Text(feedback, size=13, color=p["text_secondary"], selectable=True))
        if error:
            controls.append(ft.Text(error, size=13, color=p["danger"], selectable=True))

        if block_scores:
            block_rows: list[ft.Control] = []
            for code, text_key in _BLOCKS:
                if code in block_scores:
                    block_rows.append(_progress_row(p, TEXT.get(text_key, code.title()), block_scores[code]))
            if block_rows:
                controls.append(
                    ft.Container(
                        padding=SPACE["md"],
                        bgcolor=p["bg_surface"],
                        border_radius=RADIUS["md"],
                        border=ft.border.all(1, p["border_soft"]),
                        content=ft.Column(
                            spacing=SPACE["sm"],
                            controls=[
                                ft.Text(TEXT["result.by_block"], size=14, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                                *block_rows,
                            ],
                        ),
                    )
                )

        if criterion_scores:
            controls.append(
                ft.Container(
                    padding=SPACE["md"],
                    bgcolor=p["bg_surface"],
                    border_radius=RADIUS["md"],
                    border=ft.border.all(1, p["border_soft"]),
                    content=ft.Column(
                        spacing=SPACE["sm"],
                        controls=[
                            ft.Text(TEXT["result.by_criterion"], size=14, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                            *[_progress_row(p, _criterion_label(code), value) for code, value in criterion_scores.items()],
                        ],
                    ),
                )
            )

        if review_verdict is not None:
            controls.append(build_review_verdict(state, review_verdict))

        if weak_points:
            controls.append(
                ft.Container(
                    padding=SPACE["md"],
                    bgcolor=p["bg_surface"],
                    border_radius=RADIUS["md"],
                    border=ft.border.all(1, p["border_soft"]),
                    content=ft.Column(
                        spacing=SPACE["xs"],
                        controls=[
                            ft.Text(TEXT["result.weak_points"], size=14, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                            *[
                                ft.Row(
                                    spacing=SPACE["xs"],
                                    controls=[
                                        ft.Icon(ft.Icons.CIRCLE, size=6, color=p["warning"]),
                                        ft.Text(text, size=13, color=p["text_secondary"], expand=True, selectable=True),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                )
                                for text in weak_points
                            ],
                        ],
                    ),
                )
            )

        result_box.controls = controls
        result_box.visible = True
        result_box.update()

    body = ft.Column(
        spacing=SPACE["md"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            *field_cards,
            result_box,
        ],
    )

    actions = [
        ft.FilledButton(
            text=TEXT["action.submit"],
            icon=ft.Icons.SEND,
            on_click=_on_submit,
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.state_exam_full.title"],
        instruction=TEXT["mode.state_exam_full.hint"],
        content=body,
        actions=actions,
        timer=timer_block,
    )
