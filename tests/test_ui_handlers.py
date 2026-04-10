from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import time

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.settings_store import SettingsStore
from application.ui_data import ImportExecutionResult
from infrastructure.db import connect_initialized, get_database_path
from ui.main_window import MainWindow
from ui.theme import set_app_theme

pytestmark = pytest.mark.ui


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        set_app_theme(app, "light")
    return app


def _build_window(tmp_path: Path, settings: OllamaSettings | None = None) -> tuple[MainWindow, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    effective_settings = replace(settings or DEFAULT_OLLAMA_SETTINGS, auto_check_ollama_on_start=False)
    settings_store.save(effective_settings)
    facade = AppFacade(workspace_root, connection, settings_store)
    window = MainWindow(_qapp(), facade, "light")
    return window, workspace_root


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    app = _qapp()
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    app.processEvents()
    return predicate()


def test_import_dialog_shows_real_error_for_unsupported_file(tmp_path: Path, monkeypatch) -> None:
    window, _ = _build_window(tmp_path)
    captured: dict[str, str] = {}

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(tmp_path / "broken.txt"), ""))

    def fake_critical(parent, title: str, text: str):
        captured["title"] = title
        captured["text"] = text
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "critical", fake_critical)
    window.open_import_dialog()

    assert captured["title"] == "Импорт"
    assert "Unsupported document format" in captured["text"]
    window.close()
    window.facade.connection.close()


def test_settings_sections_persist_real_values(tmp_path: Path, monkeypatch) -> None:
    window, workspace_root = _build_window(tmp_path)
    captured: dict[str, str] = {}

    def fake_information(parent, title: str, text: str):
        captured["title"] = title
        captured["text"] = text
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", fake_information)

    settings_view = window.views["settings"]
    monkeypatch.setattr(settings_view, "check_connection", lambda: None)

    settings_view.theme_combo.setCurrentIndex(settings_view.theme_combo.findData("dark"))
    settings_view.startup_view_combo.setCurrentIndex(settings_view.startup_view_combo.findData("training"))
    settings_view.auto_check_card.toggle.setChecked(False)
    settings_view.dlc_card.toggle.setChecked(False)
    settings_view.default_import_dir_input.setText(str(workspace_root))
    settings_view.import_format_combo.setCurrentIndex(settings_view.import_format_combo.findData("pdf"))
    settings_view.import_llm_card.toggle.setChecked(False)
    settings_view.training_mode_combo.setCurrentIndex(settings_view.training_mode_combo.findData("mini-exam"))
    settings_view.review_mode_combo.setCurrentIndex(settings_view.review_mode_combo.findData("exam_crunch"))
    settings_view.queue_size_combo.setCurrentIndex(settings_view.queue_size_combo.findData(12))
    settings_view.save_settings()

    saved = (workspace_root / "app_data" / "settings.json").read_text(encoding="utf-8")

    assert captured["title"]
    assert '"theme_name": "dark"' in saved
    assert '"startup_view": "training"' in saved
    assert '"auto_check_ollama_on_start": false' in saved
    assert '"show_dlc_teaser": false' in saved
    assert '"preferred_import_format": "pdf"' in saved
    assert '"import_llm_assist": false' in saved
    assert '"default_training_mode": "mini-exam"' in saved
    assert '"review_mode": "exam_crunch"' in saved
    assert '"training_queue_size": 12' in saved
    window.close()
    window.facade.connection.close()


def test_save_settings_with_invalid_ollama_url_keeps_honest_status(tmp_path: Path, monkeypatch) -> None:
    invalid_settings = OllamaSettings(
        base_url="http://localhost:65500",
        model=DEFAULT_OLLAMA_SETTINGS.model,
        models_path=DEFAULT_OLLAMA_SETTINGS.models_path,
        timeout_seconds=2,
        rewrite_questions=DEFAULT_OLLAMA_SETTINGS.rewrite_questions,
        examiner_followups=DEFAULT_OLLAMA_SETTINGS.examiner_followups,
        rule_based_fallback=DEFAULT_OLLAMA_SETTINGS.rule_based_fallback,
    )
    window, workspace_root = _build_window(tmp_path, invalid_settings)
    captured: dict[str, str] = {}

    def fake_information(parent, title: str, text: str):
        captured["title"] = title
        captured["text"] = text
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", fake_information)

    settings_view = window.views["settings"]
    settings_view.url_input.setText("http://localhost:65500")
    settings_view.model_combo.setCurrentText("mistral:instruct")
    settings_view.timeout_stepper.set_value(2)
    settings_view.save_settings()
    assert _wait_for(lambda: settings_view.status_pill.text() != "Проверка...", timeout=5.0)

    settings_file = workspace_root / "app_data" / "settings.json"
    saved = settings_file.read_text(encoding="utf-8")

    assert captured["title"] == "Настройки"
    assert "сохранены" in captured["text"]
    assert "Недоступно" in settings_view.status_pill.text()
    assert settings_view.error_label.text().startswith("Ошибка:")
    assert "http://localhost:65500" in saved
    window.close()
    window.facade.connection.close()


def test_successful_import_switches_to_import_view_and_shows_handoff(tmp_path: Path, monkeypatch) -> None:
    window, _ = _build_window(tmp_path)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(tmp_path / "demo.docx"), ""))
    monkeypatch.setattr(
        window,
        "_import_in_background",
        lambda path, progress_callback: (
            progress_callback(42, "Построение карты билета", "Билет 5 из 12"),
            ImportExecutionResult(
                ok=True,
                document_id="doc-demo",
                document_title="Demo Import",
                status="structured",
                tickets_created=12,
                sections_created=4,
                warnings=["Часть структуры распознана через fallback."],
                used_llm_assist=True,
                llm_done_tickets=12,
            ),
        )[1],
    )

    window.open_import_dialog()
    assert _wait_for(lambda: window.views["import"].last_result.ok, timeout=5.0)

    import_view = window.views["import"]
    assert window.current_key == "import"
    assert import_view.summary_status.text() == "Последний импорт завершён полностью"
    assert "Создано билетов: 12" in import_view.summary_body.text()
    assert "LLM:" in import_view.summary_chip.text()
    assert "Откройте библиотеку" in import_view.handoff_body.text()
    assert import_view.resume_button.isHidden()
    window.close()
    window.facade.connection.close()


def test_import_view_shows_partial_llm_and_resume_button(tmp_path: Path) -> None:
    window, _ = _build_window(tmp_path)
    import_view = window.views["import"]

    import_view.set_last_result(
        ImportExecutionResult(
            ok=True,
            document_id="doc-demo",
            document_title="USUR",
            status="partial_llm",
            tickets_created=34,
            sections_created=1,
            warnings=["LLM structuring fallback: timeout"],
            used_llm_assist=False,
            llm_done_tickets=29,
            llm_pending_tickets=0,
            llm_fallback_tickets=5,
            llm_failed_tickets=0,
            resume_available=True,
        )
    )

    assert import_view.summary_status.text() == "Импорт сохранён, но LLM-хвост не добит"
    assert "резервный режим 5" in import_view.summary_chip.text()
    assert not import_view.resume_button.isHidden()
    assert "доделать только хвост" in import_view.handoff_body.text().lower()
    window.close()
    window.facade.connection.close()


def test_import_view_shows_real_progress_state(tmp_path: Path) -> None:
    window, _ = _build_window(tmp_path)
    import_view = window.views["import"]

    import_view.set_import_pending("demo.docx")
    import_view.set_import_progress(58, "Генерация упражнений", "Готовим упражнения для билета 7 из 12")

    assert import_view.summary_status.text() == "Идёт импорт документа"
    assert import_view.summary_chip.text() == "58%"
    assert import_view.progress_stage_label.text() == "Генерация упражнений"
    assert not import_view.progress_bar.isHidden()
    assert not import_view.progress_meta_label.isHidden()
    assert "Осталось примерно" in import_view.progress_meta_label.text() or "Оценка оставшегося времени" in import_view.progress_meta_label.text()
    window.close()
    window.facade.connection.close()
