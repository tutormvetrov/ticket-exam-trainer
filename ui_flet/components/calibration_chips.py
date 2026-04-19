"""CalibrationChips — обязательный виджет «насколько уверен» перед проверкой.

API:
  widget = CalibrationChips(state)
  ... добавить widget.control в layout перед кнопкой «Проверить» ...
  confidence = widget.value        # 'guess' | 'idea' | 'sure' | None
  widget.is_picked()               # True если пользователь сделал выбор

После проверки:
  widget.render_reply(score_percent) → Text с отзывом по калибровке.
"""

from __future__ import annotations

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


CONFIDENCE_GUESS = "guess"
CONFIDENCE_IDEA = "idea"
CONFIDENCE_SURE = "sure"

_VALID = (CONFIDENCE_GUESS, CONFIDENCE_IDEA, CONFIDENCE_SURE)

_ICONS = {
    CONFIDENCE_GUESS: "🤷",
    CONFIDENCE_IDEA: "🤔",
    CONFIDENCE_SURE: "💡",
}

_LABELS = {
    CONFIDENCE_GUESS: "calibration.guess",
    CONFIDENCE_IDEA: "calibration.idea",
    CONFIDENCE_SURE: "calibration.sure",
}


class CalibrationChips:
    """Stateful chip-group. Один из трёх chip'ов обязателен перед проверкой."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.value: str | None = None
        p = palette(state.is_dark)
        self._palette = p

        self.prompt = ft.Text(
            TEXT["calibration.prompt"],
            style=text_style("caption", color=p["text_muted"]),
        )
        self._chip_map: dict[str, ft.Container] = {}
        chip_row = ft.Row(
            [self._build_chip(key) for key in _VALID],
            spacing=SPACE["sm"],
            tight=True,
        )
        self.control = ft.Column(
            [self.prompt, chip_row],
            spacing=SPACE["xs"],
            tight=True,
        )

    def _build_chip(self, key: str) -> ft.Container:
        p = self._palette
        icon_text = _ICONS[key]
        label = TEXT[_LABELS[key]]
        container = ft.Container(
            content=ft.Row(
                [
                    ft.Text(icon_text, size=14),
                    ft.Text(label, style=text_style("caption", color=p["text_primary"])),
                ],
                spacing=SPACE["xs"],
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["xs"] + 2),
            bgcolor=p["bg_elevated"],
            border_radius=RADIUS["pill"],
            border=ft.border.all(1, p["border_soft"]),
            on_click=lambda _e, k=key: self._on_pick(k),
            ink=True,
        )
        self._chip_map[key] = container
        return container

    def _on_pick(self, key: str) -> None:
        self.value = key
        p = self._palette
        for k, chip in self._chip_map.items():
            selected = k == key
            chip.bgcolor = p["accent_soft"] if selected else p["bg_elevated"]
            chip.border = ft.border.all(
                2 if selected else 1,
                p["accent"] if selected else p["border_soft"],
            )
            chip.update()

    def is_picked(self) -> bool:
        return self.value in _VALID

    def render_reply(self, score_percent: int) -> ft.Control:
        """Возвращает контрол с отзывом по калибровке для показа после проверки."""
        p = self._palette
        message = _build_reply_text(self.value, score_percent)
        if not message:
            return ft.Container(width=0, height=0)
        return ft.Container(
            content=ft.Text(message, style=text_style("caption", color=p["text_secondary"])),
            padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
            bgcolor=p["bg_elevated"],
            border_radius=RADIUS["md"],
            border=ft.border.all(1, p["border_soft"]),
        )


def _build_reply_text(confidence: str | None, score_percent: int) -> str:
    """Выбирает reply-строку из i18n по паре (confidence, score_percent)."""
    if confidence not in _VALID:
        return ""
    is_ok = score_percent >= 75
    reply_keys = {
        (CONFIDENCE_SURE, True): "calibration.reply.sure_ok",
        (CONFIDENCE_SURE, False): "calibration.reply.sure_miss",
        (CONFIDENCE_IDEA, True): "calibration.reply.idea_ok",
        (CONFIDENCE_IDEA, False): "calibration.reply.idea_miss",
        (CONFIDENCE_GUESS, True): "calibration.reply.guess_ok",
        (CONFIDENCE_GUESS, False): "calibration.reply.guess_miss",
    }
    key = reply_keys[(confidence, is_ok)]
    template = TEXT[key]
    return template.format(score=score_percent) if "{score}" in template else template
