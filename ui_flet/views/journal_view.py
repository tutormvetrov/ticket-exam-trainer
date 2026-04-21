"""Journal view — утренний / дневной / вечерний ритуал.

Состояние определяется из данных:
  * Morning — нет попыток за today: приветствие с датой + queue с rust-bullets + CTA «Начать».
  * During day — есть ≥1 попытка, day_closed_at не задан: лента attempt-cards + «Продолжить» + «Хватит на сегодня».
  * Evening — day_closed_at задан сегодня: display-заголовок + best-moment tile + дата завтра + «До завтра, имя».

Визуальная плотность: display-typography в ceremonial моментах, ornamental
divider между секциями, bg_surface на bg_base без жёсткого border, fade-in.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime

import flet as ft

from application.daily_digest import DailyDigest, compute_daily_digest
from ui_flet.components.attempt_card import build_attempt_card
from ui_flet.components.ornamental_divider import build_ornamental_divider
from ui_flet.components.top_bar import build_top_bar
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.buttons import ghost_button, primary_button
from ui_flet.theme.elevation import apply_elevation
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


_RU_MONTHS_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

def _time_aware_greeting(now: datetime | None = None) -> str:
    """Pick the greeting phrase that matches the current hour.

    Windows: 5–11 утро, 11–17 день, 17–22 вечер, 22–5 ночь.
    The morning stage of the journal still triggers on "no attempts today",
    but the greeting itself follows wall-clock time — otherwise the user
    sees "С добрым утром" at 23:43 which reads as broken.
    """
    hour = (now or datetime.now()).hour
    if 5 <= hour < 11:
        return TEXT["journal.morning.greeting"]
    if 11 <= hour < 17:
        return TEXT["journal.greeting.day"]
    if 17 <= hour < 22:
        return TEXT["journal.greeting.evening"]
    return TEXT["journal.greeting.night"]


_RU_WEEKDAYS = (
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
)


def _ru_date_today() -> str:
    today = date.today()
    return f"{_RU_WEEKDAYS[today.weekday()]}, {today.day} {_RU_MONTHS_GEN[today.month - 1]}"


def build_journal_view(state: AppState) -> ft.Control:
    p = palette(state.is_dark)
    _auto_reset_day_closed_if_new_day(state)

    digest = _load_digest_safely(state)
    stage = _resolve_stage(state, digest)

    if stage == "morning":
        body = _build_morning(state, digest, p)
    elif stage == "evening":
        body = _build_evening(state, digest, p)
    else:
        body = _build_during_day(state, digest, p)

    content_column = ft.Column(
        [build_top_bar(state), body],
        spacing=0,
        expand=True,
    )
    wrapper = ft.Container(
        content=content_column,
        expand=True,
        bgcolor=p["bg_base"],
    )
    _attach_fade_in(state, wrapper)
    return wrapper


def _attach_fade_in(state: AppState, wrapper: ft.Container) -> None:
    """Мягкий fade-in 200ms; отключён на compact-breakpoint, чтобы не лагало."""
    if state.breakpoint == "compact":
        return
    wrapper.opacity = 0
    wrapper.animate_opacity = ft.Animation(200, ft.AnimationCurve.EASE_OUT)

    def _trigger() -> None:
        wrapper.opacity = 1
        try:
            wrapper.update()
        except Exception:
            pass

    threading.Timer(0.02, _trigger).start()


def _auto_reset_day_closed_if_new_day(state: AppState) -> None:
    if not state.day_closed_at:
        return
    try:
        closed_date = datetime.fromisoformat(state.day_closed_at).date()
    except (TypeError, ValueError):
        state.day_closed_at = None
        return
    if closed_date != date.today():
        state.day_closed_at = None


def _load_digest_safely(state: AppState) -> DailyDigest:
    try:
        return compute_daily_digest(
            state.facade.connection,
            exam_id=state.active_exam_id,
        )
    except Exception:
        _LOG.exception("Daily digest failed — showing empty state")
        return DailyDigest(
            today_iso=date.today().isoformat(),
            attempts=[],
            mastered_today=0,
            best_attempt=None,
            queue_due_today=0,
            queue_new=0,
            queue_estimate_minutes=1,
        )


def _resolve_stage(state: AppState, digest: DailyDigest) -> str:
    if state.day_closed_at:
        return "evening"
    if not digest.has_attempts:
        return "morning"
    return "during"


# ---------- Morning ----------

def _build_morning(state: AppState, digest: DailyDigest, p: dict) -> ft.Control:
    profile = state.user_profile
    name = profile.name if profile else ""
    avatar = profile.avatar_emoji if profile else ""

    date_line = ft.Text(
        _ru_date_today(),
        style=ft.TextStyle(
            font_family="Golos Text",
            size=12,
            weight=ft.FontWeight.W_400,
            italic=True,
            color=p["text_muted"],
        ),
    )
    greeting = ft.Text(
        f"{_time_aware_greeting()}, {name} {avatar}".strip(),
        style=text_style("display", color=p["text_primary"]),
    )

    if digest.queue_due_today == 0 and digest.queue_new == 0:
        queue_control = ft.Text(
            TEXT["journal.morning.queue_empty"],
            style=text_style("body", color=p["text_secondary"]),
        )
    else:
        lines: list[ft.Control] = []
        if digest.queue_due_today:
            lines.append(
                _rust_bullet_row(
                    p,
                    TEXT["journal.morning.queue_review"].format(count=digest.queue_due_today),
                )
            )
        if digest.queue_new:
            lines.append(
                _rust_bullet_row(
                    p,
                    TEXT["journal.morning.queue_new"].format(count=digest.queue_new),
                )
            )
        lines.append(
            _rust_bullet_row(
                p,
                TEXT["journal.morning.queue_time"].format(minutes=digest.queue_estimate_minutes),
            )
        )
        queue_control = ft.Column(lines, spacing=SPACE["xs"])

    start_button = ft.ElevatedButton(
        text=TEXT["journal.morning.start"],
        on_click=lambda _e: state.go("/tickets"),
        style=primary_button(state.is_dark),
    )

    card_content = ft.Column(
        [
            date_line,
            greeting,
            build_ornamental_divider(state),
            queue_control,
            ft.Container(height=SPACE["xl"]),
            ft.Row([start_button], alignment=ft.MainAxisAlignment.START),
        ],
        spacing=SPACE["sm"],
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
    return _center_card(state, card_content, elevation_level="flat")


# ---------- During day ----------

def _build_during_day(state: AppState, digest: DailyDigest, p: dict) -> ft.Control:
    title = ft.Text(
        TEXT["journal.day.title"],
        style=text_style("display", color=p["text_primary"]),
    )

    attempt_controls: list[ft.Control] = [
        build_attempt_card(state, attempt) for attempt in digest.attempts
    ]

    continue_btn = ft.ElevatedButton(
        text=TEXT["journal.day.continue"],
        on_click=lambda _e: state.go("/tickets"),
        style=primary_button(state.is_dark),
    )
    finish_btn = ft.TextButton(
        text=TEXT["journal.day.finish"],
        on_click=lambda _e: _on_finish_day(state),
        style=ghost_button(state.is_dark),
    )

    controls: list[ft.Control] = [
        title,
        build_ornamental_divider(state),
    ]
    if attempt_controls:
        # Плоский список, без вложенного scroll-Column: внешняя карточка уже
        # сама scrollable (см. _center_card с scroll=AUTO), а scroll внутри
        # non-expand-chain Column в Flet схлопывает детей до 0 высоты.
        controls.extend(attempt_controls)
    else:
        controls.append(
            ft.Text(
                TEXT["journal.day.empty"],
                style=text_style("body", color=p["text_muted"]),
            )
        )

    controls.append(ft.Container(height=SPACE["xl"]))
    controls.append(
        ft.Row(
            [continue_btn, finish_btn],
            spacing=SPACE["md"],
            alignment=ft.MainAxisAlignment.START,
        )
    )

    column = ft.Column(
        controls,
        spacing=SPACE["md"],
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    return _center_card(state, column, elevation_level="flat", wide=True)


def _on_finish_day(state: AppState) -> None:
    state.day_closed_at = datetime.now().isoformat(timespec="seconds")
    _LOG.info("Day closed by user at=%s", state.day_closed_at)
    state.refresh()


# ---------- Evening ----------

def _build_evening(state: AppState, digest: DailyDigest, p: dict) -> ft.Control:
    profile = state.user_profile
    name = profile.name if profile else ""

    title = ft.Text(
        TEXT["journal.evening.title"],
        style=text_style("display", color=p["text_primary"]),
    )

    if not digest.has_attempts:
        body_lines: list[ft.Control] = [
            title,
            build_ornamental_divider(state),
            ft.Text(
                TEXT["journal.evening.empty"],
                style=text_style("body", color=p["text_secondary"]),
            ),
        ]
        return _center_card(
            state,
            ft.Column(body_lines, spacing=SPACE["md"]),
            elevation_level="flat",
        )

    summary_lines: list[ft.Control] = [
        _rust_bullet_row(
            p,
            f"{len(digest.attempts)} билетов разобрано",
        ),
    ]
    if digest.mastered_today > 0:
        summary_lines.append(
            _rust_bullet_row(
                p,
                f"{digest.mastered_today} легли в долговременную память",
            )
        )

    best_tile: ft.Control | None = None
    if digest.best_attempt is not None:
        best_tile = _best_moment_tile(p, digest.best_attempt)

    tomorrow_line = ft.Text(
        TEXT["journal.evening.tomorrow"].format(
            count=digest.queue_due_today,
            new=digest.queue_new,
        ),
        style=text_style("body", color=p["text_secondary"]),
    )

    farewell_text = TEXT["journal.evening.close"].format(name=name or "").rstrip(", ")
    farewell = ft.Text(
        farewell_text,
        style=ft.TextStyle(
            font_family="Lora",
            size=32,
            weight=ft.FontWeight.W_600,
            italic=True,
            color=p["text_primary"],
        ),
        text_align=ft.TextAlign.CENTER,
    )

    reopen = ft.TextButton(
        text=TEXT["journal.evening.reopen"],
        on_click=lambda _e: _on_reopen(state),
        style=ghost_button(state.is_dark),
    )

    controls: list[ft.Control] = [
        title,
        build_ornamental_divider(state),
        ft.Column(summary_lines, spacing=SPACE["xs"]),
    ]
    if best_tile is not None:
        controls.append(ft.Container(height=SPACE["md"]))
        controls.append(best_tile)
    controls.extend(
        [
            ft.Container(height=SPACE["md"]),
            tomorrow_line,
            build_ornamental_divider(state),
            ft.Row([farewell], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=SPACE["md"]),
            ft.Row([reopen], alignment=ft.MainAxisAlignment.CENTER),
        ]
    )
    return _center_card(
        state,
        ft.Column(controls, spacing=SPACE["sm"], horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        elevation_level="flat",
    )


def _on_reopen(state: AppState) -> None:
    state.day_closed_at = None
    _LOG.info("Day reopened by user")
    state.refresh()


# ---------- Helpers ----------

def _rust_bullet_row(p: dict, text: str) -> ft.Control:
    return ft.Row(
        [
            ft.Container(
                width=6,
                height=6,
                bgcolor=p["accent"],
                border_radius=RADIUS["pill"],
                margin=ft.margin.only(top=8),
            ),
            ft.Text(
                text,
                style=text_style("body", color=p["text_secondary"]),
                expand=True,
            ),
        ],
        spacing=SPACE["sm"],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


def _best_moment_tile(p: dict, attempt) -> ft.Control:
    label = ft.Text(
        "Лучший момент",
        style=text_style("caption", color=p["text_muted"]),
    )
    title = ft.Text(
        attempt.ticket_title,
        style=text_style("h3", color=p["text_primary"]),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )
    score = ft.Text(
        f"{attempt.score_percent}%",
        style=text_style("display", color=p["accent"]),
    )
    body = ft.Row(
        [
            ft.Column([label, title], spacing=SPACE["xs"], expand=True),
            score,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=SPACE["md"],
    )
    return ft.Container(
        content=body,
        padding=ft.padding.all(SPACE["lg"]),
        bgcolor=p["bg_elevated"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["md"],
    )


def _center_card(
    state: AppState,
    content: ft.Control,
    *,
    elevation_level: str = "flat",
    wide: bool = False,
) -> ft.Control:
    p = palette(state.is_dark)
    card = ft.Container(
        content=content,
        padding=ft.padding.all(SPACE["2xl"]),
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        width=720 if wide else 560,
        shadow=apply_elevation(elevation_level, state.is_dark),
    )
    # scroll на внешнем Column позволяет прокручивать всю страницу, если
    # attempt-карточек за день накопилось много. Не плодим вложенный
    # scroll внутри карточки — это ломает layout в Flet 0.27.
    return ft.Container(
        expand=True,
        padding=ft.padding.only(top=SPACE["2xl"], bottom=SPACE["2xl"]),
        content=ft.Column(
            [ft.Row([card], alignment=ft.MainAxisAlignment.CENTER)],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
    )
