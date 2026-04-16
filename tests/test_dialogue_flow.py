from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from application.facade import AppFacade
from application.import_service import DocumentImportService, TicketCandidate
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from domain.knowledge import Exam, Section, SourceDocument
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.dialogue import DialogueTurnPayload, DialogueTurnResult
from infrastructure.ollama.service import OllamaDiagnostics, OllamaScenarioResult


def _build_ticket(title: str, body: str):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, body, 0.9, "public-assets")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    return ticket


def _build_facade(tmp_path: Path) -> tuple[AppFacade, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    connection = connect_initialized(get_database_path(workspace_root))
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(
        replace(
            DEFAULT_OLLAMA_SETTINGS,
            auto_check_ollama_on_start=False,
            auto_check_updates_on_start=False,
        )
    )
    return AppFacade(workspace_root, connection, settings_store), workspace_root


def _seed_ticket(facade: AppFacade, workspace_root: Path, ticket) -> None:
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


class _FakeDialogueOllama:
    def __init__(self, *, finish_on_submit: bool) -> None:
        self.finish_on_submit = finish_on_submit
        self.turn_calls: list[tuple[int, str]] = []
        self.review_calls: list[str] = []

    def generate_dialogue_turn(self, context, model: str) -> DialogueTurnResult:
        self.turn_calls.append((context.turn_index, context.persona_kind))
        if not context.transcript:
            payload = DialogueTurnPayload(
                feedback_text="Начните с опорного определения.",
                next_question="Что такое публичная собственность?",
                weakness_focus="определение",
                should_finish=False,
                finish_reason="",
            )
        elif self.finish_on_submit:
            payload = DialogueTurnPayload(
                feedback_text="Базовый каркас уже есть.",
                next_question="",
                weakness_focus="правовой режим",
                should_finish=True,
                finish_reason="enough_for_review",
            )
        else:
            payload = DialogueTurnPayload(
                feedback_text="Добавьте правовой режим и практический пример.",
                next_question="Каков правовой режим публичной собственности?",
                weakness_focus="правовой режим",
                should_finish=False,
                finish_reason="",
            )
        return DialogueTurnResult(True, payload, True, False, 9)

    def generate_followup_questions(self, ticket_title: str, summary: str, weak_points: list[str], model: str, count: int = 3):
        return OllamaScenarioResult(True, "- Уточните правовой режим", True, 8)

    def review_answer(self, ticket_title: str, reference_theses: list[dict[str, str]], student_answer: str, model: str):
        self.review_calls.append(student_answer)
        payload = json.dumps(
            {
                "thesis_verdicts": [
                    {
                        "thesis_label": "Definition",
                        "status": "covered",
                        "comment": "Верно.",
                        "student_excerpt": "Публичная собственность — это ресурс.",
                    }
                ],
                "structure_notes": [],
                "strengths": ["Есть определение"],
                "recommendations": ["Добавить правовой режим"],
                "overall_score": 74,
                "overall_comment": "Каркас ответа собран, но правовой режим раскрыт слабо.",
            },
            ensure_ascii=False,
        )
        return OllamaScenarioResult(True, payload, True, 11)


def test_dialogue_session_finalizes_and_updates_scoring(tmp_path: Path, monkeypatch) -> None:
    facade, workspace_root = _build_facade(tmp_path)
    ticket = _build_ticket(
        "What is public property?",
        "Public property is a public resource. It has a legal regime. Examples include land and buildings.",
    )
    _seed_ticket(facade, workspace_root, ticket)
    fake_service = _FakeDialogueOllama(finish_on_submit=True)
    monkeypatch.setattr(type(facade), "build_ollama_service", lambda self, timeout_seconds=None: fake_service)

    session = facade.start_dialogue_session(ticket.ticket_id, "tutor")

    assert session.session.status == "active"
    assert len(session.turns) == 1
    assert session.turns[0].speaker == "assistant"
    assert facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"] == 0

    updated = facade.submit_dialogue_turn(
        session.session.session_id,
        "Публичная собственность — это публичный ресурс с особым правовым режимом.",
        expected_last_turn_index=session.session.last_turn_index,
    )

    assert updated.session.status == "completed"
    assert updated.result is not None
    assert updated.result.score_percent >= 0
    assert updated.result.review is not None
    assert len(updated.turns) == 3
    assert updated.turns[-1].speaker == "assistant"
    assert facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"] == 1
    assert facade.connection.execute("SELECT COUNT(*) AS total FROM ticket_mastery_profiles").fetchone()["total"] == 1
    assert fake_service.review_calls

    facade.connection.close()


def test_dialogue_session_resumes_after_restart(tmp_path: Path, monkeypatch) -> None:
    facade, workspace_root = _build_facade(tmp_path)
    ticket = _build_ticket(
        "What is public property?",
        "Public property is a public resource. It has a legal regime. Examples include land and buildings.",
    )
    _seed_ticket(facade, workspace_root, ticket)
    monkeypatch.setattr(type(facade), "build_ollama_service", lambda self, timeout_seconds=None: _FakeDialogueOllama(finish_on_submit=False))

    session = facade.start_dialogue_session(ticket.ticket_id, "tutor")
    active = facade.submit_dialogue_turn(
        session.session.session_id,
        "Публичная собственность — это публичный ресурс.",
        expected_last_turn_index=session.session.last_turn_index,
    )
    assert active.session.status == "active"
    assert len(active.turns) == 3
    facade.connection.close()

    reopened_connection = connect_initialized(get_database_path(workspace_root))
    reopened_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    reopened_facade = AppFacade(workspace_root, reopened_connection, reopened_store)
    snapshot = reopened_facade.load_dialogue_snapshot()

    assert snapshot.active_sessions
    resumed = reopened_facade.load_dialogue_session(snapshot.active_sessions[0].session_id)
    assert resumed.session.status == "active"
    assert len(resumed.turns) == 3

    reopened_facade.connection.close()


def test_dialogue_submit_ignores_stale_last_turn_index(tmp_path: Path, monkeypatch) -> None:
    facade, workspace_root = _build_facade(tmp_path)
    ticket = _build_ticket(
        "What is public property?",
        "Public property is a public resource. It has a legal regime. Examples include land and buildings.",
    )
    _seed_ticket(facade, workspace_root, ticket)
    monkeypatch.setattr(type(facade), "build_ollama_service", lambda self, timeout_seconds=None: _FakeDialogueOllama(finish_on_submit=False))

    session = facade.start_dialogue_session(ticket.ticket_id, "tutor")
    current = facade.submit_dialogue_turn(
        session.session.session_id,
        "Публичная собственность — это публичный ресурс.",
        expected_last_turn_index=session.session.last_turn_index,
    )
    stale = facade.submit_dialogue_turn(
        session.session.session_id,
        "Второй ответ должен быть проигнорирован как stale.",
        expected_last_turn_index=session.session.last_turn_index,
    )

    assert current.session.last_turn_index == stale.session.last_turn_index
    assert current.session.user_turn_count == stale.session.user_turn_count
    assert len(stale.turns) == len(current.turns)

    facade.connection.close()


@pytest.mark.ui
def test_dialogue_view_blocks_until_ollama_is_ready(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
    from ui.theme import set_app_theme

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        set_app_theme(app, "light")

    facade, workspace_root = _build_facade(tmp_path)
    ticket = _build_ticket(
        "What is public property?",
        "Public property is a public resource. It has a legal regime. Examples include land and buildings.",
    )
    _seed_ticket(facade, workspace_root, ticket)
    window = MainWindow(app, facade, "light", suppress_startup_background_tasks=True)

    try:
        window.refresh_all_views()
        window.switch_view("dialogue")
        app.processEvents()

        dialogue = window.views["dialogue"]
        assert dialogue.gate_card.isHidden() is False
        assert dialogue.body_host.isHidden() is True

        window.apply_ollama_diagnostics(
            OllamaDiagnostics(
                endpoint_ok=True,
                model_ok=True,
                endpoint_message="Endpoint: OK",
                model_message="Модель доступна",
                model_name="qwen3:8b",
            )
        )
        window.open_dialogue_ticket(ticket.ticket_id)
        app.processEvents()

        assert dialogue.gate_card.isHidden() is True
        assert dialogue.body_host.isHidden() is False
        assert window.current_key == "dialogue"
        assert dialogue.selected_ticket_id == ticket.ticket_id
        assert dialogue.start_button.isEnabled() is True
    finally:
        window.close()
        window.facade.connection.close()
