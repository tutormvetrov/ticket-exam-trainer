from __future__ import annotations

import logging

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from PySide6.QtGui import QFont, QFontDatabase


_log = logging.getLogger(__name__)


FONT_PRESETS = {
    "georgia": {
        "label": "Georgia",
        "description": "Классическая засечковая гарнитура для комфортного чтения.",
        "families": ["Georgia", "Cambria", "Times New Roman"],
    },
    "cambria": {
        "label": "Cambria",
        "description": "Современнее и чуть плотнее Georgia.",
        "families": ["Cambria", "Georgia", "Times New Roman"],
    },
    "palatino": {
        "label": "Palatino",
        "description": "Гуманистический сериф с мягкими формами.",
        "families": ["Palatino Linotype", "Palatino", "Georgia"],
    },
}

# UI-шрифт для микро-элементов (пиллы, метрики, кнопки). Не выбирается
# пользователем — закреплён за системой.
UI_SANS_FAMILIES = ["Inter", "Segoe UI", "Bahnschrift", "Arial"]


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def resolve_font_family(preset_key: str) -> str:
    preset = FONT_PRESETS.get(preset_key)
    if preset is None:
        _log.info(
            "Unknown font_preset %r; falling back to %r",
            preset_key, DEFAULT_FONT_PRESET,
        )
        preset = FONT_PRESETS[DEFAULT_FONT_PRESET]
    available = set(QFontDatabase.families())
    for family in preset["families"]:
        if family in available:
            return family
    return QFont().defaultFamily()


def resolve_ui_font() -> str:
    available = set(QFontDatabase.families())
    for family in UI_SANS_FAMILIES:
        if family in available:
            return family
    return QFont().defaultFamily()


def build_typography(font_preset: str, font_size: int) -> dict[str, int | str]:
    base_point = _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18)
    body_px = _clamp(round(base_point * 1.4), 13, 22)
    return {
        # Семьи
        "family": resolve_font_family(font_preset),  # serif body
        "ui_family": resolve_ui_font(),              # sans micro-UI
        "base_point": base_point,
        # Serif scale
        "display": _clamp(body_px + 16, 28, 40),        # splash, welcome hero
        "hero": _clamp(body_px + 12, 24, 34),           # legacy — синоним display-small
        "page_title": _clamp(body_px + 10, 22, 30),
        "brand_title": _clamp(body_px + 8, 22, 34),
        "section_title": _clamp(body_px + 4, 18, 24),
        "card_title": _clamp(body_px + 2, 16, 22),
        "body": body_px,
        "subtitle": _clamp(body_px - 1, 12, body_px),
        "brand_subtitle": _clamp(body_px - 1, 12, body_px),
        "page_subtitle": _clamp(body_px, 13, body_px + 1),
        "muted": _clamp(body_px - 1, 12, body_px),
        "window_title": _clamp(body_px, 13, 18),
        # Sans micro-UI scale
        "eyebrow": _clamp(body_px - 4, 9, 12),
        "micro": _clamp(body_px - 3, 10, 13),
        "pill": _clamp(body_px - 2, 11, 16),
        "nav_caption": _clamp(body_px - 1, 12, 17),
        "metric_value": _clamp(body_px + 6, 18, 26),
        "metric_label": _clamp(body_px - 3, 10, 13),
        "status": _clamp(body_px - 1, 12, 18),
        "search": _clamp(body_px + 1, 14, 22),
        "input": body_px,
        "button": body_px,
        "editor": body_px,
        "combo": body_px,
    }


def app_font(font_preset: str = DEFAULT_FONT_PRESET, font_size: int = DEFAULT_FONT_SIZE) -> QFont:
    font = QFont(resolve_font_family(font_preset), _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18))
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font
