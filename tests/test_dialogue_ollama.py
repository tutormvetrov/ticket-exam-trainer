from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from dataclasses import replace

from application.facade import AppFacade
from application.import_service import DocumentImportService, TicketCandidate
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from application.ui_data import TrainingEvaluationResult
from domain.knowledge import Exam, Section, SourceDocument
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.client import OllamaResponse
from infrastructure.ollama.dialogue import DialogueTranscriptLine, DialogueTurnContext
from infrastructure.ollama.prompts import dialogue_turn_prompt
from infrastructure.ollama.service import OllamaScenarioResult, OllamaService


def _build_ticket(title: str, body: str):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, body, 0.9, "public-assets")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    return ticket


def test_dialogue_turn_prompt_includes_ticket_grounding_and_json_rules() -> None:
    context = DialogueTurnContext(
        session_id="session-1",
        ticket_id="ticket-1",
        ticket_title="What is public property?",
        ticket_summary="Public property is a public resource with a legal regime.",
        persona_kind="tutor",
        turn_index=2,
        transcript=[
            DialogueTranscriptLine("assistant", "Explain the definition."),
            DialogueTranscriptLine("user", "It is a public resource."),
        ],
        ticket_atoms=[
            {"atom_id": "a1", "type": "definition", "label": "Definition", "text": "Public property is a public resource."},
        ],
        ticket_answer_blocks=[
            {"block_code": "intro", "title": "Intro", "expected_content": "Start with a definition."},
        ],
        examiner_prompts=["What is the core definition?"],
        answer_profile_hints=["Mention legal regime."],
        weak_points=["legal regime"],
    )

    system, prompt = dialogue_turn_prompt(context)

    assert "Socratic tutor" in system
    assert "Do not introduce new facts" in system
    assert "feedback_text" in system
    assert "next_question" in system
    assert "What is public property?" in prompt
    assert "Public property is a public resource with a legal regime." in prompt
    assert "\"speaker\": \"assistant\"" in prompt
    assert "\"text\": \"It is a public resource.\"" in prompt
    assert "\"legal regime\"" in prompt
    assert "ANSWER_PROFILE_HINTS" in prompt
    assert "TICKET_ATOMS" in prompt
    assert "ANSWER_BLOCKS" in prompt
    assert "TRANSCRIPT" in prompt


def test_generate_dialogue_turn_parses_structured_json(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    context = DialogueTurnContext(
        session_id="session-2",
        ticket_id="ticket-2",
        ticket_title="What is public property?",
        ticket_summary="Public property is a public resource.",
        persona_kind="examiner",
        turn_index=3,
        weak_points=["legal regime"],
    )
    payload = {
        "feedback_text": "Вы забыли про правовой режим.",
        "next_question": "Каков правовой режим публичной собственности?",
        "weakness_focus": "правовой режим",
        "should_finish": False,
        "finish_reason": "",
    }

    monkeypatch.setattr(
        service.client,
        "generate",
        lambda model, prompt, *, system="", format_name=None, temperature=0.2: OllamaResponse(
            ok=True,
            status_code=200,
            payload={"response": json.dumps(payload, ensure_ascii=False)},
            latency_ms=13,
        ),
    )

    result = service.generate_dialogue_turn(context, "qwen3:8b")

    assert result.ok is True
    assert result.used_llm is True
    assert result.used_fallback is False
    assert result.payload.feedback_text == payload["feedback_text"]
    assert result.payload.next_question == payload["next_question"]
    assert result.payload.weakness_focus == payload["weakness_focus"]
    assert result.payload.should_finish is False
    assert result.payload.finish_reason == ""


def test_generate_dialogue_turn_falls_back_to_followup_generator_on_bad_json(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    context = DialogueTurnContext(
        session_id="session-3",
        ticket_id="ticket-3",
        ticket_title="What is public property?",
        ticket_summary="Public property is a public resource.",
        persona_kind="tutor",
        turn_index=4,
        weak_points=["legal regime"],
        answer_profile_hints=["mention legal regime"],
    )
    followup_calls: list[tuple[str, str, list[str], str, int]] = []

    monkeypatch.setattr(
        service.client,
        "generate",
        lambda model, prompt, *, system="", format_name=None, temperature=0.2: OllamaResponse(
            ok=True,
            status_code=200,
            payload={"response": "{bad json"},
            latency_ms=19,
        ),
    )

    def fake_followups(ticket_title: str, summary: str, weak_points: list[str], model: str, count: int = 3):
        followup_calls.append((ticket_title, summary, weak_points, model, count))
        return OllamaScenarioResult(True, "- Каков правовой режим публичной собственности?", True, 7)

    monkeypatch.setattr(service, "generate_followup_questions", fake_followups)

    result = service.generate_dialogue_turn(context, "qwen3:8b")

    assert result.ok is True
    assert result.used_llm is False
    assert result.used_fallback is True
    assert followup_calls == [("What is public property?", "Public property is a public resource.", ["legal regime"], "qwen3:8b", 1)]
    assert result.payload.next_question == "Каков правовой режим публичной собственности?"
    assert "Сфокусируйтесь" in result.payload.feedback_text
    assert result.payload.weakness_focus == "legal regime"
    assert result.payload.should_finish is False
    assert result.payload.finish_reason == "fallback_followup_generator"


def test_dialogue_facade_finalization_reuses_scoring_and_llm_hooks(tmp_path: Path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    connection = connect_initialized(get_database_path(workspace_root))
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(
        replace(
            DEFAULT_OLLAMA_SETTINGS,
            auto_check_ollama_on_start=False,
            auto_check_updates_on_start=False,
            examiner_followups=True,
            rewrite_questions=False,
        )
    )
    facade = AppFacade(workspace_root, connection, settings_store)

    ticket = _build_ticket(
        "What is public property?",
        "Public property is a public resource. Examples include land and buildings. The management cycle includes accounting and review.",
    )
    facade.repository.save_exam(Exam("exam-demo", "Demo Exam", "Demo", 1, "subject-demo"))
    facade.repository.save_section(Section("public-assets", "exam-demo", "Public Assets", 1))
    facade.repository.save_source_document(
        SourceDocument(
            document_id="doc-demo",
            exam_id="exam-demo",
            subject_id="subject-demo",
            title="Demo Document",
            file_path=str(workspace_root / "demo.txt"),
            file_type="txt",
            size_bytes=1,
            imported_at=datetime.now(),
        ),
        raw_text="Demo source text",
        status="structured",
        ticket_total=1,
        tickets_llm_done=1,
        last_attempted_at=datetime.now().isoformat(),
    )
    facade.repository.save_ticket_map(ticket)

    class FakeOllamaService:
        def __init__(self) -> None:
            self.followup_calls: list[tuple[str, str, list[str], str, int]] = []
            self.review_calls: list[tuple[str, list[dict[str, str]], str, str]] = []

        def generate_followup_questions(self, ticket_title: str, summary: str, weak_points: list[str], model: str, count: int = 3):
            self.followup_calls.append((ticket_title, summary, weak_points, model, count))
            return OllamaScenarioResult(True, "- Уточните правовой режим\n- Приведите пример", True, 9)

        def review_answer(self, ticket_title: str, reference_theses: list[dict[str, str]], student_answer: str, model: str):
            self.review_calls.append((ticket_title, reference_theses, student_answer, model))
            review_json = json.dumps(
                {
                    "thesis_verdicts": [
                        {
                            "thesis_label": "Definition",
                            "status": "covered",
                            "comment": "Верно.",
                            "student_excerpt": "Public property is a resource.",
                        }
                    ],
                    "structure_notes": [],
                    "strengths": ["Good definition"],
                    "recommendations": ["Add the legal regime"],
                    "overall_score": 78,
                    "overall_comment": "Ключевой тезис раскрыт.",
                },
                ensure_ascii=False,
            )
            return OllamaScenarioResult(True, review_json, True, 11)

    fake_service = FakeOllamaService()
    monkeypatch.setattr(type(facade), "build_ollama_service", lambda self, timeout_seconds=None: fake_service)

    result = facade.evaluate_answer(
        ticket.ticket_id,
        "review",
        "Public property is a resource.",
    )

    assert isinstance(result, TrainingEvaluationResult)
    assert result.ok is True
    assert result.review is not None
    assert result.review.overall_score == 78
    assert result.followup_questions
    assert fake_service.followup_calls
    assert fake_service.review_calls

    connection.close()
