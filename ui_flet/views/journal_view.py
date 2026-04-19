"""Journal view — ежедневный ритуал: утро / день / вечер.

Состояние выводится из данных: attempts за сегодня + state.day_closed_at.
  * **Morning** — ни одной попытки за today: приветствие и призыв начать.
  * **During day** — есть ≥1 попытка, day_closed_at не проставлен: лента
    попыток + «Продолжить» + «Хватит на сегодня».
  * **Evening** — day_closed_at проставлен сегодня ИЛИ явно только что
    нажата кнопка: сводка дня + best-moment + превью завтра.

Journal — root-роут после onboarding. Tickets/Training/Settings доступны
через TopBar или sidebar.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import flet as ft

from application.daily_digest import DailyDigest, compute_daily_digest
from ui_flet.components.attempt_card import build_attempt_card
from ui_flet.components.top_bar import build_top_bar
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


_LOG = logging.getLogger(__name__)


def build_journal_view(state: AppState) -> ft.Control:
    """Главная entry-функция Journal view."""
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
    return ft.Container(
        content=content_column,
        expand=True,
        bgcolor=p["bg_base"],
    )


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
        return compute_daily_digest(state.facade.connection)
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

    greeting = ft.Text(
        f"{TEXT['journal.morning.greeting']}, {name} {avatar}".strip(),
        style=text_style("h1", color=p["text_primary"]),
    )

    queue_lines: list[ft.Control] = []
    if digest.queue_due_today == 0 and digest.queue_new == 0:
        queue_lines.append(
            ft.Text(
                TEXT["journal.morning.queue_empty"],
                style=text_style("body", color=p["text_secondary"]),
            )
        )
    else:
        parts: list[str] = [TEXT["journal.morning.queue"]]
        fragments: list[str] = []
        if digest.queue_due_today:
            fragments.append(
                TEXT["journal.morning.queue_review"].format(count=digest.queue_due_today)
            )
        if digest.queue_new:
            fragments.append(
                TEXT["journal.morning.queue_new"].format(count=digest.queue_new)
            )
        fragments.append(
            TEXT["journal.morning.queue_time"].format(minutes=digest.queue_estimate_minutes)
        )
        queue_lines.append(
            ft.Text(
                " ".join(parts + [", ".join(fragments) + "."]),
                style=text_style("body", color=p["text_secondary"]),
            )
        )

    start_button = ft.ElevatedButton(
        text=TEXT["journal.morning.start"],
        on_click=lambda _e: state.go("/tickets"),
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
            shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
        ),
    )

    card_content = ft.Column(
        [greeting, *queue_lines, ft.Container(height=SPACE["md"]), start_button],
        spacing=SPACE["sm"],
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
    return _center_card(card_content, p)


# ---------- During day ----------

def _build_during_day(state: AppState, digest: DailyDigest, p: dict) -> ft.Control:
    title = ft.Text(TEXT["journal.day.title"], style=text_style("h1", color=p["text_primary"]))

    attempt_controls: list[ft.Control] = [
        build_attempt_card(state, attempt) for attempt in digest.attempts
    ]

    continue_btn = ft.ElevatedButton(
        text=TEXT["journal.day.continue"],
        on_click=lambda _e: state.go("/tickets"),
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=SPACE["xl"], vertical=SPACE["md"]),
            shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
        ),
    )
    finish_btn = ft.TextButton(
        text=TEXT["journal.day.finish"],
        on_click=lambda _e: _on_finish_day(state),
    )

    controls: list[ft.Control] = [
        title,
        ft.Container(height=SPACE["sm"]),
    ]
    if attempt_controls:
        controls.append(
            ft.Column(
                attempt_controls,
                spacing=SPACE["sm"],
                scroll=ft.ScrollMode.AUTO,
            )
        )
    else:
        controls.append(
            ft.Text(
                TEXT["journal.day.empty"],
                style=text_style("body", color=p["text_muted"]),
            )
        )

    controls.append(ft.Container(height=SPACE["md"]))
    controls.append(
        ft.Row(
            [continue_btn, finish_btn],
            spacing=SPACE["md"],
            alignment=ft.MainAxisAlignment.START,
        )
    )

    column = ft.Column(controls, spacing=SPACE["sm"], horizontal_alignment=ft.CrossAxisAlignment.START)
    return _center_card(column, p, wide=True)


def _on_finish_day(state: AppState) -> None:
    state.day_closed_at = datetime.now().isoformat(timespec="seconds")
    _LOG.info("Day closed by user at=%s", state.day_closed_at)
    state.refresh()


# ---------- Evening ----------

def _build_evening(state: AppState, digest: DailyDigest, p: dict) -> ft.Control:
    profile = state.user_profile
    name = profile.name if profile else ""

    title = ft.Text(TEXT["journal.evening.title"], style=text_style("h1", color=p["text_primary"]))

    if not digest.has_attempts:
        body = ft.Text(
            TEXT["journal.evening.empty"],
            style=text_style("body", color=p["text_secondary"]),
        )
        return _center_card(
            ft.Column([title, body], spacing=SPACE["md"]),
            p,
        )

    if digest.mastered_today > 0:
        summary_line = TEXT["journal.evening.summary"].format(
            count=len(digest.attempts),
            mastered=digest.mastered_today,
        )
    else:
        summary_line = TEXT["journal.evening.summary_simple"].format(count=len(digest.attempts))

    lines: list[ft.Control] = [
        ft.Text(summary_line, style=text_style("body", color=p["text_secondary"])),
    ]
    if digest.best_attempt is not None:
        lines.append(
            ft.Text(
                TEXT["journal.evening.best"].format(
                    ticket=digest.best_attempt.ticket_title,
                    score=digest.best_attempt.score_percent,
                ),
                style=text_style("body", color=p["text_secondary"]),
            )
        )
    lines.append(
        ft.Text(
            TEXT["journal.evening.tomorrow"].format(
                count=digest.queue_due_today,
                new=digest.queue_new,
            ),
            style=text_style("body", color=p["text_secondary"]),
        )
    )
    closing_name = name or ""
    closing_text = TEXT["journal.evening.close"].format(name=closing_name).rstrip(", ")
    lines.append(
        ft.Text(closing_text, style=text_style("body_strong", color=p["text_primary"]))
    )

    reopen = ft.TextButton(
        text=TEXT["journal.evening.reopen"],
        on_click=lambda _e: _on_reopen(state),
    )

    content = ft.Column(
        [title, ft.Container(height=SPACE["sm"]), *lines, ft.Container(height=SPACE["md"]), reopen],
        spacing=SPACE["sm"],
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
    return _center_card(content, p)


def _on_reopen(state: AppState) -> None:
    state.day_closed_at = None
    _LOG.info("Day reopened by user")
    state.refresh()


# ---------- Layout helper ----------

def _center_card(content: ft.Control, p: dict, *, wide: bool = False) -> ft.Control:
    card = ft.Container(
        content=content,
        padding=ft.padding.all(SPACE["xl"]),
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["lg"],
        width=720 if wide else 560,
    )
    return ft.Container(
        expand=True,
        alignment=ft.alignment.top_center,
        padding=ft.padding.only(top=SPACE["xl"]),
        content=card,
    )
