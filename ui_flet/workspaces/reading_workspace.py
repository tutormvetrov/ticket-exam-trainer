"""Reading workspace — entry point for ticket familiarization.

Shows:
  * Canonical answer summary (selectable)
  * List of knowledge atoms, color-tagged by atom_type
  * Six answer_blocks (non-missing ones) with expected content

Footer: single CTA to jump to the Plan mode — reading is meant to be
a one-off orientation, not a sticky workspace.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import flet as ft

from application.pdf_export import generate_ticket_pdf
from application.ticket_reference import (
    block_code_value,
    compose_reference_answer,
    normalize_reference_text,
    reference_answer_blocks,
    truncate_reference_text,
)
from ui_flet.components.ask_etalon_panel import open_ask_etalon_dialog
from ui_flet.components.training_workspace_base import build_workspace_frame
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette

_LOG = logging.getLogger(__name__)


def _safe_filename(text: str, fallback: str = "ticket") -> str:
    """Сделать безопасное имя файла из произвольной строки."""
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned[:80].strip()
    return cleaned or fallback


def _ticket_section_meta(state: AppState, section_id: str) -> tuple[str, str]:
    """(section_title, lecturer) для билета — читаем напрямую из БД, чтобы
    не тащить весь словарь sections при экспорте одного PDF.
    """
    try:
        row = state.facade.connection.execute(
            "SELECT title, description FROM sections WHERE section_id = ?",
            (section_id,),
        ).fetchone()
    except Exception:
        return "", ""
    if not row:
        return "", ""
    title = row["title"] or ""
    desc = row["description"] or ""
    lecturer = ""
    for part in re.split(r"[•|;]", desc):
        part = part.strip()
        if part.lower().startswith(("преподаватель", "лектор")):
            lecturer = part.split(":", 1)[-1].strip()
            break
    return title, lecturer


# Stable colour hints per atom_type — falls back to `accent` for unknown types.
_ATOM_TYPE_ACCENT = {
    "definition": "info",
    "features": "success",
    "examples": "warning",
    "stages": "accent",
    "functions": "info",
    "causes": "danger",
    "consequences": "danger",
    "classification": "success",
    "process_step": "accent",
    "conclusion": "success",
}


def _atom_type_value(atom) -> str:
    """Нормализует атом-тип в lowercased-snake-string ('conclusion', 'examples', ...)."""
    raw = atom.type
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw).lower().split(".")[-1]


def _block_code_value(block) -> str:
    return block_code_value(getattr(block, "block_code", ""))


def _atom_card(palette_map: dict, atom) -> ft.Control:
    atom_type_value = _atom_type_value(atom)
    accent_key = _ATOM_TYPE_ACCENT.get(atom_type_value, "accent")
    accent_colour = palette_map.get(accent_key, palette_map["accent"])
    type_label = TEXT.get(f"atom.type.{atom_type_value}", atom_type_value.replace("_", " "))
    display_label = truncate_reference_text(atom.label or type_label, limit=88)

    header_row: list[ft.Control] = [
        ft.Container(
            width=4,
            bgcolor=accent_colour,
            border_radius=RADIUS["sm"],
        ),
        ft.Text(
            display_label or type_label,
            size=14,
            weight=ft.FontWeight.W_600,
            color=palette_map["text_primary"],
            expand=True,
        ),
        ft.Container(
            padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
            border_radius=RADIUS["pill"],
            bgcolor=palette_map["bg_elevated"],
            border=ft.border.all(1, accent_colour),
            content=ft.Text(type_label, size=11, color=accent_colour, weight=ft.FontWeight.W_600),
        ),
    ]

    controls: list[ft.Control] = [
        ft.Row(
            controls=header_row,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE["sm"],
        ),
    ]
    atom_text = normalize_reference_text(atom.text)
    if atom_text:
        controls.append(
            ft.Text(
                atom_text,
                size=13,
                color=palette_map["text_secondary"],
                selectable=True,
            )
        )
    keywords = list(atom.keywords or [])
    if keywords:
        controls.append(
            ft.Row(
                wrap=True,
                spacing=SPACE["xs"],
                run_spacing=SPACE["xs"],
                controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=SPACE["xs"]),
                        bgcolor=palette_map["bg_elevated"],
                        border_radius=RADIUS["pill"],
                        content=ft.Text(kw, size=11, color=palette_map["text_muted"]),
                    )
                    for kw in keywords[:8]
                ],
            )
        )

    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(spacing=SPACE["xs"], controls=controls),
    )


def _answer_block_card(palette_map: dict, block) -> ft.Control:
    code = _block_code_value(block)
    fallback_title = TEXT.get(f"block.{code}", code.replace("_", " "))
    content = normalize_reference_text(block.expected_content or "")
    return ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(
            spacing=SPACE["xs"],
            controls=[
                ft.Text(
                    block.title or fallback_title,
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=palette_map["text_primary"],
                ),
                ft.Markdown(
                    content,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                ),
            ],
        ),
    )


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    _reference_blocks = reference_answer_blocks(ticket)
    _full_answer_text = compose_reference_answer(ticket, include_headings=True, heading_level=3)

    summary_control = ft.Container(
        padding=SPACE["md"],
        bgcolor=p["bg_elevated"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Markdown(
            _full_answer_text,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        ),
    )

    atom_cards = [_atom_card(p, atom) for atom in (ticket.atoms or [])]
    atoms_section = (
        ft.Column(spacing=SPACE["sm"], controls=atom_cards) if atom_cards else ft.Text("—", color=p["text_muted"])
    )

    block_cards: list[ft.Control] = []
    blocks_by_code = {_block_code_value(block): block for block in (ticket.answer_blocks or [])}
    for reference_block in _reference_blocks:
        block = blocks_by_code.get(reference_block.code)
        if block is not None:
            block_cards.append(_answer_block_card(p, block))
    blocks_section = (
        ft.Column(spacing=SPACE["sm"], controls=block_cards) if block_cards else ft.Text("—", color=p["text_muted"])
    )

    body = ft.Column(
        spacing=SPACE["lg"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            ft.Text(TEXT["reading.summary"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
            summary_control,
            ft.Text(TEXT["reading.atoms"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
            atoms_section,
            *(
                [
                    ft.Text(TEXT["reading.blocks"], size=15, weight=ft.FontWeight.W_600, color=p["text_primary"]),
                    blocks_section,
                ]
                if block_cards
                else []
            ),
        ],
    )

    # PDF-экспорт текущего билета.
    section_title, lecturer = _ticket_section_meta(state, ticket.section_id)
    default_name = _safe_filename(f"Тезис — Билет {ticket.title}", fallback=f"ticket-{ticket.ticket_id}")

    def _on_pdf_save(e: ft.FilePickerResultEvent) -> None:
        if not e.path:
            return
        out = Path(e.path)
        if out.suffix.lower() != ".pdf":
            out = out.with_suffix(".pdf")
        try:
            generate_ticket_pdf(
                ticket,
                out,
                section_title=section_title or None,
                lecturer=lecturer or None,
            )
            _toast(state, TEXT["pdf.saved"].format(path=str(out)))
        except Exception:
            _LOG.exception("Failed to export ticket PDF")
            _toast(state, TEXT["pdf.failed"], error=True)

    file_picker = ft.FilePicker(on_result=_on_pdf_save)
    state.page.overlay.append(file_picker)
    state.page.update()

    def _open_save_dialog(_e: ft.ControlEvent) -> None:
        file_picker.save_file(
            dialog_title=TEXT["pdf.dialog_title.ticket"],
            file_name=f"{default_name}.pdf",
            allowed_extensions=["pdf"],
            initial_directory=str(Path.home() / "Downloads"),
        )

    def _open_ask(_e: ft.ControlEvent) -> None:
        open_ask_etalon_dialog(state, ticket)

    actions = [
        ft.OutlinedButton(
            text=TEXT["ask.action"],
            icon=ft.Icons.AUTO_AWESOME,
            on_click=_open_ask,
        ),
        ft.OutlinedButton(
            text=TEXT["pdf.action.ticket"],
            icon=ft.Icons.PICTURE_AS_PDF,
            on_click=_open_save_dialog,
        ),
        ft.FilledButton(
            text=f"{TEXT['action.start']} — {TEXT['mode.plan.title']}",
            icon=ft.Icons.ARROW_FORWARD,
            on_click=lambda _: state.go(f"/training/{ticket.ticket_id}/plan"),
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.reading.title"],
        instruction=TEXT["mode.reading.hint"],
        content=body,
        actions=actions,
    )


def _toast(state: AppState, message: str, *, error: bool = False) -> None:
    """Coloured snackbar — вынесен наружу, чтобы переиспользоваться."""
    p = palette(state.is_dark)
    state.page.snack_bar = ft.SnackBar(
        ft.Text(message, color=p["text_primary"]),
        bgcolor=p["danger"] if error else p["bg_elevated"],
        duration=4000,
    )
    state.page.snack_bar.open = True
    try:
        state.page.update()
    except Exception:
        pass
