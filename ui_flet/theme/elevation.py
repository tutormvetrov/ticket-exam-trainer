"""Soft shadow tokens для warm-minimal surfaces.

Три уровня: `flat` (нет тени), `raised` (карточка чуть приподнята),
`floating` (модалка/tile, заметный). Цвет тени — warm-tinted, не чистый
чёрный: на парче это `#2B1F17` c alpha, в тёмной теме — чёрный с
чуть большей alpha (кроме dark-cognac shadow смотрится грязно).

Использование:
    Container(..., shadow=apply_elevation("raised", is_dark))
"""

from __future__ import annotations

import flet as ft


SHADOW_LEVELS: dict[str, dict[str, float]] = {
    "flat":     {"blur": 0.0,  "spread": 0.0, "offset_y": 0.0, "alpha": 0.00},
    "raised":   {"blur": 8.0,  "spread": 0.0, "offset_y": 2.0, "alpha": 0.06},
    "floating": {"blur": 16.0, "spread": 0.0, "offset_y": 4.0, "alpha": 0.10},
}


def apply_elevation(level: str, is_dark: bool) -> ft.BoxShadow | None:
    """Возвращает BoxShadow для `level` или None, если 'flat'.

    None означает «тень не нужна» — передавать напрямую в `shadow=` параметр
    Flet-контейнеров корректно: они воспринимают None как «без тени».
    """
    spec = SHADOW_LEVELS.get(level) or SHADOW_LEVELS["flat"]
    if spec["alpha"] <= 0 or spec["blur"] <= 0:
        return None
    base_rgba = _shadow_rgba(is_dark, spec["alpha"])
    return ft.BoxShadow(
        spread_radius=spec["spread"],
        blur_radius=spec["blur"],
        color=base_rgba,
        offset=ft.Offset(0, spec["offset_y"]),
    )


def _shadow_rgba(is_dark: bool, alpha: float) -> str:
    """Warm-tinted shadow color.

    Тёмная тема — чистый чёрный (парчевый shadow на тёмной поверхности
    выглядит мутно). Светлая — тёплый тёмно-коричневый, чтобы тень
    сочеталась с tокенами, а не прожигала холодным серым.
    """
    alpha_pct = max(0.0, min(1.0, alpha))
    alpha_hex = f"{int(round(alpha_pct * 255)):02X}"
    base_hex = "000000" if is_dark else "2B1F17"
    return f"#{alpha_hex}{base_hex}"
