from __future__ import annotations

import json
from dataclasses import dataclass

from application.import_service import DocumentImportService, TicketCandidate
from application.scoring import MicroSkillScoringService
from application.ui_data import ReviewVerdict


@dataclass
class _FakeResponse:
    ok: bool
    content: str


class _FakeOllamaService:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[tuple] = []

    def review_answer(self, title, theses, answer, model):  # noqa: D401
        self.calls.append((title, theses, answer, model))
        return self._response


def _ticket():
    service = DocumentImportService()
    candidate = TicketCandidate(
        1,
        "What is public property?",
        (
            "Public property is a public resource. Examples include land and buildings. "
            "It has a legal regime. The management cycle includes accounting and review."
        ),
        0.9,
        "section-1",
    )
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "section-1", "doc-demo")
    return ticket


def test_review_verdict_uses_llm_when_available() -> None:
    ticket = _ticket()
    payload = {
        "thesis_verdicts": [
            {"thesis_label": "def", "status": "covered", "comment": "ok", "student_excerpt": "resource"},
        ],
        "structure_notes": ["note"],
        "strengths": ["strong def"],
        "recommendations": ["add examples"],
        "overall_score": 81,
        "overall_comment": "solid",
    }
    fake = _FakeOllamaService(_FakeResponse(ok=True, content=json.dumps(payload)))
    service = MicroSkillScoringService()

    verdict = service.build_review_verdict(ticket, "oral_full", "Answer text", ollama_service=fake, model="qwen3:8b")

    assert isinstance(verdict, ReviewVerdict)
    assert verdict.overall_score == 81
    assert verdict.overall_comment == "solid"
    assert verdict.recommendations == ["add examples"]
    assert fake.calls, "LLM должен быть вызван"


def test_review_verdict_falls_back_when_llm_returns_not_ok() -> None:
    ticket = _ticket()
    fake = _FakeOllamaService(_FakeResponse(ok=False, content=""))
    service = MicroSkillScoringService()

    verdict = service.build_review_verdict(ticket, "oral_full", "Answer", ollama_service=fake, model="qwen3:8b")
    assert isinstance(verdict, ReviewVerdict)
    # Fallback-комментарий отличается от LLM-ответа.
    assert "ключевых слов" in verdict.overall_comment


def test_review_verdict_falls_back_on_llm_exception() -> None:
    ticket = _ticket()

    class _ExplodingService:
        def review_answer(self, *args, **kwargs):
            raise RuntimeError("network down")

    service = MicroSkillScoringService()
    verdict = service.build_review_verdict(
        ticket, "oral_full", "Answer", ollama_service=_ExplodingService(), model="qwen3:8b"
    )
    assert "ключевых слов" in verdict.overall_comment


def test_review_verdict_falls_back_when_llm_returns_invalid_json() -> None:
    ticket = _ticket()
    fake = _FakeOllamaService(_FakeResponse(ok=True, content="{not valid json"))
    service = MicroSkillScoringService()

    verdict = service.build_review_verdict(ticket, "oral_full", "Answer", ollama_service=fake, model="qwen3:8b")
    assert "ключевых слов" in verdict.overall_comment


def test_review_verdict_returns_none_when_ticket_has_no_theses() -> None:
    service = DocumentImportService()
    candidate = TicketCandidate(1, "", "", 0.0, "section-1")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "section-1", "doc-demo")
    # Пустой билет → эталонных тезисов нет, верна None.
    verdict = MicroSkillScoringService().build_review_verdict(ticket, "oral_full", "Answer")
    assert verdict is None
