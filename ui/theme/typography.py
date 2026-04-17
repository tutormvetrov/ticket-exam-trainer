from __future__ import annotations

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from PySide6.QtGui import QFont, QFontDatabase


FONT_PRESETS = {
    "segoe": {
        "label": "Segoe UI",
        "description": "Нейтральный системный шрифт для долгой работы.",
        "families": ["Segoe UI", "Arial", "Helvetica Neue"],
    },
    "bahnschrift": {
        "label": "Bahnschrift",
        "description": "Более собранный и современный акцент без декоративности.",
        "families": ["Bahnschrift", "Segoe UI", "Arial"],
    },
    "trebuchet": {
        "label": "Trebuchet MS",
        "description": "Чуть более живой гуманистический гротеск.",
        "families": ["Trebuchet MS", "Segoe UI", "Arial"],
    },
    "verdana": {
        "label": "Verdana",
        "description": "Максимально читабельный вариант для плотного текста.",
        "families": ["Verdana", "Segoe UI", "Arial"],
    },
    "arial": {
        "label": "Arial",
        "description": "Классический запасной нейтральный вариант.",
        "families": ["Arial", "Segoe UI", "Helvetica Neue"],
    },
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def resolve_font_family(preset_key: str) -> str:
    preset = FONT_PRESETS.get(preset_key, FONT_PRESETS[DEFAULT_FONT_PRESET])
    available = set(QFontDatabase.families())
    for family in preset["families"]:
        if family in available:
            return family
    return QFont().defaultFamily()


def build_typography(font_preset: str, font_size: int) -> dict[str, int | str]:
    base_point = _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18)
    body_px = _clamp(round(base_point * 1.4), 13, 22)
    return {
        "family": resolve_font_family(font_preset),
        "base_point": base_point,
        "window_title": _clamp(body_px, 13, 18),
        "brand_title": _clamp(body_px + 8, 22, 34),
        "brand_subtitle": _clamp(body_px - 1, 12, 18),
        "nav_caption": _clamp(body_px - 1, 12, 17),
        "hero": _clamp(body_px + 12, 24, 34),
        "page_subtitle": _clamp(body_px, 13, 20),
        "section_title": _clamp(body_px + 2, 16, 24),
        "card_title": _clamp(body_px + 1, 15, 22),
        "body": body_px,
        "muted": _clamp(body_px - 1, 12, 18),
        "pill": _clamp(body_px - 2, 11, 16),
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
