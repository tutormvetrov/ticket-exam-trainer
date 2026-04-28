"""TicketsView — catalog of 208 exam tickets.

Layout is responsive:
- compact (<1280): single column, list fills the width. Card click navigates
  straight to /training/<id>/reading.
- standard / wide (1280-2560): two columns — list on the left, detail panel
  on the right.
- ultrawide (>=2560): three columns — list, detail, progress sidebar.

Data flow:
- state.facade.load_ticket_maps() — 208 TicketKnowledgeMap records.
- state.facade.connection — raw SQLite read for sections + lecturer meta
  (parsed out of sections.description which follows the convention
  "Преподаватель: <ФИО> • <Кафедра> • <Должность>").
- state.facade.load_mastery_breakdowns() — overall mastery per ticket.
- state.facade.load_training_snapshot() — queue items for the wide layout
  progress column. Best-effort; errors are swallowed to keep the catalog
  usable even if the readiness layer is mid-migration.

The view holds its own small bit of local state (search query, filter
selections, selected ticket) in closure-scoped variables; callbacks mutate
them and call .update() on the list / detail containers. This keeps Flet's
reactive surface area tiny and predictable.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import flet as ft

from application.ticket_reference import reference_answer_preview
from ui_flet.components.empty_state import build_empty_state, build_error_card, build_error_state
from ui_flet.components.ticket_card import TicketCard
from ui_flet.components.top_bar import build_top_bar
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


# Dispatch list for the training mode dropdown — order matters (reading first).
_MODE_KEYS: list[str] = [
    "reading",
    "plan",
    "cloze",
    "active_recall",
    "state_exam_full",
    "review",
]


def _mode_title(key: str) -> str:
    return TEXT.get(f"mode.{key}.title", key)


def _lecturer_from_description(description: str) -> str:
    """Pull the lecturer name out of a sections.description string.

    Convention established by the import pipeline:
        "Преподаватель: Иванов И.И. • ВШГА МГУ • Доцент"
    We split on bullets / semicolons and take the "Преподаватель: ..." piece.
    """
    if not description:
        return ""
    # Split on common bullet chars / pipes / semicolons
    parts = re.split(r"[•|;]", description)
    for part in parts:
        part = part.strip()
        lower = part.lower()
        if lower.startswith("преподаватель") or lower.startswith("лектор"):
            # Drop label + separator, keep the rest
            after = part.split(":", 1)[-1] if ":" in part else part
            return after.strip()
    return ""


def _load_sections_map(state: AppState) -> tuple[dict[str, dict[str, str]], Exception | None]:
    """section_id → {title, description, lecturer}. Tolerates missing table."""
    try:
        exam_id = state.active_exam_id
        if exam_id:
            rows = state.facade.connection.execute(
                """
                SELECT section_id, title, description
                FROM sections
                WHERE exam_id = ?
                ORDER BY order_index, section_id
                """,
                (exam_id,),
            ).fetchall()
        else:
            rows = state.facade.connection.execute(
                """
                SELECT section_id, title, description
                FROM sections
                ORDER BY order_index, section_id
                """
            ).fetchall()
    except Exception as exc:
        _LOG.exception("Tickets: load sections failed exam_id=%s", state.active_exam_id)
        return {}, exc
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        desc = r["description"] or ""
        out[r["section_id"]] = {
            "title": r["title"] or "",
            "description": desc,
            "lecturer": _lecturer_from_description(desc),
        }
    return out, None


def _load_mastery_map(state: AppState) -> tuple[dict[str, float], Exception | None]:
    """ticket_id → overall mastery 0..1. Tolerates missing data."""
    try:
        breakdowns = state.facade.load_mastery_breakdowns()
    except Exception as exc:
        _LOG.exception("Tickets: load mastery failed exam_id=%s", state.active_exam_id)
        return {}, exc
    return {tid: float(getattr(b, "confidence_score", 0.0) or 0.0) for tid, b in breakdowns.items()}, None


def _ticket_has_warning(ticket: Any) -> bool:
    """Safe check: TicketKnowledgeMap doesn't currently carry a `warnings`
    attribute, but future iterations might. We return True only when the exact
    sentinel "source_missing_in_conspect" is present."""
    warnings = getattr(ticket, "warnings", None)
    if not warnings:
        return False
    try:
        return "source_missing_in_conspect" in warnings
    except TypeError:
        return False


def _build_filters_block(
    *,
    breakpoint: str,
    palette_map: dict[str, str],
    section_choices: list[tuple[str, str]],
    search_value: str,
    active_section_value: str,
    active_difficulty_value: str,
    on_search,
    on_section_change,
    on_difficulty_change,
) -> tuple[ft.Control, ft.TextField, ft.Dropdown, ft.Dropdown]:
    """Build the search/filter chrome without mixing wrap + expand.

    Flet web 0.27.x misbehaves when a wrapping Row contains expanded children.
    The old tickets toolbar used `Row(wrap=True)` plus `search_field.expand=1`,
    which rendered as a large grey placeholder and hid the rest of the left
    column. We split the layout by breakpoint:
    - compact: vertical stack
    - standard/wide/ultrawide: plain Row without wrap
    """
    search_field = ft.TextField(
        label=TEXT["tickets.search"],
        hint_text=TEXT["tickets.search.hint"],
        value=search_value,
        on_change=on_search,
        prefix_icon=ft.Icons.SEARCH,
        border_color=palette_map["border_medium"],
        focused_border_color=palette_map["accent"],
        dense=True,
        expand=1 if breakpoint != "compact" else None,
    )
    section_dd = ft.Dropdown(
        label=TEXT["tickets.filter.section"],
        value=active_section_value,
        options=[ft.dropdown.Option(key=k, text=label) for k, label in section_choices],
        on_change=on_section_change,
        border_color=palette_map["border_medium"],
        focused_border_color=palette_map["accent"],
        dense=True,
        width=None if breakpoint == "compact" else 240,
    )
    difficulty_dd = ft.Dropdown(
        label=TEXT["tickets.filter.difficulty"],
        value=active_difficulty_value,
        options=[
            ft.dropdown.Option(key="all", text=TEXT["tickets.filter.all"]),
            ft.dropdown.Option(key="1", text="1"),
            ft.dropdown.Option(key="2", text="2"),
            ft.dropdown.Option(key="3", text="3"),
            ft.dropdown.Option(key="4", text="4"),
            ft.dropdown.Option(key="5", text="5"),
        ],
        on_change=on_difficulty_change,
        border_color=palette_map["border_medium"],
        focused_border_color=palette_map["accent"],
        dense=True,
        width=None if breakpoint == "compact" else 160,
    )

    if breakpoint == "compact":
        block = ft.Column(
            [search_field, section_dd, difficulty_dd],
            spacing=SPACE["sm"],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    else:
        block = ft.Row(
            [search_field, section_dd, difficulty_dd],
            spacing=SPACE["md"],
            wrap=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return block, search_field, section_dd, difficulty_dd


def _ensure_tickets_breakpoint_listener(state: AppState) -> None:
    """Register the /tickets breakpoint listener once per AppState."""
    if getattr(state, "_tickets_breakpoint_listener_registered", False):
        return

    def _on_bp(_new_bp: str) -> None:
        route = getattr(state.page, "route", "") or ""
        if route.startswith("/tickets"):
            state.go("/tickets")

    state.on_breakpoint_change(_on_bp)
    state._tickets_breakpoint_listener_registered = True


def build_tickets_view(state: AppState) -> ft.Control:
    """Entry point — returns a full-page control for the /tickets route."""
    p = palette(state.is_dark)
    retry_button = ft.OutlinedButton(
        text=TEXT["action.retry"],
        icon=ft.Icons.REFRESH,
        on_click=lambda _e: state.refresh(),
    )

    # ---- data ----
    tickets_error = None
    try:
        tickets = state.facade.load_ticket_maps(exam_id=state.active_exam_id)
    except Exception as exc:
        _LOG.exception("Tickets: load tickets failed exam_id=%s", state.active_exam_id)
        tickets_error = exc
        tickets = []
    sections_by_id, sections_error = _load_sections_map(state)
    mastery_by_id, mastery_error = _load_mastery_map(state)
    ticket_positions = {ticket.ticket_id: index for index, ticket in enumerate(tickets, start=1)}

    # Build unique section options (sorted by title)
    section_choices: list[tuple[str, str]] = [("all", TEXT["tickets.filter.all"])]
    for sid, meta in sorted(sections_by_id.items(), key=lambda kv: kv[1]["title"]):
        title = meta["title"] or sid
        section_choices.append((sid, title))

    # ---- local state ----
    search_query: dict[str, str] = {"value": ""}
    active_section: dict[str, str] = {"value": "all"}
    active_difficulty: dict[str, str] = {"value": "all"}
    selected_id: dict[str, str | None] = {"value": state.selected_ticket_id}

    # ---- building blocks ----
    # ListView instead of Column(scroll=AUTO) — Column with scroll requires a
    # bounded parent height, and Flet 0.27 renders it as a grey placeholder
    # (no children visible) when wrapped in expand-chain containers.
    # padding right резервирует место под scrollbar Flet'а — иначе полоса
    # прокрутки наезжает на правый край карточек.
    list_container = ft.ListView(
        spacing=SPACE["sm"],
        expand=True,
        padding=ft.padding.only(right=SPACE["md"]),
    )
    detail_container = ft.Container(expand=True, padding=SPACE["lg"])
    progress_container = ft.Container(expand=True, padding=SPACE["lg"])
    counter_label = ft.Text(
        "",
        style=text_style("caption", color=p["text_muted"]),
    )

    # Track current card widgets so we can un-highlight them without a rebuild.
    current_cards: dict[str, TicketCard] = {}

    # ---- helpers: filtering ----
    def _passes_filters(ticket: Any) -> bool:
        q = search_query["value"].strip().lower()
        if q:
            haystack_parts = [
                ticket.title or "",
                sections_by_id.get(ticket.section_id, {}).get("title", ""),
                sections_by_id.get(ticket.section_id, {}).get("lecturer", ""),
            ]
            haystack = " ".join(haystack_parts).lower()
            if q not in haystack:
                return False
        sec = active_section["value"]
        if sec != "all" and ticket.section_id != sec:
            return False
        diff = active_difficulty["value"]
        if diff != "all":
            try:
                if int(ticket.difficulty or 1) != int(diff):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _filtered_tickets() -> list[Any]:
        return [t for t in tickets if _passes_filters(t)]

    # ---- helpers: detail panel ----
    def _build_detail(ticket: Any) -> ft.Control:
        pp = palette(state.is_dark)
        section = sections_by_id.get(ticket.section_id, {}) if ticket else {}
        section_title = section.get("title", "—")
        lecturer = section.get("lecturer", "")

        # Header
        header = ft.Column(
            [
                ft.Text(
                    ticket.title,
                    style=text_style("h1", color=pp["text_primary"]),
                    max_lines=3,
                ),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.BOOKMARK_OUTLINE, size=14, color=pp["text_muted"]),
                        ft.Text(
                            section_title,
                            style=text_style("body", color=pp["text_secondary"]),
                        ),
                    ],
                    spacing=SPACE["xs"],
                    tight=True,
                ),
            ]
            + (
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=14, color=pp["text_muted"]),
                            ft.Text(
                                lecturer,
                                style=text_style("caption", color=pp["text_muted"]),
                            ),
                        ],
                        spacing=SPACE["xs"],
                        tight=True,
                    )
                ]
                if lecturer
                else []
            ),
            spacing=SPACE["xs"],
            tight=True,
        )

        # Meta row: difficulty + mastery + oral time estimate
        meta_items: list[ft.Control] = []
        meta_items.append(
            _meta_chip(
                pp,
                icon=ft.Icons.SIGNAL_CELLULAR_ALT,
                label=f"{TEXT['tickets.difficulty_label']}: {int(getattr(ticket, 'difficulty', 1) or 1)}/5",
            )
        )
        mastery = mastery_by_id.get(ticket.ticket_id, 0.0)
        meta_items.append(
            _meta_chip(
                pp,
                icon=ft.Icons.INSIGHTS,
                label=f"{TEXT['tickets.mastery_label']}: {int(round(mastery * 100))}%",
            )
        )
        oral_sec = getattr(ticket, "estimated_oral_time_sec", 0) or 0
        if oral_sec:
            meta_items.append(
                _meta_chip(
                    pp,
                    icon=ft.Icons.TIMER_OUTLINED,
                    label=f"~{max(1, round(oral_sec / 60))} мин",
                )
            )
        meta_row = ft.Row(meta_items, spacing=SPACE["sm"], wrap=True)

        # Summary
        summary_text = reference_answer_preview(ticket, limit=500)
        summary_block = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        TEXT["tickets.summary_label"],
                        style=text_style("caption", color=pp["text_muted"]),
                    ),
                    ft.Text(
                        summary_text or "—",
                        style=text_style("body", color=pp["text_primary"]),
                    ),
                ],
                spacing=SPACE["xs"],
                tight=True,
            ),
            padding=SPACE["lg"],
            bgcolor=pp["bg_surface"],
            border=ft.border.all(1, pp["border_soft"]),
            border_radius=RADIUS["md"],
        )

        # Train button + mode dropdown
        mode_selection = {"value": "reading"}

        def _handle_mode_change(e: ft.ControlEvent) -> None:
            mode_selection["value"] = e.control.value or "reading"

        def _handle_train(_e: ft.ControlEvent) -> None:
            state.open_training(ticket.ticket_id, mode_selection["value"])

        mode_dropdown = ft.Dropdown(
            label=TEXT["tickets.pick_mode"],
            value="reading",
            options=[ft.dropdown.Option(key=k, text=_mode_title(k)) for k in _MODE_KEYS],
            on_change=_handle_mode_change,
            border_color=pp["border_medium"],
            focused_border_color=pp["accent"],
            text_size=14,
            dense=True,
            expand=1,
        )
        train_button = ft.FilledButton(
            text=TEXT["tickets.train"],
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=_handle_train,
            style=ft.ButtonStyle(
                bgcolor=pp["accent"],
                color=pp["bg_surface"],
                padding=ft.padding.symmetric(horizontal=SPACE["lg"], vertical=SPACE["md"]),
                shape=ft.RoundedRectangleBorder(radius=RADIUS["md"]),
            ),
        )

        action_row = ft.Row(
            [mode_dropdown, train_button],
            spacing=SPACE["md"],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Column(
            [header, meta_row, summary_block, action_row],
            spacing=SPACE["lg"],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_empty_detail() -> ft.Control:
        return build_empty_state(
            state,
            title=TEXT["tickets.no_selection"],
            hint=TEXT["tickets.no_selection.hint"],
            icon="📘",
        )

    def _build_empty_list() -> ft.Control:
        def _reset_filters(_e: ft.ControlEvent) -> None:
            search_query["value"] = ""
            active_section["value"] = "all"
            active_difficulty["value"] = "all"
            search_field.value = ""
            section_dd.value = "all"
            difficulty_dd.value = "all"
            _refresh_list()
            search_field.update()
            section_dd.update()
            difficulty_dd.update()

        reset_btn = ft.TextButton(
            TEXT["tickets.reset_filters"],
            icon=ft.Icons.FILTER_ALT_OFF,
            on_click=_reset_filters,
        )
        return build_empty_state(
            state,
            title=TEXT["tickets.empty"],
            hint=TEXT["tickets.empty.hint"],
            icon="🗂️",
            action=reset_btn,
        )

    # ---- rendering: list ----
    def _refresh_list() -> None:
        filtered = _filtered_tickets()
        current_cards.clear()
        list_container.controls.clear()

        if not filtered:
            list_container.controls.append(_build_empty_list())
        else:
            for t in filtered:
                section = sections_by_id.get(t.section_id, {})
                skeleton_weak = state.ticket_quality_cache.verdict_for(t).plan_skeleton_weak
                card = TicketCard(
                    state,
                    ticket_id=t.ticket_id,
                    title=t.title or "",
                    section_title=section.get("title", ""),
                    lecturer_name=section.get("lecturer", ""),
                    display_number=ticket_positions.get(t.ticket_id),
                    difficulty=int(getattr(t, "difficulty", 1) or 1),
                    mastery=mastery_by_id.get(t.ticket_id, 0.0),
                    has_warning=_ticket_has_warning(t),
                    plan_skeleton_weak=skeleton_weak,
                    selected=(selected_id["value"] == t.ticket_id),
                    on_click=_on_card_click,
                )
                current_cards[t.ticket_id] = card
                list_container.controls.append(card)

        counter_label.value = f"{len(filtered)} / {len(tickets)} {TEXT['tickets.count']}"
        if list_container.page:
            list_container.update()
        if counter_label.page:
            counter_label.update()

    # ---- rendering: detail ----
    def _refresh_detail() -> None:
        if selected_id["value"] is None:
            detail_container.content = _build_empty_detail()
        else:
            ticket = next((t for t in tickets if t.ticket_id == selected_id["value"]), None)
            if ticket is None:
                detail_container.content = _build_empty_detail()
            else:
                detail_container.content = _build_detail(ticket)
        if detail_container.page:
            detail_container.update()

    # ---- rendering: progress (ultrawide only) ----
    def _refresh_progress() -> None:
        pp = palette(state.is_dark)
        try:
            snapshot = state.facade.load_training_snapshot(tickets=tickets, exam_id=state.active_exam_id)
            queue_items = list(snapshot.queue_items)
        except Exception:
            _LOG.exception("Tickets: load training snapshot failed exam_id=%s", state.active_exam_id)
            progress_container.content = build_error_card(
                state,
                title=TEXT["tickets.progress.failed"],
                hint=TEXT["tickets.progress.failed.hint"],
                action=retry_button,
            )
            progress_container.bgcolor = pp["bg_surface"]
            progress_container.border = ft.border.only(left=ft.BorderSide(1, pp["border_soft"]))
            if progress_container.page:
                progress_container.update()
            return

        header = ft.Text(
            TEXT["tickets.progress.title"],
            style=text_style("h2", color=pp["text_primary"]),
        )

        # ---- Today dashboard (FSRS retention + due count) ----
        # Counts queue items whose due_at is today or overdue. `due_at` is a
        # `datetime` on the domain SpacedReviewItem — items list stays small
        # (<=12 used in the pane below) but we count the full snapshot here.
        from datetime import datetime, timedelta

        today_cutoff = datetime.now() + timedelta(hours=18)
        due_today = 0
        for it in queue_items:
            due = getattr(it, "due_at", None)
            if due is not None and due <= today_cutoff:
                due_today += 1

        today_block = ft.Container(
            padding=SPACE["lg"],
            bgcolor=pp["accent_soft"] if due_today else pp["bg_surface"],
            border=ft.border.all(1, pp["accent"] if due_today else pp["border_soft"]),
            border_radius=RADIUS["md"],
            content=ft.Column(
                [
                    ft.Text(
                        TEXT["tickets.progress.today"],
                        style=text_style("caption", color=pp["text_muted"]),
                    ),
                    ft.Text(
                        f"{due_today}",
                        style=text_style("display", color=pp["accent"] if due_today else pp["text_muted"]),
                    ),
                    ft.Text(
                        TEXT["tickets.progress.today.hint"] if due_today else TEXT["tickets.progress.today.clear"],
                        style=text_style("caption", color=pp["text_secondary"]),
                    ),
                ],
                spacing=SPACE["xs"],
                tight=True,
            ),
        )

        # Selected ticket readiness (if any)
        readiness_block: ft.Control
        if selected_id["value"]:
            mastery = mastery_by_id.get(selected_id["value"], 0.0)
            readiness_block = ft.Container(
                padding=SPACE["lg"],
                bgcolor=pp["bg_surface"],
                border=ft.border.all(1, pp["border_soft"]),
                border_radius=RADIUS["md"],
                content=ft.Column(
                    [
                        ft.Text(
                            TEXT["tickets.progress.ready"],
                            style=text_style("caption", color=pp["text_muted"]),
                        ),
                        ft.ProgressBar(
                            value=max(0.0, min(1.0, mastery)),
                            color=pp["accent"],
                            bgcolor=pp["bg_sidebar"],
                            height=8,
                        ),
                        ft.Text(
                            f"{int(round(mastery * 100))}%",
                            style=text_style("body_strong", color=pp["text_primary"]),
                        ),
                    ],
                    spacing=SPACE["sm"],
                    tight=True,
                ),
            )
        else:
            readiness_block = ft.Container(height=0)

        # Review queue (top 12)
        queue_children: list[ft.Control] = []
        queue_children.append(
            ft.Text(
                TEXT["tickets.progress.queue"],
                style=text_style("caption", color=pp["text_muted"]),
            )
        )
        if queue_items:
            for item in queue_items[:12]:
                queue_children.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
                        content=ft.Column(
                            [
                                ft.Text(
                                    item.ticket_title or item.ticket_id,
                                    style=text_style("body", color=pp["text_primary"]),
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    item.due_label or "",
                                    style=text_style("caption", color=pp["text_muted"]),
                                ),
                            ],
                            spacing=0,
                            tight=True,
                        ),
                        border=ft.border.only(bottom=ft.BorderSide(1, pp["border_soft"])),
                    )
                )
        else:
            queue_children.append(
                ft.Text(
                    TEXT["tickets.progress.empty"],
                    style=text_style("caption", color=pp["text_muted"]),
                )
            )

        progress_container.content = ft.Column(
            [
                header,
                today_block,
                readiness_block,
                ft.Column(queue_children, spacing=SPACE["xs"]),
            ],
            spacing=SPACE["lg"],
            scroll=ft.ScrollMode.AUTO,
        )
        progress_container.bgcolor = pp["bg_surface"]
        progress_container.border = ft.border.only(left=ft.BorderSide(1, pp["border_soft"]))
        if progress_container.page:
            progress_container.update()

    # ---- card click handler ----
    def _on_card_click(ticket_id: str) -> None:
        # On compact — go straight to training view with the default mode.
        if state.breakpoint == "compact":
            state.open_training(ticket_id, "reading")
            return
        # On wider breakpoints — update the detail panel in-place.
        prev = selected_id["value"]
        selected_id["value"] = ticket_id
        state.selected_ticket_id = ticket_id
        if prev and prev in current_cards:
            current_cards[prev].set_selected(False)
        if ticket_id in current_cards:
            current_cards[ticket_id].set_selected(True)
        _refresh_detail()
        _refresh_progress()

    # ---- filter/search handlers ----
    def _on_search(e: ft.ControlEvent) -> None:
        search_query["value"] = e.control.value or ""
        _refresh_list()

    def _on_section_change(e: ft.ControlEvent) -> None:
        active_section["value"] = e.control.value or "all"
        _refresh_list()

    def _on_difficulty_change(e: ft.ControlEvent) -> None:
        active_difficulty["value"] = e.control.value or "all"
        _refresh_list()

    bp = state.breakpoint
    filters_block, search_field, section_dd, difficulty_dd = _build_filters_block(
        breakpoint=bp,
        palette_map=p,
        section_choices=section_choices,
        search_value=search_query["value"],
        active_section_value=active_section["value"],
        active_difficulty_value=active_difficulty["value"],
        on_search=_on_search,
        on_section_change=_on_section_change,
        on_difficulty_change=_on_difficulty_change,
    )

    # Initial populate
    _refresh_list()
    _refresh_detail()
    _refresh_progress()

    # ---- compose per breakpoint ----
    top_bar = build_top_bar(state)
    _ensure_tickets_breakpoint_listener(state)

    if tickets_error is not None:
        return ft.Container(
            expand=True,
            bgcolor=p["bg_base"],
            content=ft.Column(
                [
                    top_bar,
                    ft.Container(
                        expand=True,
                        padding=SPACE["xl"],
                        content=build_error_state(
                            state,
                            title=TEXT["tickets.load_failed"],
                            hint=TEXT["tickets.load_failed.hint"],
                            action=retry_button,
                        ),
                    ),
                ],
                spacing=0,
                expand=True,
            ),
        )

    meta_warning = None
    if sections_error is not None or mastery_error is not None:
        meta_warning = build_error_card(
            state,
            title=TEXT["tickets.meta_failed"],
            hint=TEXT["tickets.meta_failed.hint"],
            action=retry_button,
        )

    left_column = ft.Container(
        expand=True,
        padding=ft.padding.only(
            left=SPACE["xl"],
            right=SPACE["xl"] if bp == "compact" else SPACE["lg"],
            top=SPACE["lg"],
            bottom=SPACE["lg"],
        ),
        content=ft.Column(
            [
                ft.Column(
                    [
                        ft.Text(
                            TEXT["tickets.title"],
                            style=text_style("h1", color=p["text_primary"]),
                        ),
                        ft.Text(
                            TEXT["tickets.subtitle"].format(n=len(tickets)),
                            style=text_style("caption", color=p["text_muted"]),
                        ),
                    ],
                    spacing=0,
                    tight=True,
                ),
                *([meta_warning] if meta_warning is not None else []),
                filters_block,
                counter_label,
                ft.Container(content=list_container, expand=True, bgcolor=p["bg_base"]),
            ],
            spacing=SPACE["md"],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    detail_column = ft.Container(
        expand=True,
        bgcolor=p["bg_surface"],
        border=ft.border.only(left=ft.BorderSide(1, p["border_soft"])),
        content=detail_container,
    )

    # Compact: list-only (click opens training)
    if bp == "compact":
        body = left_column
    # Standard / wide: 2 columns
    elif bp in ("standard", "wide"):
        body = ft.Row(
            [
                ft.Container(content=left_column, expand=3),
                ft.Container(content=detail_column, expand=4),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    # Wide / ultrawide: 3 columns — detail + progress pane (FSRS queue)
    # Per 2026-04-19 spec update (Part 3.3), the progress pane moves down
    # from ultrawide-only to laptop_hd+, which in our current breakpoint map
    # corresponds to the `wide` bucket (≥1920). On `ultrawide` (≥2560) we
    # simply grow the pane proportionally.
    else:
        progress_column = ft.Container(
            expand=True,
            content=progress_container,
        )
        progress_expand = 3 if bp == "ultrawide" else 2
        body = ft.Row(
            [
                ft.Container(content=left_column, expand=3),
                ft.Container(content=detail_column, expand=4),
                ft.Container(content=progress_column, expand=progress_expand),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    return ft.Container(
        expand=True,
        bgcolor=p["bg_base"],
        content=ft.Column(
            [top_bar, ft.Container(content=body, expand=True)],
            spacing=0,
            expand=True,
        ),
    )


def _meta_chip(p: dict[str, str], *, icon: str, label: str) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, size=14, color=p["text_muted"]),
                ft.Text(label, size=12, color=p["text_secondary"], weight=ft.FontWeight.W_500),
            ],
            spacing=SPACE["xs"],
            tight=True,
        ),
        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
        bgcolor=p["bg_sidebar"],
        border=ft.border.all(1, p["border_soft"]),
        border_radius=RADIUS["pill"],
    )
