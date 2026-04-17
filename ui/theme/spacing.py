from __future__ import annotations

from PySide6.QtGui import QColor


SPACING = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 20,
    "xl": 24,
    "2xl": 32,
    "3xl": 40,
}

RADII = {
    "xs": 4,
    "sm": 6,
    "md": 10,
    "lg": 14,
    "xl": 18,
    "2xl": 22,
    "pill": 999,
}


# Уровни материальности (тени). См. spec §4.
# Ключи: blur — радиус размытия; dy — смещение по Y; alpha — 0..255
# для warm-brown shadow (light) или чёрного (dark).
ELEVATION = {
    "sm": {"blur": 4, "dy": 1, "alpha_light": 15, "alpha_dark": 60},
    "md": {"blur": 22, "dy": 10, "alpha_light": 45, "alpha_dark": 100},
    "lg": {"blur": 28, "dy": 14, "alpha_light": 90, "alpha_dark": 140},
}


def shadow_color(is_dark: bool, level: str) -> QColor:
    """Warm brown shadow для light / глубокая чёрная для dark.

    Level должен быть одним из 'sm' | 'md' | 'lg'.
    Raises KeyError если level неверный.
    """
    spec = ELEVATION[level]
    alpha = spec["alpha_dark"] if is_dark else spec["alpha_light"]
    if is_dark:
        return QColor(0, 0, 0, alpha)
    return QColor(90, 55, 25, alpha)
