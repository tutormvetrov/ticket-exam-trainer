from __future__ import annotations

from pathlib import Path

from application.defense_ui_data import ModelRecommendation
from application.facade import AppFacade
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path


def _build_facade(tmp_path: Path) -> AppFacade:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    connection = connect_initialized(get_database_path(workspace_root))
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    return AppFacade(workspace_root, connection, settings_store)


def _fake_dlc_llm(_self, _service, _system: str, prompt: str, *, model: str):
    if "extract a defense dossier" in prompt:
        return {
            "claims": [
                {"kind": "relevance", "text": "Актуальность работы связана с цифровизацией управления.", "confidence": 0.82, "needs_review": False},
                {"kind": "goal", "text": "Цель работы состоит в разработке практических рекомендаций.", "confidence": 0.79, "needs_review": False},
                {"kind": "methods", "text": "Использованы сравнительный анализ, статистика и кейс-метод.", "confidence": 0.77, "needs_review": False},
                {"kind": "results", "text": "Получены рекомендации по повышению эффективности управления.", "confidence": 0.8, "needs_review": False},
            ],
            "risk_topics": [{"text": "Новизна раскрыта кратко", "confidence": 0.6}],
        }
    if "build a defense speech outline" in prompt:
        return {
            "segments": [
                {"title": "Актуальность", "talking_points": "Почему тема важна именно сейчас.", "target_seconds": 60},
                {"title": "Методы", "talking_points": "Какие методы использованы и зачем.", "target_seconds": 70},
                {"title": "Результаты", "talking_points": "Что именно получено и почему это полезно.", "target_seconds": 90},
            ]
        }
    if "create a slide storyboard" in prompt:
        return {
            "slides": [
                {"title": "Тема и актуальность", "purpose": "Открыть доклад", "talking_points": ["Контекст темы"], "evidence_links": ["thesis:1"]},
                {"title": "Результаты", "purpose": "Показать выводы", "talking_points": ["Главный результат"], "evidence_links": ["thesis:2"]},
            ]
        }
    if "generate defense follow-up questions" in prompt:
        return {
            "questions": [
                {"topic": "Новизна", "difficulty": 2, "question_text": "В чём именно состоит новизна работы?", "risk_tag": "novelty"},
                {"topic": "Методы", "difficulty": 2, "question_text": "Почему выбран именно этот набор методов?", "risk_tag": "methods"},
            ]
        }
    if "score a thesis defense answer" in prompt:
        return {
            "summary": "Ответ держит структуру, но новизна и ограничения раскрыты слишком кратко.",
            "followups": [
                "Чем ваша новизна отличается от уже известных подходов?",
                "Какие ограничения работы вы бы назвали первыми?",
            ],
            "scores": {},
            "weak_points": [],
        }
    return None


def test_defense_service_unlocks_imports_and_scores(tmp_path: Path, monkeypatch) -> None:
    facade = _build_facade(tmp_path)
    monkeypatch.setattr(type(facade.defense), "_call_llm_json", _fake_dlc_llm)
    monkeypatch.setattr(
        type(facade.defense),
        "_build_model_recommendation",
        lambda self: ModelRecommendation(
            model_name="mistral:instruct",
            label="Рекомендуемая модель: mistral:instruct",
            rationale="Локальный тестовый профиль.",
            available=True,
        ),
    )

    code = facade.issue_local_defense_activation_code()
    state = facade.activate_defense_dlc(code)
    assert state.activated is True

    project = facade.create_defense_project(
        {
            "title": "Цифровизация управления муниципальными ресурсами",
            "degree": "магистр",
            "specialty": "Государственное и муниципальное управление",
            "student_name": "Тестовый студент",
            "supervisor_name": "Научный руководитель",
            "defense_date": "2026-06-01",
            "discipline_profile": "applied",
        }
    )
    thesis_path = tmp_path / "thesis.txt"
    thesis_path.write_text(
        "Актуальность исследования определяется цифровизацией управления. "
        "Цель работы состоит в выработке практических рекомендаций. "
        "Использованы методы сравнительного анализа и кейс-метод. "
        "Результаты показывают рост эффективности управления.",
        encoding="utf-8",
    )
    notes_path = tmp_path / "notes.md"
    notes_path.write_text("Новизна работы состоит в связке цифрового профиля ресурсов и управленческого цикла.", encoding="utf-8")

    result = facade.import_defense_materials_with_progress(project.project_id, [thesis_path, notes_path])
    assert result.ok is True

    snapshot = facade.load_defense_workspace_snapshot(project.project_id)
    assert snapshot.license_state.activated is True
    assert snapshot.active_project is not None
    assert len(snapshot.active_project.sources) == 2
    assert len(snapshot.active_project.claims) >= 4
    assert snapshot.active_project.outlines["7"]
    assert snapshot.active_project.slides
    assert snapshot.active_project.questions

    evaluation = facade.evaluate_defense_mock(project.project_id, "full_mock_defense", "Тема актуальна, методы подобраны под задачу, результаты прикладные.")
    assert evaluation.ok is True
    assert evaluation.summary
    assert evaluation.followup_questions

    facade.connection.close()


def test_defense_workspace_starts_locked(tmp_path: Path) -> None:
    facade = _build_facade(tmp_path)
    snapshot = facade.load_defense_workspace_snapshot()
    assert snapshot.license_state.activated is False
    assert snapshot.projects == []
    facade.connection.close()
