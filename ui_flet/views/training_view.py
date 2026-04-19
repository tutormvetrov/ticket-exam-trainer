"""TrainingView — screen for training on a selected ticket.

Layout:
    top      back link → /tickets, ticket header (number + title)
    chip-row six mode chips; the active one is highlighted
    body     two-column on ultrawide (workspace + side info),
             single-column otherwise

The actual exercise UI is delegated to a workspace module keyed by mode.
"""

from __future__ import annotations

from typing import Callable, Dict

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS
from ui_flet.workspaces.active_recall_workspace import build_workspace as _active_recall
from ui_flet.workspaces.cloze_workspace import build_workspace as _cloze
from ui_flet.workspaces.plan_workspace import build_workspace as _plan
from ui_flet.workspaces.reading_workspace import build_workspace as _reading
from ui_flet.workspaces.review_workspace import build_workspace as _review
from ui_flet.workspaces.state_exam_full_workspace import build_workspace as _state_exam_full


# Mode key aliases — the UI route path, URL slug, text key base, and
# facade mode identifier are not always literally equal. We keep a
# canonical key per mode and two projections: `url_slug` (what we
# navigate to) and `text_base` (i18n prefix, uses underscores).
_MODES: list[tuple[str, str, str]] = [
    # (url_slug, canonical_mode, text_base)
    ("reading",         "reading",          "reading"),
    ("plan",            "plan",             "plan"),
    ("cloze",           "cloze",            "cloze"),
    ("active-recall",   "active-recall",    "active_recall"),
    ("state-exam-full", "state-exam-full",  "state_exam_full"),
    ("review",          "review",           "review"),
]


_WORKSPACE_BUILDERS: Dict[str, Callable] = {
    "reading":          _reading,
    "plan":             _plan,
    "cloze":            _cloze,
    "active-recall":    _active_recall,
    "active_recall":    _active_recall,  # forgiving alias
    "state-exam-full":  _state_exam_full,
    "state_exam_full":  _state_exam_full,  # forgiving alias
    "review":           _review,
}


def _normalize_mode(mode_key: str) -> str:
    """Resolve various legal spellings to a canonical mode key."""
    if not mode_key:
        return "reading"
    normalized = mode_key.strip()
    # Accept both "state-exam-full" and "state_exam_full"
    direct_map = {
        "reading": "reading",
        "plan": "plan",
        "cloze": "cloze",
        "active-recall": "active-recall",
        "active_recall": "active-recall",
        "state-exam-full": "state-exam-full",
        "state_exam_full": "state-exam-full",
        "review": "review",
    }
    return direct_map.get(normalized, "reading")


def _mode_chip(
    palette_map: dict,
    *,
    label: str,
    is_active: bool,
    on_click: Callable,
) -> ft.Control:
    bg = palette_map["accent"] if is_active else palette_map["bg_elevated"]
    fg = palette_map["bg_elevated"] if is_active else palette_map["text_primary"]
    border = palette_map["accent"] if is_active else palette_map["border_soft"]
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["xs"] + 2),
        bgcolor=bg,
        border_radius=RADIUS["pill"],
        border=ft.border.all(1, border),
        on_click=on_click,
        ink=True,
        content=ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=fg),
    )


def _ticket_number_text(ticket_title: str) -> tuple[str, str]:
    """Split leading 'Билет 12. …' into (number_badge, short_title)."""
    title = (ticket_title or "").strip()
    if title.lower().startswith("билет"):
        parts = title.split(".", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return "", title


def _load_ticket(state: AppState, ticket_id: str):
    try:
        return state.facade.queries.load_ticket_map(ticket_id)
    except Exception:
        return None


def _load_section_title(state: AppState, ticket) -> str:
    if ticket is None:
        return ""
    try:
        for section in state.facade.load_sections_overview() or []:
            # Section overview is keyed by title; ticket has section_id (slug)
            pass
    except Exception:
        return ticket.section_id or ""
    return ticket.section_id or ""


def _difficulty_label(difficulty: int | None) -> str:
    try:
        value = int(difficulty or 0)
    except Exception:
        value = 0
    if value <= 1:
        return TEXT["ticket.difficulty.easy"]
    if value == 2:
        return TEXT["ticket.difficulty.medium"]
    return TEXT["ticket.difficulty.hard"]


def _mastery_percent_for(state: AppState, ticket_id: str) -> int | None:
    try:
        breakdowns = state.facade.load_mastery_breakdowns() or {}
    except Exception:
        return None
    breakdown = breakdowns.get(ticket_id)
    if breakdown is None:
        return None
    # Prefer state_exam_overall_score when present; else fall back to confidence_score.
    score = float(getattr(breakdown, "state_exam_overall_score", 0.0) or 0.0)
    if score <= 0:
        score = float(getattr(breakdown, "confidence_score", 0.0) or 0.0)
    return int(round(score * 100))


def _side_panel(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)
    if ticket is None:
        return ft.Container(
            width=300,
            padding=SPACE["md"],
            content=ft.Text(TEXT["empty.no_ticket"], color=p["text_muted"]),
        )

    mastery_percent = _mastery_percent_for(state, ticket.ticket_id)

    info_rows: list[ft.Control] = [
        _info_row(p, TEXT["ticket.section"], ticket.section_id or "—"),
        _info_row(p, TEXT["ticket.difficulty"], _difficulty_label(ticket.difficulty)),
        _info_row(p, TEXT["ticket.time_to_answer"], f"~{max(1, int(ticket.estimated_oral_time_sec or 0) // 60)} мин"),
    ]
    if mastery_percent is not None:
        info_rows.append(_info_row(p, TEXT["ticket.mastery"], f"{mastery_percent}%"))

    return ft.Container(
        width=300,
        padding=SPACE["lg"],
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["md"],
            controls=[
                ft.Text(TEXT["ticket.about"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                *info_rows,
            ],
        ),
    )


def _info_row(palette_map: dict, label: str, value: str) -> ft.Control:
    return ft.Column(
        spacing=SPACE["xs"],
        controls=[
            ft.Text(label, size=11, color=palette_map["text_muted"]),
            ft.Text(value, size=14, color=palette_map["text_primary"], weight=ft.FontWeight.W_500),
        ],
    )


def _empty_body(state: AppState, ticket_id: str) -> ft.Control:
    p = palette(state.is_dark)
    return ft.Container(
        padding=SPACE["xl"],
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["sm"],
            controls=[
                ft.Text(TEXT["empty.no_ticket"], size=18, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                ft.Text(
                    f"{ticket_id}: {TEXT['ticket.not_found']}",
                    size=13,
                    color=p["text_secondary"],
                ),
                ft.TextButton(
                    TEXT["training.back_to_list"],
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda _: state.go("/tickets"),
                ),
            ],
        ),
    )


def build_training_view(state: AppState, *, ticket_id: str, mode_key: str) -> ft.Control:
    p = palette(state.is_dark)
    mode = _normalize_mode(mode_key)
    state.selected_ticket_id = ticket_id
    state.selected_mode = mode

    ticket = _load_ticket(state, ticket_id)

    back_link = ft.TextButton(
        text=TEXT["training.back_to_list"],
        icon=ft.Icons.ARROW_BACK,
        on_click=lambda _: state.go("/tickets"),
    )

    # Header: number badge + title
    if ticket is not None:
        number_text, title_text = _ticket_number_text(ticket.title)
        header_controls: list[ft.Control] = []
        if number_text:
            header_controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
                    bgcolor=p["accent_soft"],
                    border_radius=RADIUS["pill"],
                    content=ft.Text(number_text, size=12, color=p["accent"], weight=ft.FontWeight.W_600),
                )
            )
        header_controls.append(
            ft.Text(
                title_text or TEXT["training.title"],
                size=22,
                weight=ft.FontWeight.W_600,
                color=p["text_primary"],
                expand=True,
                selectable=True,
            )
        )
        header = ft.Row(
            spacing=SPACE["sm"],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=header_controls,
        )
    else:
        header = ft.Text(
            TEXT["training.title"],
            size=22,
            weight=ft.FontWeight.W_600,
            color=p["text_primary"],
        )

    # Mode chips row
    def _go_mode(slug: str) -> Callable:
        def _cb(_e) -> None:
            state.selected_mode = slug
            state.go(f"/training/{ticket_id}/{slug}")
        return _cb

    chips = []
    for url_slug, canonical, text_base in _MODES:
        label = TEXT.get(f"mode.{text_base}.title", canonical)
        chips.append(
            _mode_chip(
                p,
                label=label,
                is_active=(canonical == mode),
                on_click=_go_mode(url_slug),
            )
        )

    chip_row = ft.Row(
        spacing=SPACE["sm"],
        wrap=True,
        run_spacing=SPACE["sm"],
        controls=chips,
    )

    # Workspace body
    if ticket is None:
        workspace = _empty_body(state, ticket_id)
    else:
        builder = _WORKSPACE_BUILDERS.get(mode)
        if builder is None:
            workspace = _empty_body(state, ticket_id)
        else:
            try:
                workspace = builder(state, ticket)
            except Exception as exc:  # noqa: BLE001
                workspace = ft.Container(
                    padding=SPACE["lg"],
                    content=ft.Text(f"Ошибка рендера режима '{mode}': {exc}", color=p["danger"], selectable=True),
                )

    # Responsive body: ultrawide gets a right-side info panel
    if state.breakpoint == "ultrawide" and ticket is not None:
        body_row = ft.Row(
            spacing=SPACE["lg"],
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Container(content=workspace, expand=True),
                _side_panel(state, ticket),
            ],
            expand=True,
        )
    else:
        body_row = ft.Container(content=workspace, expand=True)

    return ft.Container(
        padding=SPACE["xl"],
        bgcolor=p["bg_base"],
        expand=True,
        content=ft.Column(
            spacing=SPACE["md"],
            expand=True,
            controls=[
                back_link,
                header,
                ft.Text(TEXT["training.pick_mode"], size=12, color=p["text_muted"]),
                chip_row,
                ft.Container(height=SPACE["xs"]),
                body_row,
            ],
        ),
    )
