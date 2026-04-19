"""DashboardView — стартовый экран «Дашборд готовности».

Три блока:

1. **Header-баннер**: приветствие + дата экзамена/осталось дней + общий процент готовности.
2. **Heat-map билетов**: сетка 16-в-ряд цветных квадратов по освоенности билета
   (`TicketMasteryBreakdown.confidence_score`). Кликабельные → /training/<id>/reading.
3. **План на сегодня**: 3-5 билетов из adaptive-queue с обоснованием
   («слабое место» / «давно не повторял» / «свежий»).

Все данные тянем через ``state.facade`` с фильтром по ``state.active_exam_id``.
Декор — ``decorative.divider`` + ``sunburst_badge`` в стиле активного семейства тем.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import flet as ft

from application.user_profile import COURSE_CATALOG
from ui_flet.components.decorative import (
    divider as decorative_divider,
)
from ui_flet.components.decorative import (
    sunburst_badge,
)
from ui_flet.components.empty_state import build_error_card, build_error_state
from ui_flet.components.top_bar import build_top_bar
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────

def _course_short_title(active_exam_id: str) -> str:
    for course in COURSE_CATALOG:
        if course.get("exam_id") == active_exam_id:
            return course.get("short_title", "")
    return ""


def _days_to_exam(exam_date_iso: str | None) -> int | None:
    if not exam_date_iso:
        return None
    try:
        target = datetime.strptime(exam_date_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (target - date.today()).days


def _mastery_color(p: dict, score: float) -> str:
    """Цвет квадрата в heat-map по освоенности (0..1)."""
    if score <= 0.05:
        return p["bg_elevated"]            # ещё не трогал
    if score < 0.30:
        return p["danger"]                  # слабо
    if score < 0.60:
        return p["warning"]                 # средне
    if score < 0.85:
        return p["info"]                    # хорошо
    return p["success"]                     # отлично


def _format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "0 мин"
    if minutes < 60:
        return f"{minutes} мин"
    h = minutes // 60
    m = minutes % 60
    if m == 0:
        return f"{h} ч"
    return f"{h} ч {m} мин"


# ── Главные секции ─────────────────────────────────────────────────────

def _header_banner(state: AppState, p: dict, *, readiness_percent: int,
                   tickets_total: int, tickets_practiced: int) -> ft.Control:
    profile = state.user_profile
    name = profile.name if profile is not None else "магистрант"
    course_title = _course_short_title(state.active_exam_id) or "Госэкзамен"
    days = _days_to_exam(profile.exam_date if profile else None)

    # Левая колонка: «Привет, {name}. {курс}.»
    greet = ft.Text(
        f"Привет, {name}.",
        style=text_style("h1", color=p["text_primary"]),
    )
    course_line = ft.Text(
        course_title,
        style=text_style("body", color=p["text_secondary"]),
    )
    left = ft.Column(
        [greet, course_line],
        spacing=SPACE["xs"],
        tight=True,
    )

    # Правая колонка: круглый процент готовности.
    pct_text = ft.Text(
        f"{readiness_percent}%",
        size=46,
        weight=ft.FontWeight.W_700,
        color=p["accent"],
    )
    pct_caption = ft.Text(
        TEXT["dashboard.readiness"],
        style=text_style("caption", color=p["text_muted"]),
    )
    right = ft.Column(
        [pct_text, pct_caption],
        spacing=0,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.END,
    )

    top_row = ft.Row(
        [left, ft.Container(expand=True), right],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # Под низом: дата экзамена / прогноз / прогресс.
    if days is None:
        forecast_text = TEXT["dashboard.exam.no_date"]
    elif days < 0:
        forecast_text = TEXT["dashboard.exam.passed"]
    elif days == 0:
        forecast_text = TEXT["dashboard.exam.today"]
    else:
        forecast_text = TEXT["dashboard.exam.in_days"].format(days=days)
    progress_text = TEXT["dashboard.tickets.progress"].format(
        practiced=tickets_practiced,
        total=tickets_total,
    )

    forecast_row = ft.Row(
        [
            ft.Text(forecast_text, style=text_style("body_strong", color=p["text_primary"])),
            ft.Container(width=SPACE["md"]),
            ft.Text(progress_text, style=text_style("caption", color=p["text_muted"])),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        padding=SPACE["xl"],
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["lg"],
        content=ft.Column(
            [
                top_row,
                ft.Container(
                    content=decorative_divider(state, width=200),
                    padding=ft.padding.symmetric(vertical=SPACE["sm"]),
                ),
                forecast_row,
            ],
            spacing=SPACE["sm"],
            tight=True,
        ),
    )


def _heatmap_cell(state: AppState, p: dict, ticket, mastery_score: float, on_click) -> ft.Control:
    bg = _mastery_color(p, mastery_score)
    title = ticket.title or ""
    pct = int(round(mastery_score * 100))
    tooltip = f"{title}\n{pct}% освоено"
    return ft.Container(
        width=22, height=22,
        bgcolor=bg,
        border=ft.border.all(1, p["border_soft"]),
        border_radius=4,
        tooltip=tooltip,
        on_click=lambda _e, tid=ticket.ticket_id: on_click(tid),
        ink=True,
    )


def _heatmap_block(state: AppState, p: dict, tickets, mastery_map) -> ft.Control:
    def _open(tid: str) -> None:
        state.go(f"/training/{tid}/reading")

    cells = []
    for t in tickets:
        score = 0.0
        if t.ticket_id in mastery_map:
            score = float(getattr(mastery_map[t.ticket_id], "confidence_score", 0.0) or 0.0)
        cells.append(_heatmap_cell(state, p, t, score, _open))

    grid = ft.Row(
        cells,
        wrap=True,
        spacing=4,
        run_spacing=4,
    )

    legend_items = [
        (TEXT["dashboard.heatmap.legend.untouched"], p["bg_elevated"]),
        (TEXT["dashboard.heatmap.legend.weak"], p["danger"]),
        (TEXT["dashboard.heatmap.legend.mid"], p["warning"]),
        (TEXT["dashboard.heatmap.legend.good"], p["info"]),
        (TEXT["dashboard.heatmap.legend.mastered"], p["success"]),
    ]
    legend = ft.Row(
        [
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=color, border_radius=2),
                    ft.Text(label, size=11, color=p["text_muted"]),
                ],
                spacing=SPACE["xs"],
                tight=True,
            )
            for label, color in legend_items
        ],
        spacing=SPACE["md"],
        wrap=True,
    )

    return ft.Container(
        padding=SPACE["lg"],
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["lg"],
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            TEXT["dashboard.heatmap.title"],
                            style=text_style("h3", color=p["text_primary"]),
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            TEXT["dashboard.heatmap.count"].format(n=len(tickets)),
                            style=text_style("caption", color=p["text_muted"]),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=decorative_divider(state, width=200),
                    padding=ft.padding.symmetric(vertical=SPACE["xs"]),
                ),
                grid,
                ft.Container(height=SPACE["sm"]),
                legend,
            ],
            spacing=SPACE["sm"],
        ),
    )


def _plan_card(state: AppState, p: dict, ticket_id: str, title: str, reason: str) -> ft.Control:
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=p["bg_elevated"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["md"],
        on_click=lambda _e, tid=ticket_id: state.go(f"/training/{tid}/reading"),
        ink=True,
        content=ft.Column(
            [
                ft.Text(
                    title,
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=p["text_primary"],
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(reason, size=12, italic=True, color=p["text_muted"]),
            ],
            spacing=SPACE["xs"],
            tight=True,
        ),
    )


def _plan_block(state: AppState, p: dict, queue_items) -> ft.Control:
    """Top-N карточек плана на сегодня."""
    cards: list[ft.Control] = []
    for it in (queue_items or [])[:5]:
        ticket_id = getattr(it, "ticket_id", None) or ""
        if not ticket_id:
            continue
        title = getattr(it, "ticket_title", None) or ticket_id
        # Простое объяснение приоритета.
        priority = float(getattr(it, "priority", 0.0) or 0.0)
        if priority >= 0.8:
            reason = TEXT["dashboard.plan.reason.weak"]
        elif priority >= 0.5:
            reason = TEXT["dashboard.plan.reason.gap"]
        else:
            reason = TEXT["dashboard.plan.reason.fresh"]
        cards.append(_plan_card(state, p, ticket_id, title, reason))

    if not cards:
        cards.append(ft.Text(
            TEXT["dashboard.plan.empty"],
            size=13, color=p["text_muted"],
        ))

    return ft.Container(
        padding=SPACE["lg"],
        bgcolor=p["bg_surface"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["lg"],
        content=ft.Column(
            [
                ft.Row(
                    [
                        sunburst_badge(state, size=24),
                        ft.Container(width=SPACE["sm"]),
                        ft.Text(
                            TEXT["dashboard.plan.title"],
                            style=text_style("h3", color=p["text_primary"]),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                ft.Container(
                    content=decorative_divider(state, width=180),
                    padding=ft.padding.symmetric(vertical=SPACE["xs"]),
                ),
                ft.Column(cards, spacing=SPACE["sm"]),
            ],
            spacing=SPACE["sm"],
        ),
    )


# ── Entry point ────────────────────────────────────────────────────────

def build_dashboard_view(state: AppState) -> ft.Control:
    p = palette(state.is_dark)
    eid = state.active_exam_id

    retry_button = ft.OutlinedButton(
        text=TEXT["action.retry"],
        icon=ft.Icons.REFRESH,
        on_click=lambda _e: state.refresh(),
    )

    # ---- data ----
    tickets_error = None
    try:
        tickets = state.facade.load_ticket_maps(exam_id=eid)
    except Exception as exc:
        _LOG.exception("Dashboard: load tickets failed exam_id=%s", eid)
        tickets_error = exc
        tickets = []

    mastery_error = None
    try:
        mastery = state.facade.load_mastery_breakdowns()
    except Exception as exc:
        _LOG.exception("Dashboard: load mastery failed exam_id=%s", eid)
        mastery_error = exc
        mastery = {}

    snapshot_error = None
    try:
        snapshot = state.facade.load_training_snapshot(tickets=tickets)
        queue_items = list(getattr(snapshot, "queue_items", []) or [])
    except Exception as exc:
        _LOG.exception("Dashboard: load training snapshot failed exam_id=%s", eid)
        snapshot_error = exc
        queue_items = []

    readiness_error = None
    try:
        readiness = state.facade.load_readiness_score(
            tickets=tickets, mastery=mastery,
        )
        readiness_percent = int(getattr(readiness, "percent", 0) or 0)
        tickets_practiced = int(getattr(readiness, "tickets_practiced", 0) or 0)
    except Exception as exc:
        _LOG.exception("Dashboard: load readiness failed exam_id=%s", eid)
        readiness_error = exc
        readiness_percent = 0
        tickets_practiced = 0

    if tickets_error is not None:
        body = build_error_state(
            state,
            title=TEXT["dashboard.load_failed"],
            hint=TEXT["dashboard.load_failed.hint"],
            action=retry_button,
        )
    else:
        body_controls: list[ft.Control] = []
        if readiness_error is not None:
            body_controls.append(
                build_error_card(
                    state,
                    title=TEXT["dashboard.section_failed"],
                    hint=TEXT["dashboard.section_failed.hint"],
                    action=retry_button,
                )
            )
        else:
            body_controls.append(
                _header_banner(
                    state, p,
                    readiness_percent=readiness_percent,
                    tickets_total=len(tickets),
                    tickets_practiced=tickets_practiced,
                )
            )

        if mastery_error is not None:
            body_controls.append(
                build_error_card(
                    state,
                    title=TEXT["dashboard.section_failed"],
                    hint=TEXT["dashboard.section_failed.hint"],
                    action=retry_button,
                )
            )
        else:
            body_controls.append(_heatmap_block(state, p, tickets, mastery))

        if snapshot_error is not None:
            body_controls.append(
                build_error_card(
                    state,
                    title=TEXT["dashboard.section_failed"],
                    hint=TEXT["dashboard.section_failed.hint"],
                    action=retry_button,
                )
            )
        else:
            body_controls.append(_plan_block(state, p, queue_items))

        body = ft.Column(
            body_controls,
            spacing=SPACE["lg"],
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )

    layout = ft.Column(
        [
            build_top_bar(state),
            ft.Container(
                content=body,
                padding=SPACE["xl"],
                expand=True,
            ),
        ],
        spacing=0,
        expand=True,
    )

    return ft.Container(
        content=layout,
        bgcolor=p["bg_base"],
        expand=True,
    )
