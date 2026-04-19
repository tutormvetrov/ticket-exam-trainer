"""Warm-minimal кнопочные стили — primary (rust) и ghost (transparent).

В Flet нельзя просто прописать accent-цвет кнопке без ButtonStyle:
ElevatedButton по дефолту material-blue. Этот модуль — единственная
точка правды для всех CTAs в приложении.

Использование:
    ft.ElevatedButton(text="...", style=primary_button(state.is_dark))
    ft.TextButton(text="...", style=ghost_button(state.is_dark))
"""

from __future__ import annotations

import flet as ft

from ui_flet.theme.tokens import RADIUS, SPACE, palette


def primary_button(is_dark: bool) -> ft.ButtonStyle:
    """Rust-bg, parchment-fg. Для основных CTA (Начнём, Начать, Продолжить)."""
    p = palette(is_dark)
    return ft.ButtonStyle(
        color={
            ft.ControlState.DEFAULT: p["bg_elevated"],
            ft.ControlState.HOVERED: p["bg_elevated"],
            ft.ControlState.PRESSED: p["bg_elevated"],
        },
        bgcolor={
            ft.ControlState.DEFAULT: p["accent"],
            ft.ControlState.HOVERED: p["accent_hover"],
            ft.ControlState.PRESSED: p["accent_hover"],
        },
        overlay_color={
            ft.ControlState.DEFAULT: p["accent_hover"],
        },
        shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
        padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
        text_style=ft.TextStyle(
            font_family="Golos Text",
            size=14,
            weight=ft.FontWeight.W_600,
        ),
        elevation={ft.ControlState.DEFAULT: 0},
    )


def ghost_button(is_dark: bool) -> ft.ButtonStyle:
    """Прозрачный фон, text_primary. Для secondary-actions (Назад, Открыть заново)."""
    p = palette(is_dark)
    return ft.ButtonStyle(
        color={
            ft.ControlState.DEFAULT: p["text_secondary"],
            ft.ControlState.HOVERED: p["accent"],
        },
        bgcolor={ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT},
        overlay_color={ft.ControlState.DEFAULT: p["accent_soft"]},
        shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
        padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["xs"] + 2),
        text_style=ft.TextStyle(
            font_family="Golos Text",
            size=13,
            weight=ft.FontWeight.W_500,
        ),
    )
