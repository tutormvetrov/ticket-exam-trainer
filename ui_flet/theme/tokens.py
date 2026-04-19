"""Design tokens for Flet theme — два «семейства» стиля.

Семейства:
- **warm** — sand paper / rust / cognac (исходный warm-minimal).
- **deco** — ivory cream / forest green / antique brass (Ар-деко + Old Money + летняя свежесть).

Каждое семейство имеет light/dark вариант. Переключение — через
``set_active_family(name)``; вызывается из настроек при старте и при
смене выбора пользователем. Все компоненты тянут палитру через
``palette(is_dark)`` и типографику через ``text_style(token)`` —
оба читают активное семейство, поэтому по UI ничего больше менять не надо.
"""

from __future__ import annotations

import flet as ft

# ── Семейство WARM (исходное warm-minimal) ──────────────────────────────
_WARM_LIGHT: dict[str, str] = {
    "bg_base":        "#F3E8D2",   # sand paper
    "bg_surface":     "#FBF4E4",   # parchment
    "bg_elevated":    "#FFFBF0",
    "bg_sidebar":     "#F7EDD6",
    "accent":         "#A94434",   # rust (Toscana terracotta)
    "accent_hover":   "#8F3528",
    "accent_soft":    "#E8C9BF",
    "accent_secondary": "#9B5A3D", # sienna — итальянская охра
    "ornament":       "#C0843A",   # керамика, азулехо, средиземноморская мозаика
    "text_primary":   "#2B1F17",
    "text_secondary": "#6B5A4A",
    "text_muted":     "#9B8874",
    "border_soft":    "#E3D4B5",
    "border_medium":  "#C9B68F",
    "success":        "#5B8A3A",   # moss / cypress
    "warning":        "#C68B2E",
    "danger":         "#A94434",
    "info":           "#4A6A8A",   # azulejo blue
}

_WARM_DARK: dict[str, str] = {
    "bg_base":        "#241811",   # dark cognac
    "bg_surface":     "#2E1F16",
    "bg_elevated":    "#3A2A1E",
    "bg_sidebar":     "#1F140E",
    "accent":         "#D9735E",
    "accent_hover":   "#E88670",
    "accent_soft":    "#4A2820",
    "accent_secondary": "#C68561", # sienna в тёмной версии
    "ornament":       "#D9A857",   # золотистая охра на тёмном
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

# ── Семейство DECO (Ар-деко + Old Money + летняя свежесть) ─────────────
_DECO_LIGHT: dict[str, str] = {
    "bg_base":        "#F4ECD3",   # ivory cream
    "bg_surface":     "#FBF6E9",   # летняя бумага
    "bg_elevated":    "#FFFBF0",
    "bg_sidebar":     "#EFE6CB",
    "accent":         "#1F4F47",   # deep forest green — Old Money classic
    "accent_hover":   "#16403A",
    "accent_soft":    "#C7DAD3",
    "accent_secondary": "#B8A36D", # antique brass — золотой второй акцент
    "ornament":       "#9B7B2C",   # тёплое золото для декоративных линий и веером
    "text_primary":   "#1F2A2A",   # deep ink
    "text_secondary": "#5A6566",   # slate
    "text_muted":     "#8C8E84",
    "border_soft":    "#E5DCB8",   # aged paper
    "border_medium":  "#B8A36D",   # antique brass
    "success":        "#4F7A3F",
    "warning":        "#B58A2B",
    "danger":         "#9C3B2E",
    "info":           "#3D5C7A",
}

_DECO_DARK: dict[str, str] = {
    "bg_base":        "#142020",   # dark evergreen
    "bg_surface":     "#1B2929",
    "bg_elevated":    "#243333",
    "bg_sidebar":     "#0F1818",
    "accent":         "#A8C7B6",   # sage cream — мягкий приглушённый зелёный
    "accent_hover":   "#C2DBCD",
    "accent_soft":    "#1F4F47",
    "accent_secondary": "#C7B98A", # antique brass на тёмном
    "ornament":       "#D9B05F",   # тёплое золото-веером
    "text_primary":   "#F1E9D0",   # cream
    "text_secondary": "#C7B98A",   # antique brass
    "text_muted":     "#8A8770",
    "border_soft":    "#243333",
    "border_medium":  "#3F5147",
    "success":        "#9DBE8A",
    "warning":        "#D9B05F",
    "danger":         "#C76C5C",
    "info":           "#9FB7CF",
}

_PALETTES: dict[str, dict[str, dict[str, str]]] = {
    "warm": {"light": _WARM_LIGHT, "dark": _WARM_DARK},
    "deco": {"light": _DECO_LIGHT, "dark": _DECO_DARK},
}

# ── Типографика по семействам ──────────────────────────────────────────
_TYPE_WARM: dict[str, dict] = {
    "display":     {"family": "Lora",           "size": 32, "weight": ft.FontWeight.W_600},
    "h1":          {"family": "Lora",           "size": 26, "weight": ft.FontWeight.W_600},
    "h2":          {"family": "Lora",           "size": 20, "weight": ft.FontWeight.W_600},
    "h3":          {"family": "Golos Text",     "size": 16, "weight": ft.FontWeight.W_600},
    "body":        {"family": "Golos Text",     "size": 14, "weight": ft.FontWeight.W_400},
    "body_strong": {"family": "Golos Text",     "size": 14, "weight": ft.FontWeight.W_600},
    "caption":     {"family": "Golos Text",     "size": 12, "weight": ft.FontWeight.W_400},
    "mono":        {"family": "JetBrains Mono", "size": 12, "weight": ft.FontWeight.W_400},
}

# Deco — Playfair Display (Didot-style high-contrast serif, Gatsby/Vogue look)
# для display/h1/h2; Lora — для остального текста (тоже serif, читаемый).
_TYPE_DECO: dict[str, dict] = {
    "display":     {"family": "Playfair Display", "size": 34, "weight": ft.FontWeight.W_600},
    "h1":          {"family": "Playfair Display", "size": 28, "weight": ft.FontWeight.W_600},
    "h2":          {"family": "Playfair Display", "size": 21, "weight": ft.FontWeight.W_500},
    "h3":          {"family": "Lora",              "size": 16, "weight": ft.FontWeight.W_600},
    "body":        {"family": "Lora",              "size": 14, "weight": ft.FontWeight.W_400},
    "body_strong": {"family": "Lora",              "size": 14, "weight": ft.FontWeight.W_600},
    "caption":     {"family": "Lora",              "size": 12, "weight": ft.FontWeight.W_400},
    "mono":        {"family": "JetBrains Mono",    "size": 12, "weight": ft.FontWeight.W_400},
}

_TYPE_BY_FAMILY: dict[str, dict[str, dict]] = {
    "warm": _TYPE_WARM,
    "deco": _TYPE_DECO,
}

SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}
RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}

# ── Активное семейство (модуль-level state) ────────────────────────────
_active_family: str = "warm"
_listeners: list = []


def set_active_family(name: str) -> None:
    """Переключить активное семейство тем. Вызывается из Settings."""
    global _active_family
    if name not in _PALETTES:
        return
    if name == _active_family:
        return
    _active_family = name
    for cb in list(_listeners):
        try:
            cb(name)
        except Exception:
            pass


def get_active_family() -> str:
    return _active_family


def on_family_change(callback) -> None:
    """Подписка на смену семейства (для пере-применения темы)."""
    _listeners.append(callback)


def palette(is_dark: bool) -> dict[str, str]:
    return _PALETTES[_active_family]["dark" if is_dark else "light"]


def text_style(token: str, *, color: str | None = None) -> ft.TextStyle:
    spec = _TYPE_BY_FAMILY[_active_family][token]
    return ft.TextStyle(
        font_family=spec["family"],
        size=spec["size"],
        weight=spec["weight"],
        color=color,
    )


# Backward-compat экспорты (на случай прямых импортов).
COLOR_LIGHT = _WARM_LIGHT
COLOR_DARK = _WARM_DARK
TYPE = _TYPE_WARM
