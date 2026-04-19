"""CalibrationChips — обязательный виджет «насколько уверен» перед проверкой.

Warm-minimal polish:
  * h3 heading вместо caption-prompt — делает метакогнитивный момент
    видимым.
  * Chip'ы крупнее (padding-lg), gap-md между ними.
  * Selected — accent_soft bg + 2px accent border + W_600 text.
  * Reply после проверки — accent_soft bg + accent border (вместо нейтрального).

API неизменён:
  widget = CalibrationChips(state)
  widget.control                   → контрол для layout
  widget.value                     → 'guess' | 'idea' | 'sure' | None
  widget.is_picked()
  widget.render_reply(score)       → Text с отзывом по калибровке
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

        heading = ft.Text(
            TEXT["calibration.prompt"],
            style=text_style("h3", color=p["text_primary"]),
        )

        self._chip_map: dict[str, ft.Container] = {}
        chip_row = ft.Row(
            [self._build_chip(key) for key in _VALID],
            spacing=SPACE["md"],
            tight=True,
        )
        self.control = ft.Column(
            [heading, chip_row],
            spacing=SPACE["sm"],
            tight=True,
        )

    def _build_chip(self, key: str) -> ft.Container:
        p = self._palette
        icon_text = _ICONS[key]
        label = TEXT[_LABELS[key]]
        label_text = ft.Text(
            label,
            style=ft.TextStyle(
                font_family="Golos Text",
                size=13,
                weight=ft.FontWeight.W_500,
                color=p["text_primary"],
            ),
        )
        container = ft.Container(
            content=ft.Row(
                [
                    ft.Text(icon_text, size=16),
                    label_text,
                ],
                spacing=SPACE["xs"],
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=SPACE["lg"], vertical=SPACE["sm"]),
            bgcolor=p["bg_elevated"],
            border_radius=RADIUS["pill"],
            border=ft.border.all(1, p["border_soft"]),
            on_click=lambda _e, k=key: self._on_pick(k),
            ink=True,
        )
        # Сохраняем ссылку на label_text, чтобы на selected поменять вес.
        container.data = {"label": label_text}
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
            label_text = chip.data.get("label") if isinstance(chip.data, dict) else None
            if isinstance(label_text, ft.Text):
                label_text.style = ft.TextStyle(
                    font_family="Golos Text",
                    size=13,
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                    color=p["text_primary"],
                )
            chip.update()

    def is_picked(self) -> bool:
        return self.value in _VALID

    def render_reply(self, score_percent: int) -> ft.Control:
        """Контрол с отзывом по калибровке для показа после проверки."""
        p = self._palette
        message = _build_reply_text(self.value, score_percent)
        if not message:
            return ft.Container(width=0, height=0)
        return ft.Container(
            content=ft.Text(
                message,
                style=text_style("caption", color=p["text_primary"]),
            ),
            padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["sm"]),
            bgcolor=p["accent_soft"],
            border_radius=RADIUS["md"],
            border=ft.border.all(1, p["accent"]),
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
