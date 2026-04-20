from __future__ import annotations

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette


def _fallback_message(state: AppState, ollama_status: str) -> str:
    settings = getattr(state.facade, "settings", None)
    model_name = getattr(settings, "model", "") or ""
    ollama_enabled = bool(getattr(settings, "ollama_enabled", True))
    if not ollama_enabled:
        return TEXT["result.review_fallback_reason.disabled"]
    if ollama_status == "not_installed":
        return TEXT["result.review_fallback_reason.not_installed"]
    if ollama_status == "installed_not_running":
        return TEXT["result.review_fallback_reason.installed_not_running"]
    if ollama_status == "model_missing":
        return TEXT["result.review_fallback_reason.model_missing"].format(model=model_name or "qwen3:8b")
    return TEXT["result.review_fallback_reason.error"]


def build_ollama_fallback_notice(state: AppState, ollama_status: str) -> ft.Control:
    p = palette(state.is_dark)
    message = _fallback_message(state, ollama_status)
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=p["bg_elevated"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["sm"],
            controls=[
                ft.Row(
                    spacing=SPACE["xs"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=p["warning"]),
                        ft.Text(
                            TEXT["result.review_fallback_short"],
                            size=12,
                            color=p["text_secondary"],
                            weight=ft.FontWeight.W_600,
                        ),
                    ],
                ),
                ft.Text(
                    message,
                    size=12,
                    color=p["text_secondary"],
                    selectable=True,
                ),
                ft.TextButton(
                    text=TEXT["result.review_setup_action"],
                    icon=ft.Icons.SETTINGS,
                    on_click=lambda _e: state.go("/settings"),
                ),
            ],
        ),
    )
