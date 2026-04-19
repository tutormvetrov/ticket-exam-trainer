"""Onboarding view — первый запуск, создание локального профиля.

Одноэкранный flow: имя + 12 emoji-аватаров + кнопка «Начнём».

После успешного сохранения профиля происходит редирект на `/journal`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from application.user_profile import (
    AVATAR_CHOICES,
    ProfileStore,
    build_profile,
    validate_name,
)
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


_LOG = logging.getLogger(__name__)


def _profile_path(state: AppState) -> Path:
    workspace_root = Path(getattr(state.facade, "workspace_root", Path(".")))
    return workspace_root / "app_data" / "profile.json"


def build_onboarding_view(state: AppState) -> ft.Control:
    p = palette(state.is_dark)
    store = ProfileStore(_profile_path(state))

    picked_avatar: dict[str, str | None] = {"value": None}

    name_field = ft.TextField(
        label=TEXT["onboarding.name_label"],
        hint_text=TEXT["onboarding.name_hint"],
        autofocus=True,
        border_radius=RADIUS["md"],
        width=420,
    )

    error_text = ft.Text(
        "",
        style=text_style("caption", color=p["danger"]),
        visible=False,
    )

    avatar_buttons: list[ft.Control] = []

    def _rebuild_avatar_row() -> None:
        """Ручная пере-отрисовка — `IconButton` selected-state в Flet капризен."""
        avatar_buttons.clear()
        for avatar in AVATAR_CHOICES:
            selected = picked_avatar["value"] == avatar
            avatar_buttons.append(_avatar_button(avatar, selected, _on_pick_avatar, p))
        avatar_row.controls = avatar_buttons
        avatar_row.update()

    def _on_pick_avatar(avatar: str) -> None:
        picked_avatar["value"] = avatar
        _rebuild_avatar_row()
        if error_text.visible and "аватар" in error_text.value.lower():
            error_text.visible = False
            error_text.update()

    avatar_row = ft.Row(
        [],
        spacing=SPACE["sm"],
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
    )
    for avatar in AVATAR_CHOICES:
        avatar_row.controls.append(_avatar_button(avatar, False, _on_pick_avatar, p))

    def _on_start(_evt: ft.ControlEvent) -> None:
        raw_name = name_field.value or ""
        ok, err_msg = validate_name(raw_name)
        if not ok:
            error_text.value = err_msg
            error_text.visible = True
            error_text.update()
            return
        if not picked_avatar["value"]:
            error_text.value = TEXT["onboarding.avatar_not_picked"]
            error_text.visible = True
            error_text.update()
            return

        profile = build_profile(raw_name, picked_avatar["value"])
        try:
            store.save(profile)
        except Exception:
            _LOG.exception("Profile save failed")
            error_text.value = "Не удалось сохранить профиль. Проверь права на папку приложения."
            error_text.visible = True
            error_text.update()
            return

        _LOG.info("Profile created name=%s avatar=%s", profile.name, profile.avatar_emoji)
        state.user_profile = profile
        state.go("/journal")

    start_button = ft.ElevatedButton(
        text=TEXT["onboarding.start"],
        on_click=_on_start,
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
            shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
        ),
    )

    welcome = ft.Text(TEXT["onboarding.welcome"], style=text_style("h1", color=p["text_primary"]))
    subtitle = ft.Text(
        TEXT["onboarding.subtitle"],
        style=text_style("body", color=p["text_secondary"]),
        max_lines=3,
    )
    avatar_label = ft.Text(
        TEXT["onboarding.avatar_label"],
        style=text_style("h3", color=p["text_primary"]),
    )
    avatar_hint = ft.Text(
        TEXT["onboarding.avatar_hint"],
        style=text_style("caption", color=p["text_muted"]),
    )

    content = ft.Column(
        [
            welcome,
            subtitle,
            ft.Container(height=SPACE["lg"]),
            name_field,
            ft.Container(height=SPACE["md"]),
            avatar_label,
            avatar_hint,
            ft.Container(height=SPACE["sm"]),
            avatar_row,
            ft.Container(height=SPACE["lg"]),
            error_text,
            start_button,
        ],
        spacing=SPACE["sm"],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    card = ft.Container(
        content=content,
        padding=ft.padding.all(SPACE["xl"]),
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["lg"],
        width=560,
    )

    return ft.Container(
        expand=True,
        bgcolor=p["bg_base"],
        alignment=ft.alignment.center,
        content=card,
    )


def _avatar_button(
    avatar: str,
    selected: bool,
    on_pick,
    p: dict,
) -> ft.Control:
    size = 56
    return ft.Container(
        content=ft.Text(avatar, size=28, text_align=ft.TextAlign.CENTER),
        width=size,
        height=size,
        alignment=ft.alignment.center,
        border_radius=RADIUS["md"],
        bgcolor=p["accent_soft"] if selected else p["bg_elevated"],
        border=ft.border.all(
            2 if selected else 1,
            p["accent"] if selected else p["border_soft"],
        ),
        on_click=lambda _e, a=avatar: on_pick(a),
        tooltip=avatar,
    )
