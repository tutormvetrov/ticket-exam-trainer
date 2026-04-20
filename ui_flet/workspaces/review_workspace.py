"""Review workspace — discuss a finished answer (yours or someone else's).

A single large TextField. On "Рецензировать":
  facade.evaluate_answer(ticket_id, "review", text)
→ result focuses entirely on the ReviewVerdict widget.
"""

from __future__ import annotations

import logging

import flet as ft

from ui_flet.components.calibration_chips import CalibrationChips
from ui_flet.components.ollama_fallback_notice import build_ollama_fallback_notice
from ui_flet.components.review_verdict_widget import build_review_verdict
from ui_flet.components.training_workspace_base import build_workspace_frame, safe_update
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette

_LOG = logging.getLogger(__name__)


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    answer_field = ft.TextField(
        multiline=True,
        min_lines=10,
        max_lines=18,
        hint_text=TEXT["review.placeholder"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
    )
    result_box = ft.Column(spacing=SPACE["md"], visible=False)
    calibration = CalibrationChips(state)
    calibration_warning = ft.Text(
        TEXT["calibration.required"],
        color=p["danger"],
        visible=False,
    )
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
        in_flight["value"] = True
        try:
            result = state.facade.evaluate_answer(
                ticket.ticket_id,
                "review",
                text,
                confidence=calibration.value,
            )
        except Exception:  # noqa: BLE001
            _LOG.exception("evaluate_answer failed mode=review ticket=%s", ticket.ticket_id)
            result_box.controls = [ft.Text(TEXT["result.failed"], color=p["danger"])]
            result_box.visible = True
            safe_update(result_box)
            in_flight["value"] = False
            return

        error = getattr(result, "error", "") or ""
        review_verdict = getattr(result, "review", None)
        score_percent = getattr(result, "score_percent", 0)
        feedback = getattr(result, "feedback", "") or ""
        used_fallback = bool(getattr(result, "used_fallback", False))
        ollama_status = str(getattr(result, "ollama_status", "") or "")

        controls: list[ft.Control] = []
        reply = calibration.render_reply(score_percent)
        if getattr(reply, "visible", True):
            controls.append(reply)
        if error:
            controls.append(ft.Text(error, size=13, color=p["danger"], selectable=True))

        if review_verdict is None:
            # Fallback: facade didn't build a verdict (ollama offline, empty answer)
            controls.append(
                ft.Container(
                    padding=SPACE["md"],
                    bgcolor=p["bg_surface"],
                    border_radius=RADIUS["md"],
                    border=ft.border.all(1, p["border_soft"]),
                    content=ft.Column(
                        spacing=SPACE["xs"],
                        controls=[
                            ft.Text(
                                f"{TEXT['result.score']}: {score_percent}%",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=p["text_primary"],
                            ),
                            *([ft.Text(feedback, size=13, color=p["text_secondary"], selectable=True)] if feedback else []),
                            ft.Text(TEXT["result.review_fallback"], size=12, color=p["text_muted"]),
                        ],
                    ),
                )
            )
        else:
            if used_fallback:
                controls.append(build_ollama_fallback_notice(state, ollama_status))
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
            text=TEXT["review.action"],
            icon=ft.Icons.RATE_REVIEW,
            on_click=_on_check,
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.review.title"],
        instruction=TEXT["mode.review.hint"],
        content=body,
        actions=actions,
    )
