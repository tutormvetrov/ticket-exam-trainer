"""Review workspace — discuss a finished answer (yours or someone else's).

A single large TextField. On "Рецензировать":
  facade.evaluate_answer(ticket_id, "review", text)
→ result focuses entirely on the ReviewVerdict widget.
"""

from __future__ import annotations

import flet as ft

from ui_flet.components.review_verdict_widget import build_review_verdict
from ui_flet.components.training_workspace_base import build_workspace_frame
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


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

    def _on_check(_evt) -> None:
        text = (answer_field.value or "").strip()
        skip_llm = not state.is_ollama_available()
        try:
            result = state.facade.evaluate_answer(
                ticket.ticket_id,
                "review",
                text,
                skip_llm=skip_llm,
            )
        except Exception as exc:  # noqa: BLE001
            result_box.controls = [ft.Text(str(exc), color=p["danger"])]
            result_box.visible = True
            result_box.update()
            return

        error = getattr(result, "error", "") or ""
        review_verdict = getattr(result, "review", None)
        score_percent = getattr(result, "score_percent", 0)
        feedback = getattr(result, "feedback", "") or ""

        controls: list[ft.Control] = []
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
        result_box.update()

    body = ft.Column(
        spacing=SPACE["md"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            answer_field,
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
