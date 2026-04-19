"""Onboarding view — первый запуск, создание локального профиля.

Макет (display-first, warm-minimal):
    ┌───────────────────────────────┐
    │        Тезис (display)        │   brand-mark
    │ caption muted subtitle        │
    │           • • •               │   ornamental divider
    │ Привет. Давай познакомимся.   │   welcome (display)
    │ body subtitle                 │
    │                               │
    │ [ Как к тебе обращаться? __ ] │   name field
    │                               │
    │ Выбери аватар (h3)            │
    │ caption muted hint            │
    │ 🦉 🐺 🦊 🐻 🦁 🐢             │   12 avatars 2×6
    │ 🦅 🐉 🌲 🌊 🔥 ⚡              │
    │                               │
    │         [ Начнём ]            │   primary button
    └───────────────────────────────┘

Card: bg_surface на bg_base, raised elevation, padding-2xl, width=560.
Fade-in 200ms если не compact breakpoint.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from application.user_profile import (
    AVATAR_CHOICES,
    COURSE_CATALOG,
    DEFAULT_EXAM_ID,
    ProfileStore,
    build_profile,
    validate_name,
)
from ui_flet.components.decorative import divider as decorative_divider
from ui_flet.components.decorative import sunburst_badge
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.buttons import primary_button
from ui_flet.theme.elevation import apply_elevation
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


def _profile_path(state: AppState) -> Path:
    workspace_root = Path(getattr(state.facade, "workspace_root", Path(".")))
    return workspace_root / "app_data" / "profile.json"


def build_onboarding_view(state: AppState) -> ft.Control:
    p = palette(state.is_dark)
    store = ProfileStore(_profile_path(state))

    picked_avatar: dict[str, str | None] = {"value": None}
    picked_course: dict[str, str] = {"value": DEFAULT_EXAM_ID}

    name_field = ft.TextField(
        label=TEXT["onboarding.name_label"],
        hint_text=TEXT["onboarding.name_hint"],
        autofocus=True,
        border_radius=RADIUS["md"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
        width=460,
    )

    error_text = ft.Text(
        "",
        style=text_style("caption", color=p["danger"]),
        visible=False,
    )

    avatar_row = ft.Row(
        [],
        spacing=SPACE["sm"],
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    def _rebuild_avatars() -> None:
        avatar_row.controls = [
            _avatar_button(avatar, picked_avatar["value"] == avatar, _on_pick_avatar, p)
            for avatar in AVATAR_CHOICES
        ]
        if avatar_row.page:
            avatar_row.update()

    def _on_pick_avatar(avatar: str) -> None:
        picked_avatar["value"] = avatar
        _rebuild_avatars()
        if error_text.visible and "аватар" in (error_text.value or "").lower():
            error_text.visible = False
            error_text.update()

    _rebuild_avatars()

    # ---------- course picker ----------
    course_row = ft.Row(
        [],
        spacing=SPACE["md"],
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    def _rebuild_courses() -> None:
        course_row.controls = [
            _course_card(
                course,
                selected=(picked_course["value"] == course["exam_id"]),
                on_pick=_on_pick_course,
                p=p,
            )
            for course in COURSE_CATALOG
        ]
        if course_row.page:
            course_row.update()

    def _on_pick_course(exam_id: str) -> None:
        picked_course["value"] = exam_id
        _rebuild_courses()

    _rebuild_courses()

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

        profile = build_profile(
            raw_name,
            picked_avatar["value"],
            active_exam_id=picked_course["value"],
        )
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

    # ---------- sections ----------
    brand_title = ft.Text(
        TEXT["app_title"],
        style=text_style("display", color=p["text_primary"]),
        text_align=ft.TextAlign.CENTER,
    )
    brand_subtitle = ft.Text(
        TEXT["app_subtitle"],
        style=text_style("caption", color=p["text_muted"]),
        text_align=ft.TextAlign.CENTER,
    )
    brand_block = ft.Column(
        [
            ft.Container(
                content=sunburst_badge(state, size=44),
                alignment=ft.alignment.center,
                padding=ft.padding.only(bottom=SPACE["sm"]),
            ),
            brand_title,
            brand_subtitle,
        ],
        spacing=SPACE["xs"],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    welcome = ft.Text(
        TEXT["onboarding.welcome"],
        style=text_style("display", color=p["text_primary"]),
    )
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

    course_label = ft.Text(
        TEXT["onboarding.course_label"],
        style=text_style("h3", color=p["text_primary"]),
    )
    course_hint = ft.Text(
        TEXT["onboarding.course_hint"],
        style=text_style("caption", color=p["text_muted"]),
    )

    start_button = ft.ElevatedButton(
        text=TEXT["onboarding.start"],
        on_click=_on_start,
        style=primary_button(state.is_dark),
    )
    action_row = ft.Row(
        [start_button],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    content = ft.Column(
        [
            brand_block,
            ft.Container(
                content=decorative_divider(state, width=260),
                padding=ft.padding.symmetric(vertical=SPACE["md"]),
                alignment=ft.alignment.center,
            ),
            welcome,
            subtitle,
            ft.Container(height=SPACE["lg"]),
            ft.Row([name_field], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=SPACE["md"]),
            course_label,
            course_hint,
            ft.Container(height=SPACE["sm"]),
            course_row,
            ft.Container(height=SPACE["md"]),
            avatar_label,
            avatar_hint,
            ft.Container(height=SPACE["sm"]),
            avatar_row,
            ft.Container(height=SPACE["xl"]),
            error_text,
            action_row,
        ],
        spacing=SPACE["sm"],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    card = ft.Container(
        content=content,
        padding=ft.padding.all(SPACE["2xl"]),
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        width=560,
        shadow=apply_elevation("raised", state.is_dark),
    )

    animate_fade = state.breakpoint != "compact"
    wrapper = ft.Container(
        expand=True,
        bgcolor=p["bg_base"],
        alignment=ft.alignment.center,
        content=card,
        opacity=0 if animate_fade else 1,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT) if animate_fade else None,
    )

    if animate_fade:
        def _fade_in(_evt: ft.ControlEvent) -> None:
            wrapper.opacity = 1
            wrapper.update()
        wrapper.on_animation_end = None  # сброс, если был
        # Fire-after-mount: ставим opacity=1 сразу после page.update() в router.
        # Flet отыграет 200ms animation-curve, потому что opacity уже прикручен
        # к `animate_opacity`. Триггерим через page-level микротаск.
        def _trigger_fade() -> None:
            wrapper.opacity = 1
            try:
                wrapper.update()
            except Exception:
                pass
        # Ставим в state.page for-each-render хук — но простейший рабочий
        # способ: через did_mount fill. У Container'а нет on_mount в Flet,
        # поэтому используем page.run_task (coroutine) или page.set_timer.
        # Простейший вариант — запустить после коротких 1ms через Thread.
        import threading
        threading.Timer(0.02, _trigger_fade).start()

    return wrapper


def _course_card(
    course: dict[str, str],
    selected: bool,
    on_pick,
    p: dict,
) -> ft.Control:
    """Карточка-кнопка выбора курса (Госэкзамен по ИИ / по ГМУ / …)."""
    short = course.get("short_title", "")
    description = course.get("description", "")
    title_text = ft.Text(
        short,
        size=15,
        weight=ft.FontWeight.W_600,
        color=p["accent"] if selected else p["text_primary"],
    )
    desc_text = ft.Text(
        description,
        size=11,
        color=p["text_muted"],
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    return ft.Container(
        content=ft.Column(
            [title_text, desc_text],
            spacing=SPACE["xs"],
            tight=True,
        ),
        padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["sm"]),
        bgcolor=p["accent_soft"] if selected else p["bg_elevated"],
        border=ft.border.all(
            2 if selected else 1,
            p["accent"] if selected else p["border_soft"],
        ),
        border_radius=RADIUS["md"],
        width=240,
        on_click=lambda _e, eid=course["exam_id"]: on_pick(eid),
        ink=True,
    )


def _avatar_button(
    avatar: str,
    selected: bool,
    on_pick,
    p: dict,
) -> ft.Control:
    size = 64
    return ft.Container(
        content=ft.Text(avatar, size=32, text_align=ft.TextAlign.CENTER),
        width=size,
        height=size,
        alignment=ft.alignment.center,
        border_radius=RADIUS["md"],
        bgcolor=p["accent_soft"] if selected else p["bg_elevated"],
        border=ft.border.all(
            3 if selected else 1,
            p["accent"] if selected else p["border_soft"],
        ),
        on_click=lambda _e, a=avatar: on_pick(a),
    )
