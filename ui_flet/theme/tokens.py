"""Design tokens for warm-minimal Flet theme.

Two palettes (light + dark) plus typography, spacing, radius. Every Flet
component reads from here — no hardcoded colors or font sizes elsewhere.

The dark palette is desaturated warm (cognac leather), not ink black —
it preserves the emotional continuity with the light version.
"""

from __future__ import annotations

import flet as ft

COLOR_LIGHT: dict[str, str] = {
    "bg_base":        "#F3E8D2",   # sand paper
    "bg_surface":     "#FBF4E4",   # parchment
    "bg_elevated":    "#FFFBF0",
    "bg_sidebar":     "#F7EDD6",
    "accent":         "#A94434",   # rust
    "accent_hover":   "#8F3528",
    "accent_soft":    "#E8C9BF",
    "text_primary":   "#2B1F17",
    "text_secondary": "#6B5A4A",
    "text_muted":     "#9B8874",
    "border_soft":    "#E3D4B5",
    "border_medium":  "#C9B68F",
    "success":        "#5B8A3A",   # moss
    "warning":        "#C68B2E",
    "danger":         "#A94434",
    "info":           "#4A6A8A",
}

COLOR_DARK: dict[str, str] = {
    "bg_base":        "#241811",   # dark cognac
    "bg_surface":     "#2E1F16",
    "bg_elevated":    "#3A2A1E",
    "bg_sidebar":     "#1F140E",
    "accent":         "#D9735E",   # desaturated rust
    "accent_hover":   "#E88670",
    "accent_soft":    "#4A2820",
    "text_primary":   "#F3E8D2",
    "text_secondary": "#C9B68F",
    "text_muted":     "#8F7D63",
    "border_soft":    "#3D2C1F",
    "border_medium":  "#553F2C",
    "success":        "#8EB266",
    "warning":        "#D9A857",
    "danger":         "#D9735E",
    "info":           "#7FA1C7",
}

TYPE = {
    "display":     {"family": "Lora",           "size": 32, "weight": ft.FontWeight.W_600},
    "h1":          {"family": "Lora",           "size": 26, "weight": ft.FontWeight.W_600},
    "h2":          {"family": "Lora",           "size": 20, "weight": ft.FontWeight.W_600},
    "h3":          {"family": "Golos Text",     "size": 16, "weight": ft.FontWeight.W_600},
    "body":        {"family": "Golos Text",     "size": 14, "weight": ft.FontWeight.W_400},
    "body_strong": {"family": "Golos Text",     "size": 14, "weight": ft.FontWeight.W_600},
    "caption":     {"family": "Golos Text",     "size": 12, "weight": ft.FontWeight.W_400},
    "mono":        {"family": "JetBrains Mono", "size": 12, "weight": ft.FontWeight.W_400},
}

SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}

RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}


def palette(is_dark: bool) -> dict[str, str]:
    return COLOR_DARK if is_dark else COLOR_LIGHT


def text_style(token: str, *, color: str | None = None) -> ft.TextStyle:
    spec = TYPE[token]
    return ft.TextStyle(
        font_family=spec["family"],
        size=spec["size"],
        weight=spec["weight"],
        color=color,
    )
