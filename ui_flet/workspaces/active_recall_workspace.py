"""Active-recall workspace — short freeform answer from memory.

UI:
  * optional count-up timer (user-driven: Start/Pause/Reset)
  * large multiline TextField
  * Check button → facade.evaluate_answer(ticket_id, "active-recall", text)

Result area shows score_percent, weak_points, and a ReviewVerdictWidget
when the facade returns a `review` payload.
"""

from __future__ import annotations

import logging

import flet as ft

from ui_flet.components.calibration_chips import CalibrationChips
from ui_flet.components.review_verdict_widget import build_review_verdict
from ui_flet.components.timer_widget import TimerWidget
from ui_flet.components.training_workspace_base import build_workspace_frame, safe_update
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


_LOG = logging.getLogger(__name__)


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    answer_field = ft.TextField(
        multiline=True,
        min_lines=8,
        max_lines=14,
        hint_text=TEXT["active_recall.placeholder"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
    )

    timer = TimerWidget(state.page, is_dark=state.is_dark, mode="count_up", initial_seconds=0)
    result_box = ft.Column(spacing=SPACE["md"], visible=False)
    calibration = CalibrationChips(state)
    calibration_warning = ft.Text(
        TEXT["calibration.required"],
        color=p["danger"],
        visible=False,
    )
    # Guard от двойного клика / race при быстрых повторах «Проверить».
    in_flight = {"value": False}

    def _on_check(_evt) -> None:
        if in_flight["value"]:
            return
        if not calibration.is_picked():
            calibration_warning.visible = True
            safe_update(calibration_warning)
            return
        calibration_warning.visible = False
        safe_update(calibration_warning)
        text = (answer_field.value or "").strip()
        skip_llm = not state.is_ollama_available()
        in_flight["value"] = True
        try:
            result = state.facade.evaluate_answer(
                ticket.ticket_id,
                "active-recall",
                text,
                skip_llm=skip_llm,
                confidence=calibration.value,
            )
        except Exception:  # noqa: BLE001
            _LOG.exception("evaluate_answer failed mode=active-recall ticket=%s", ticket.ticket_id)
            result_box.controls = [ft.Text(TEXT["result.failed"], color=p["danger"])]
            result_box.visible = True
            safe_update(result_box)
            in_flight["value"] = False
            return

        timer.pause()
        score_percent = getattr(result, "score_percent", 0)
        feedback = getattr(result, "feedback", "") or ""
        weak_points = list(getattr(result, "weak_points", []) or [])
        review_verdict = getattr(result, "review", None)
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
            calibration.render_reply(score_percent),
        ]
        if feedback:
            controls.append(
                ft.Text(feedback, size=13, color=p["text_secondary"], selectable=True)
            )
        if error:
            controls.append(
                ft.Text(error, size=13, color=p["danger"], selectable=True)
            )
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
        if review_verdict is not None:
            if skip_llm:
                controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(vertical=SPACE["xs"], horizontal=SPACE["sm"]),
                        bgcolor=p["bg_elevated"],
                        border_radius=RADIUS["pill"],
                        border=ft.border.all(1, p["border_soft"]),
                        content=ft.Row(
                            spacing=SPACE["xs"],
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=p["text_muted"]),
                                ft.Text(
                                    TEXT["result.review_fallback_short"],
                                    size=12,
                                    color=p["text_secondary"],
                                ),
                            ],
                        ),
                    )
                )
            controls.append(build_review_verdict(state, review_verdict))

        result_box.controls = controls
        result_box.visible = True
        safe_update(result_box)
        in_flight["value"] = False

    body = ft.Column(
        spacing=SPACE["md"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            answer_field,
            calibration.control,
            calibration_warning,
            result_box,
        ],
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
        title=TEXT["mode.active_recall.title"],
        instruction=TEXT["mode.active_recall.hint"],
        content=body,
        actions=actions,
        timer=timer.control,
    )
