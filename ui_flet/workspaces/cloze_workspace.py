"""Cloze workspace — fill-in-the-blanks on definition/features atoms.

Generation rule (rule-based, no LLM):
  * pick 1-3 atoms of type `definition` or `features` from the ticket
  * replace every 5th "significant" word (len ≥ 4, not a stopword) with
    a TextField sized to the original word's length
  * user fills in; on "Проверить" we compare case-insensitive and show
    a hit-count and percentage

We join the user's inputs with spaces and ship them to
`facade.evaluate_answer(ticket_id, "cloze", joined)`. The facade's
rule-based scoring reads keyword matches out of this text.
"""

from __future__ import annotations

import re
from typing import List

import flet as ft

from ui_flet.components.training_workspace_base import build_workspace_frame
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import palette, SPACE, RADIUS


_RU_STOPWORDS = {
    "или", "при", "для", "это", "этот", "эта", "это", "как", "что", "чтобы",
    "если", "либо", "также", "который", "которая", "которые", "между", "через",
    "только", "более", "менее", "всего", "всех", "свой", "быть", "есть",
    "которое", "таких", "таким", "такой", "такая", "такие", "того",
}


def _pick_atoms(ticket, max_atoms: int = 3):
    picked = []
    for atom in ticket.atoms or []:
        atype = str(atom.type)
        if atype in ("definition", "features"):
            if (atom.text or "").strip():
                picked.append(atom)
        if len(picked) >= max_atoms:
            break
    if picked:
        return picked
    # fallback: first atom with text
    for atom in ticket.atoms or []:
        if (atom.text or "").strip():
            return [atom]
    return []


def _tokenize(text: str) -> List[tuple[str, str]]:
    """Return a list of (kind, value): kind is "word" | "gap"."""
    tokens: list[tuple[str, str]] = []
    for match in re.finditer(r"[\wа-яёА-ЯЁ-]+|\s+|[^\w\s]", text, flags=re.UNICODE):
        piece = match.group(0)
        if piece.isspace():
            tokens.append(("space", piece))
        elif re.match(r"[\wа-яёА-ЯЁ-]+", piece, flags=re.UNICODE):
            tokens.append(("word", piece))
        else:
            tokens.append(("punct", piece))
    return tokens


def _is_significant(word: str) -> bool:
    stripped = word.strip("-")
    if len(stripped) < 4:
        return False
    if stripped.isdigit():
        return False
    if stripped.lower() in _RU_STOPWORDS:
        return False
    return True


def _build_cloze_for_atom(atom) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Tokenize an atom's text and mark every 5th significant word as a gap.

    Returns (pieces, expected_words).
    pieces is a list of (kind, value, expected_or_empty):
      kind ∈ {"text", "gap"}.
    """
    text = atom.text or ""
    tokens = _tokenize(text)
    pieces: list[tuple[str, str, str]] = []
    expected_words: list[str] = []
    significant_index = 0
    for kind, value in tokens:
        if kind == "word" and _is_significant(value):
            significant_index += 1
            if significant_index % 5 == 0:
                pieces.append(("gap", value, value))
                expected_words.append(value)
                continue
        pieces.append(("text", value, ""))
    # If there are no gaps at all (short text), force one gap on the longest word.
    if not expected_words:
        longest_idx = -1
        longest_len = 0
        for idx, (kind, value, _exp) in enumerate(pieces):
            if kind == "text":
                if re.match(r"[\wа-яёА-ЯЁ-]+", value, flags=re.UNICODE) and len(value) > longest_len:
                    longest_len = len(value)
                    longest_idx = idx
        if longest_idx >= 0:
            word_value = pieces[longest_idx][1]
            pieces[longest_idx] = ("gap", word_value, word_value)
            expected_words.append(word_value)
    return pieces, expected_words


def _gap_field(palette_map: dict, expected: str) -> ft.TextField:
    width = max(60, min(220, len(expected) * 12 + 28))
    return ft.TextField(
        data=expected,
        width=width,
        height=36,
        content_padding=ft.padding.symmetric(horizontal=SPACE["sm"], vertical=0),
        border_color=palette_map["border_medium"],
        focused_border_color=palette_map["accent"],
        text_size=13,
        hint_text="_" * len(expected),
    )


def _render_atom(palette_map: dict, atom) -> tuple[ft.Control, list[ft.TextField], list[str]]:
    """Return (control, text_fields_in_order, expected_words_in_order)."""
    pieces, expected_words = _build_cloze_for_atom(atom)
    inline: list[ft.Control] = []
    fields: list[ft.TextField] = []
    for kind, value, expected in pieces:
        if kind == "text":
            inline.append(
                ft.Text(
                    value,
                    size=13,
                    color=palette_map["text_primary"],
                    selectable=True,
                )
            )
        else:
            field = _gap_field(palette_map, expected)
            fields.append(field)
            inline.append(field)

    card = ft.Container(
        padding=SPACE["md"],
        bgcolor=palette_map["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, palette_map["border_soft"]),
        content=ft.Column(
            spacing=SPACE["sm"],
            controls=[
                ft.Text(
                    atom.label or str(atom.type),
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=palette_map["text_primary"],
                ),
                ft.Row(
                    controls=inline,
                    wrap=True,
                    spacing=SPACE["xs"],
                    run_spacing=SPACE["xs"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
        ),
    )
    return card, fields, expected_words


def build_workspace(state: AppState, ticket) -> ft.Control:
    p = palette(state.is_dark)

    atoms = _pick_atoms(ticket, max_atoms=3)
    atom_cards: list[ft.Control] = []
    all_fields: list[ft.TextField] = []
    all_expected: list[str] = []
    for atom in atoms:
        card, fields, expected = _render_atom(p, atom)
        atom_cards.append(card)
        all_fields.extend(fields)
        all_expected.extend(expected)

    if not atom_cards:
        body = ft.Text(TEXT["cloze.empty"], color=p["text_muted"])
        return build_workspace_frame(
            state,
            title=TEXT["mode.cloze.title"],
            instruction=TEXT["mode.cloze.hint"],
            content=body,
            actions=[],
        )

    result_box = ft.Column(spacing=SPACE["sm"], visible=False)

    def _on_check(_evt) -> None:
        hits = 0
        for field, expected in zip(all_fields, all_expected):
            user_val = (field.value or "").strip().casefold()
            exp_val = (expected or "").strip().casefold()
            if user_val and user_val == exp_val:
                hits += 1
                field.border_color = p["success"]
            else:
                field.border_color = p["danger"]
            field.update()

        total = max(1, len(all_expected))
        percent = int(round(hits / total * 100))
        joined = " ".join((f.value or "").strip() for f in all_fields)

        try:
            result = state.facade.evaluate_answer(ticket.ticket_id, "cloze", joined)
            facade_score = getattr(result, "score_percent", percent)
            feedback = getattr(result, "feedback", "") or ""
        except Exception as exc:  # noqa: BLE001
            facade_score = percent
            feedback = str(exc)

        result_box.controls = [
            ft.Text(
                f"{TEXT['result.matches']}: {hits} из {len(all_expected)} ({percent}%)",
                size=14,
                weight=ft.FontWeight.W_600,
                color=p["text_primary"],
            ),
            ft.Text(
                f"{TEXT['result.score']}: {facade_score}%",
                size=13,
                color=p["text_secondary"],
            ),
            *([ft.Text(feedback, size=13, color=p["text_secondary"], selectable=True)] if feedback else []),
        ]
        result_box.visible = True
        result_box.update()

    body = ft.Column(
        spacing=SPACE["md"],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        controls=[
            *atom_cards,
            ft.Container(
                padding=SPACE["md"],
                bgcolor=p["bg_elevated"],
                border_radius=RADIUS["md"],
                border=ft.border.all(1, p["border_soft"]),
                content=result_box,
            ),
        ],
    )

    actions = [
        ft.FilledButton(
            text=TEXT["action.check"],
            icon=ft.Icons.CHECK,
            on_click=_on_check,
        ),
    ]

    return build_workspace_frame(
        state,
        title=TEXT["mode.cloze.title"],
        instruction=TEXT["mode.cloze.hint"],
        content=body,
        actions=actions,
    )
