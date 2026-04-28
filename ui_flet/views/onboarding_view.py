"""Onboarding view — first launch profile and preparation setup."""

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
    validate_exam_date,
    validate_name,
    validate_reminder_time,
)
from ui_flet.components.decorative import divider as decorative_divider
from ui_flet.components.decorative import sunburst_badge
from ui_flet.first_step import go_to_first_training_step, resolve_first_training_step
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
    course_ticket_counts = _load_course_ticket_counts(state)
    compact = state.breakpoint == "compact"

    picked_avatar: dict[str, str | None] = {"value": AVATAR_CHOICES[0] if AVATAR_CHOICES else None}
    picked_course: dict[str, str] = {"value": DEFAULT_EXAM_ID}

    name_field = ft.TextField(
        label=TEXT["onboarding.name_label"],
        hint_text=TEXT["onboarding.name_hint"],
        autofocus=True,
        border_radius=RADIUS["md"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
        width=None if compact else 360,
    )
    exam_date_field = ft.TextField(
        label=TEXT["onboarding.exam_date_label"],
        hint_text=TEXT["onboarding.exam_date_hint"],
        border_radius=RADIUS["md"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
        width=None if compact else 170,
        dense=True,
    )
    reminder_switch = ft.Switch(
        label=TEXT["onboarding.reminder_label"],
        value=False,
    )
    reminder_time_field = ft.TextField(
        label=TEXT["onboarding.reminder_time"],
        value="10:00",
        hint_text="ЧЧ:ММ",
        border_radius=RADIUS["md"],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        text_size=14,
        width=None if compact else 120,
        dense=True,
        disabled=True,
    )

    error_text = ft.Text(
        "",
        style=text_style("caption", color=p["danger"]),
        visible=False,
    )

    def _set_error(message: str) -> None:
        error_text.value = message
        error_text.visible = True
        error_text.update()

    def _clear_error() -> None:
        if error_text.visible:
            error_text.visible = False
            error_text.update()

    def _on_reminder_change(_evt: ft.ControlEvent) -> None:
        reminder_time_field.disabled = not bool(reminder_switch.value)
        reminder_time_field.update()

    reminder_switch.on_change = _on_reminder_change

    avatar_row = ft.Row(
        [],
        spacing=SPACE["sm"],
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
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
        _clear_error()

    _rebuild_avatars()

    # ---------- course picker ----------
    course_row = ft.Row(
        [],
        spacing=SPACE["sm"],
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
    )

    first_step_title = ft.Text(
        "",
        style=text_style("body_strong", color=p["text_primary"]),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    first_step_hint = ft.Text(
        "",
        style=text_style("caption", color=p["text_muted"]),
    )

    def _refresh_first_step_preview() -> None:
        step = resolve_first_training_step(state, exam_id=picked_course["value"])
        if step.has_ticket:
            first_step_title.value = step.ticket_title
            first_step_hint.value = TEXT["onboarding.first_step.ready"]
        else:
            first_step_title.value = TEXT["onboarding.first_step.empty"]
            first_step_hint.value = ""
        if first_step_title.page:
            first_step_title.update()
        if first_step_hint.page:
            first_step_hint.update()

    def _rebuild_courses() -> None:
        course_row.controls = [
            _course_card(
                course,
                selected=(picked_course["value"] == course["exam_id"]),
                on_pick=_on_pick_course,
                ticket_count=course_ticket_counts.get(course["exam_id"]),
                p=p,
            )
            for course in COURSE_CATALOG
        ]
        if course_row.page:
            course_row.update()

    def _on_pick_course(exam_id: str) -> None:
        picked_course["value"] = exam_id
        _rebuild_courses()
        _refresh_first_step_preview()
        _clear_error()

    _rebuild_courses()
    _refresh_first_step_preview()

    def _on_start(_evt: ft.ControlEvent) -> None:
        raw_name = name_field.value or ""
        ok, err_msg = validate_name(raw_name)
        if not ok:
            _set_error(err_msg)
            return
        if not picked_avatar["value"]:
            _set_error(TEXT["onboarding.avatar_not_picked"])
            return

        exam_date = (exam_date_field.value or "").strip()
        ok, err_msg = validate_exam_date(exam_date)
        if not ok:
            _set_error(err_msg)
            return

        reminder_enabled = bool(reminder_switch.value)
        reminder_time = (reminder_time_field.value or "10:00").strip() or "10:00"
        ok, err_msg = validate_reminder_time(reminder_time)
        if not ok:
            _set_error(err_msg)
            return

        profile = build_profile(
            raw_name,
            picked_avatar["value"],
            active_exam_id=picked_course["value"],
            exam_date=exam_date or None,
            reminder_enabled=reminder_enabled,
            reminder_time=reminder_time,
        )
        try:
            store.save(profile)
        except Exception:
            _LOG.exception("Profile save failed")
            _set_error("Не удалось сохранить профиль. Проверь права на папку приложения.")
            return

        _LOG.info("Profile created name=%s avatar=%s", profile.name, profile.avatar_emoji)
        state.user_profile = profile
        go_to_first_training_step(state, exam_id=profile.active_exam_id)

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
    kicker = ft.Text(
        TEXT["onboarding.kicker"].upper(),
        style=ft.TextStyle(
            font_family="Golos Text",
            size=11,
            weight=ft.FontWeight.W_600,
            color=p["text_muted"],
        ),
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
    first_step_block = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        sunburst_badge(state, size=24),
                        ft.Text(
                            TEXT["onboarding.first_step.title"],
                            style=text_style("h3", color=p["text_primary"]),
                        ),
                    ],
                    spacing=SPACE["sm"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                first_step_title,
                first_step_hint,
            ],
            spacing=SPACE["xs"],
            tight=True,
        ),
        padding=ft.padding.only(left=SPACE["md"]),
        border=ft.border.only(left=ft.BorderSide(3, p["accent"])),
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
        alignment=ft.MainAxisAlignment.START,
    )

    preparation_fields: ft.Control
    if compact:
        preparation_fields = ft.Column(
            [
                name_field,
                exam_date_field,
                reminder_switch,
                reminder_time_field,
            ],
            spacing=SPACE["sm"],
        )
    else:
        preparation_fields = ft.Column(
            [
                name_field,
                ft.Row(
                    [exam_date_field, reminder_time_field],
                    spacing=SPACE["sm"],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                reminder_switch,
            ],
            spacing=SPACE["sm"],
        )

    form_column = ft.Column(
        [
            course_label,
            course_hint,
            course_row,
            ft.Container(height=SPACE["xs"]),
            preparation_fields,
            ft.Text(
                TEXT["onboarding.reminder_hint"],
                style=text_style("caption", color=p["text_muted"]),
            ),
            ft.Container(height=SPACE["xs"]),
            avatar_label,
            avatar_hint,
            avatar_row,
            ft.Container(height=SPACE["md"]),
            error_text,
            action_row,
        ],
        spacing=SPACE["sm"],
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    intro_column = ft.Column(
        [
            brand_block,
            ft.Container(
                content=decorative_divider(state, width=260),
                padding=ft.padding.symmetric(vertical=SPACE["md"]),
                alignment=ft.alignment.center,
            ),
            kicker,
            welcome,
            subtitle,
            ft.Container(height=SPACE["md"]),
            first_step_block,
        ],
        spacing=SPACE["sm"],
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    if compact:
        content = ft.Column(
            [intro_column, form_column],
            spacing=SPACE["xl"],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    else:
        content = ft.Row(
            [
                ft.Container(content=intro_column, width=360),
                ft.Container(width=1, bgcolor=p["border_soft"], height=460),
                ft.Container(content=form_column, width=420),
            ],
            spacing=SPACE["2xl"],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    card = ft.Container(
        content=content,
        padding=ft.padding.all(SPACE["2xl"]),
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        width=560 if compact else 900,
        shadow=apply_elevation("raised", state.is_dark),
    )

    animate_fade = state.breakpoint != "compact"
    wrapper = ft.Container(
        expand=True,
        bgcolor=p["bg_base"],
        alignment=ft.alignment.center,
        content=ft.Column(
            [ft.Row([card], alignment=ft.MainAxisAlignment.CENTER)],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
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
    ticket_count: int | None,
    p: dict,
) -> ft.Control:
    """Карточка-кнопка выбора курса (Госэкзамен по ИИ / по ГМУ / …)."""
    short = course.get("short_title", "")
    description = _course_description(course, ticket_count)
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


def _load_course_ticket_counts(state: AppState) -> dict[str, int]:
    try:
        rows = state.facade.connection.execute(
            """
            SELECT exam_id, COUNT(*) AS tickets_count
            FROM tickets
            GROUP BY exam_id
            """
        ).fetchall()
    except Exception:
        _LOG.exception("Failed to load course ticket counts for onboarding")
        return {}
    return {
        str(row["exam_id"] or "").strip(): int(row["tickets_count"] or 0)
        for row in rows
        if str(row["exam_id"] or "").strip()
    }


def _course_description(course: dict[str, str], ticket_count: int | None) -> str:
    if ticket_count is not None and ticket_count > 0:
        long_title = str(course.get("long_title", "") or "").strip()
        if long_title:
            return f"{ticket_count} билетов · {long_title}"
        return f"{ticket_count} билетов"
    return str(course.get("description", "") or "").strip()


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
