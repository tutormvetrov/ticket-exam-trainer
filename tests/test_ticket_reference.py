from __future__ import annotations

from types import SimpleNamespace

from application.ticket_reference import (
    clean_ticket_title,
    compose_reference_answer,
    iter_reference_segments,
    normalize_reference_text,
    reference_answer_preview,
)
from domain.answer_profile import AnswerBlockCode


def _block(code, text: str, *, title: str = "", missing: bool = False):
    return SimpleNamespace(
        block_code=code,
        title=title,
        expected_content=text,
        is_missing=missing,
    )


def test_compose_reference_answer_prefers_clean_blocks_in_canonical_order() -> None:
    ticket = SimpleNamespace(
        canonical_answer_summary="СЫРОЙ OCR ТЕКСТ",
        answer_blocks=[
            _block(AnswerBlockCode.THEORY, "Теория ответа.", title="Теория"),
            _block(AnswerBlockCode.INTRO, "Введение ответа.", title="Введение"),
            _block(AnswerBlockCode.EXTRA, "Черновик", missing=True),
        ],
    )

    text = compose_reference_answer(ticket)

    assert text == "Введение ответа.\n\nТеория ответа."
    assert "СЫРОЙ OCR" not in text


def test_compose_reference_answer_can_render_markdown_headings() -> None:
    ticket = SimpleNamespace(
        canonical_answer_summary="",
        answer_blocks=[
            _block("intro", "Первый блок.", title="Введение"),
            _block("skills", "Навыковый блок.", title="Навыки"),
        ],
    )

    text = compose_reference_answer(ticket, include_headings=True, heading_level=3)

    assert text.startswith("### Введение\n\nПервый блок.")
    assert "### Навыки\n\nНавыковый блок." in text


def test_normalize_reference_text_removes_ocr_spacing_and_keeps_lists_readable() -> None:
    raw = (
        "Низкая эффективность происходит из-за:\n"
        "•           собственного промедления,\n"
        "•           отсутствия самодисциплины,\n\n"
        "Выраженных        в           стоимостных показателях"
    )

    text = normalize_reference_text(raw)

    assert "        " not in text
    assert "- собственного промедления," in text
    assert "- отсутствия самодисциплины," in text
    assert "Выраженных в стоимостных показателях" in text


def test_normalize_reference_text_removes_service_fragment_prefixes() -> None:
    assert normalize_reference_text("**Основное содержание.** Законопроектная деятельность") == "Законопроектная деятельность"
    assert normalize_reference_text("**Фрагмент 3.** 4) одобрение закона") == "4) одобрение закона"
    assert normalize_reference_text("Фрагмент 4. Правительству РФ") == "Правительству РФ"


def test_clean_ticket_title_removes_author_tail() -> None:
    assert (
        clean_ticket_title(
            "Содержание и структура государственного бюджета: доходы и расходы, "
            "сбалансированность бюджета. Шаруханов Шарухан"
        )
        == "Содержание и структура государственного бюджета: доходы и расходы, сбалансированность бюджета"
    )
    assert clean_ticket_title("Психология сотрудничества в организации.Чернышов Елисей") == (
        "Психология сотрудничества в организации"
    )
    assert clean_ticket_title("Содержание и функции государственного кредита.( Камила") == (
        "Содержание и функции государственного кредита"
    )


def test_reference_preview_uses_blocks_and_compacts_whitespace() -> None:
    ticket = SimpleNamespace(
        canonical_answer_summary="ОРГАНИЗАЦИОННАЯ КУЛЬТУРА\nсырой текст",
        answer_blocks=[
            _block("intro", "Менеджмент — это управление.\n\nСамоменеджмент — управление собой."),
        ],
    )

    preview = reference_answer_preview(ticket, limit=200)

    assert preview == "Менеджмент — это управление. Самоменеджмент — управление собой."


def test_iter_reference_segments_distinguishes_lists_from_paragraphs() -> None:
    segments = list(iter_reference_segments("Задачи:\n- первая\n- вторая"))

    assert segments[0].kind == "paragraph"
    assert segments[0].lines == ("Задачи:",)
    assert segments[1].kind == "list"
    assert segments[1].lines == ("первая", "вторая")
