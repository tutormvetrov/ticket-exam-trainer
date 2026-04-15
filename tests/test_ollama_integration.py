from __future__ import annotations

import pytest

from application.facade import AppFacade
from application.settings_store import SettingsStore
from application.import_service import DocumentImportService, TicketCandidate
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.service import OllamaService

pytestmark = pytest.mark.live_ollama


def test_ollama_connection_check() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=30)
    diagnostics = service.inspect("qwen3:8b")
    assert diagnostics.endpoint_ok
    assert diagnostics.model_ok


def test_ollama_fallback_when_unavailable() -> None:
    service = OllamaService("http://localhost:65500", timeout_seconds=1)
    diagnostics = service.inspect("qwen3:8b")
    assert not diagnostics.endpoint_ok


def test_real_response_from_local_model_if_available() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=240)
    diagnostics = service.inspect("qwen3:8b")
    if not diagnostics.endpoint_ok or not diagnostics.model_ok:
        pytest.skip("Local Ollama or qwen3:8b is unavailable")

    result = service.rewrite_question(
        "What is active recall?",
        "Active recall is a memory practice based on retrieving information from memory.",
        "qwen3:8b",
    )
    assert result.ok
    assert result.used_llm
    assert result.content


def test_llm_assisted_structuring_if_available() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=240)
    diagnostics = service.inspect("qwen3:8b")
    if not diagnostics.endpoint_ok or not diagnostics.model_ok:
        pytest.skip("Local Ollama or qwen3:8b is unavailable")

    import_service = DocumentImportService(
        ollama_service=service,
        llm_model="qwen3:8b",
        enable_llm_structuring=True,
    )
    candidate = TicketCandidate(
        index=1,
        title="What is public property as an object of management?",
        body="Public property is a public resource assigned to public bodies. It has a legal regime and requires control.",
        confidence=0.5,
        section_title="public-assets",
    )
    ticket, used_llm, warning = import_service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    assert warning == ""
    assert used_llm
    assert len(ticket.atoms) >= 1
    assert ticket.canonical_answer_summary
    assert len(ticket.skills) >= 2
    assert len(ticket.exercise_templates) >= 5


def test_live_defense_flow_if_available(tmp_path) -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=240)
    diagnostics = service.inspect("qwen3:8b")
    if not diagnostics.endpoint_ok or not diagnostics.model_ok:
        pytest.skip("Local Ollama or qwen3:8b is unavailable")

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    connection = connect_initialized(get_database_path(workspace_root))
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)

    code = facade.issue_local_defense_activation_code()
    facade.activate_defense_dlc(code)
    project = facade.create_defense_project(
        {
            "title": "Цифровизация муниципальных сервисов",
            "degree": "магистр",
            "specialty": "ГМУ",
            "student_name": "Тестовый студент",
            "supervisor_name": "Научрук",
            "defense_date": "2026-06-01",
            "discipline_profile": "applied",
        }
    )
    thesis_path = workspace_root / "thesis.txt"
    thesis_path.write_text(
        "Актуальность исследования связана с цифровизацией муниципальных сервисов. "
        "Цель работы состоит в разработке практических рекомендаций. "
        "Использованы сравнительный анализ и кейс-метод. "
        "Получены результаты по ускорению процессов, но ограничения описаны кратко.",
        encoding="utf-8",
    )
    notes_path = workspace_root / "notes.md"
    notes_path.write_text(
        "Новизна состоит в связке цифрового профиля услуги и управленческого цикла. "
        "Практическая значимость связана с внедрением рекомендаций в органы местного самоуправления.",
        encoding="utf-8",
    )

    result = facade.import_defense_materials_with_progress(project.project_id, [thesis_path, notes_path])
    snapshot = facade.load_defense_workspace_snapshot(project.project_id)
    evaluation = facade.evaluate_defense_mock_with_context(
        project.project_id,
        "persona_qa",
        "opponent",
        420,
        "Новизна работы состоит в новой связке цифрового профиля услуги и управленческого цикла. "
        "Методы и результаты связаны, но ограничения нужно проговорить точнее.",
    )

    assert result.ok
    assert snapshot.active_project is not None
    assert snapshot.active_project.gap_findings
    assert snapshot.active_project.repair_tasks
    assert evaluation.ok
    assert evaluation.followup_questions

    connection.close()
