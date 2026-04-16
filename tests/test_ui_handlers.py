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
from ui.admin_password_dialog import AdminPasswordDialog
from ui.main_window import MainWindow
from ui.text_admin import collect_text_entries
from ui.theme import FONT_PRESETS, build_stylesheet, resolve_font_family, set_app_theme

pytestmark = pytest.mark.ui


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        set_app_theme(app, "light")
    return app


def _build_window(
    tmp_path: Path,
    settings: OllamaSettings | None = None,
    *,
    suppress_startup_background_tasks: bool = False,
) -> tuple[MainWindow, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    effective_settings = replace(
        settings or DEFAULT_OLLAMA_SETTINGS,
        auto_check_ollama_on_start=False,
        auto_check_updates_on_start=False,
    )
    settings_store.save(effective_settings)
    facade = AppFacade(workspace_root, connection, settings_store)
    window = MainWindow(
        _qapp(),
        facade,
        "light",
        suppress_startup_background_tasks=suppress_startup_background_tasks,
    )
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


def test_suppress_startup_background_tasks_skips_auto_threads(tmp_path: Path) -> None:
    settings = replace(
        DEFAULT_OLLAMA_SETTINGS,
        auto_check_ollama_on_start=True,
        auto_check_updates_on_start=True,
    )
    window, _ = _build_window(tmp_path, settings, suppress_startup_background_tasks=True)

    _qapp().processEvents()

    assert window._diagnostics_thread is None
    assert window._update_thread is None
    assert window.views["settings"].status_pill.text() == "Автопроверка отключена"
    window.close()
    window.facade.connection.close()


def test_library_refresh_skips_heavy_ticket_loading(tmp_path: Path, monkeypatch) -> None:
    window, _ = _build_window(tmp_path)
    calls = {"ticket_maps": 0, "training_snapshot": 0}

    def fake_load_ticket_maps():
        calls["ticket_maps"] += 1
        return []

    def fake_load_training_snapshot(*, tickets=None):
        calls["training_snapshot"] += 1
        from application.ui_data import TrainingSnapshot
        return TrainingSnapshot(queue_items=[], tickets=tickets or [])

    monkeypatch.setattr(AppFacade, "load_ticket_maps", lambda self: fake_load_ticket_maps())
    monkeypatch.setattr(AppFacade, "load_training_snapshot", lambda self, tickets=None: fake_load_training_snapshot(tickets=tickets))

    window.switch_view("library")
    window.refresh_all_views()
    _qapp().processEvents()

    assert calls["ticket_maps"] == 1  # knowledge-map view needs ticket data
    assert calls["training_snapshot"] == 0
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
    settings_view.model_combo.setCurrentText("qwen3:8b")
    settings_view.timeout_stepper.set_value(2)
    settings_view.save_settings()
    assert _wait_for(lambda: settings_view.error_label.text().startswith("Ошибка:"), timeout=5.0)

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
        lambda path, answer_profile_code, progress_callback: (
            progress_callback(42, "Построение карты билета", "Билет 5 из 12"),
            ImportExecutionResult(
                ok=True,
                document_id="doc-demo",
                document_title="Demo Import",
                status="structured",
                answer_profile_code="state_exam_public_admin",
                answer_profile_label="Госэкзамен",
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
    assert "Госэкзамен" in import_view.summary_body.text()
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


def test_admin_login_enables_debug_and_text_overrides(tmp_path: Path, monkeypatch) -> None:
    window, _ = _build_window(tmp_path)
    window.admin_store.set_password("секрет-123", "локальная подсказка")
    window.admin_state = window.admin_store.load_state()
    settings_view = window.views["settings"]
    settings_view.set_admin_state(window.admin_state, False)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    window.handle_admin_login("секрет-123")

    assert window.admin_unlocked is True
    assert settings_view.admin_text_button.isEnabled()
    assert settings_view.admin_debug_button.isEnabled()
    assert "открыт" in settings_view.admin_status_label.text().lower()

    window.toggle_admin_debug_mode(True)
    assert window.admin_store.load_state().debug_mode is True
    assert settings_view.admin_debug_button.isChecked() is True

    entries = collect_text_entries(window, {})
    library_button_entry = next(entry for entry in entries if "sidebar-library" in entry.key and entry.source_text == "Библиотека")
    window.text_overrides = {library_button_entry.key: "Материалы"}
    window._apply_interface_text_overrides()
    assert window.sidebar.buttons["library"].text() == "Материалы"

    window.handle_admin_logout()
    assert window.admin_unlocked is False
    assert settings_view.admin_text_button.isEnabled() is False

    window.close()
    window.facade.connection.close()


def test_admin_password_dialog_sets_password(tmp_path: Path) -> None:
    window, workspace_root = _build_window(tmp_path)
    dialog = AdminPasswordDialog(window.admin_store, workspace_root, window)

    dialog.password_input.setText("новый-секрет-123")
    dialog.confirm_input.setText("новый-секрет-123")
    dialog.hint_input.setText("локальная подсказка")
    dialog._save_password()

    state = window.admin_store.load_state()
    assert state.configured is True
    assert state.password_hint == "локальная подсказка"
    assert window.admin_store.verify_password("новый-секрет-123") is True

    dialog.close()
    window.close()
    window.facade.connection.close()


def test_open_admin_password_dialog_refreshes_state(tmp_path: Path, monkeypatch) -> None:
    window, _ = _build_window(tmp_path)

    def fake_exec(self) -> int:
        self.store.set_password("секрет-456", "подсказка")
        return 1

    monkeypatch.setattr(AdminPasswordDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    window.open_admin_password_dialog()

    assert window.admin_state.configured is True
    assert "задан" in window.views["settings"].admin_status_label.text().lower()
    assert window.views["settings"].admin_setup_button.text() == "Изменить или сбросить пароль"

    window.close()
    window.facade.connection.close()


def test_settings_typography_controls_offer_curated_fonts_and_preview(tmp_path: Path) -> None:
    window, _ = _build_window(tmp_path)
    settings_view = window.views["settings"]

    assert settings_view.font_preset_combo.count() >= 4
    available_keys = {settings_view.font_preset_combo.itemData(index) for index in range(settings_view.font_preset_combo.count())}
    assert {"segoe", "bahnschrift", "trebuchet", "verdana"}.issubset(available_keys)

    settings_view._set_combo_value(settings_view.font_preset_combo, "bahnschrift")
    settings_view.font_size_stepper.set_value(14)
    settings_view._refresh_typography_preview()

    assert "Bahnschrift" in settings_view.typography_preview_meta.text()
    assert "размер: 14 pt" in settings_view.typography_preview_meta.text()
    assert settings_view.typography_preview_body.font().family() == resolve_font_family("bahnschrift")
    assert settings_view.typography_preview_button.font().family() == resolve_font_family("bahnschrift")
    assert settings_view.typography_preview_title.font().pointSize() >= settings_view.typography_preview_body.font().pointSize()

    window.close()
    window.facade.connection.close()


def test_font_presets_have_user_facing_descriptions() -> None:
    for preset_key in ("segoe", "bahnschrift", "trebuchet", "verdana", "arial"):
        assert FONT_PRESETS[preset_key]["label"]
        assert FONT_PRESETS[preset_key]["description"]


def test_theme_styles_qmessagebox_for_readable_dialogs() -> None:
    stylesheet = build_stylesheet(
        {
            "app_bg": "#EEF3F8",
            "sidebar_bg": "#F3F7FB",
            "surface_bg": "#F8FBFE",
            "card_bg": "#FFFFFF",
            "card_soft": "#F5F8FC",
            "card_muted": "#F8FAFD",
            "input_bg": "#FBFCFE",
            "primary": "#2E78E6",
            "primary_soft": "#EEF5FF",
            "primary_hover": "#246AD0",
            "success": "#18B06A",
            "success_soft": "#EAF9F1",
            "warning": "#F59A23",
            "warning_soft": "#FFF4E7",
            "danger": "#F26C7F",
            "danger_soft": "#FFF0F2",
            "violet_soft": "#F5EEFF",
            "cyan_soft": "#ECFAFE",
            "text": "#1F2A3B",
            "text_secondary": "#5F6B7A",
            "text_tertiary": "#8E99A8",
            "border": "#E4EAF2",
            "border_strong": "#D4DEEA",
            "shadow": None,
        },
        {
            "family": "Segoe UI",
            "base_point": 11,
            "window_title": 16,
            "brand_title": 24,
            "brand_subtitle": 14,
            "nav_caption": 13,
            "hero": 28,
            "page_subtitle": 15,
            "section_title": 18,
            "card_title": 17,
            "body": 15,
            "muted": 14,
            "pill": 13,
            "status": 14,
            "search": 16,
            "input": 15,
            "button": 15,
            "editor": 15,
            "combo": 15,
        },
    )

    assert "QMessageBox {" in stylesheet
    assert "QMessageBox QLabel {" in stylesheet
    assert "QMessageBox QPushButton {" in stylesheet


def test_refresh_all_views_preserves_training_mode_selection(tmp_path: Path) -> None:
    """Regression: refresh_all_views used to force-reset training mode to settings
    default, which clobbered the evaluation result label after any attempt where
    the user had picked a non-default mode."""
    window, _ = _build_window(tmp_path, suppress_startup_background_tasks=True)
    try:
        training = window.views["training"]
        initial_mode = training.selected_mode
        other_mode = "mini-exam" if initial_mode != "mini-exam" else "reading"

        training.select_mode(other_mode)
        assert training.selected_mode == other_mode

        window.refresh_all_views()

        assert training.selected_mode == other_mode, (
            f"refresh_all_views clobbered training mode from {other_mode!r} to "
            f"{training.selected_mode!r}; это ломает persistence результата после evaluate."
        )
    finally:
        window.close()
        window.facade.connection.close()


def test_refresh_does_not_reapply_interface_text_overrides(tmp_path: Path) -> None:
    """Regression: apply_text_overrides was called inside _refresh_lightweight_views.
    It resets every QLabel/QPushButton without an active override to the text it
    had at first apply, obliterating dynamic labels (training-mode-result, session
    title, timer badge) after every evaluate/import/settings-save cycle.
    Fix: removed the call — overrides still apply at startup and via admin dialog."""
    window, _ = _build_window(tmp_path, suppress_startup_background_tasks=True)
    try:
        call_count = {"n": 0}
        original = window._apply_interface_text_overrides

        def _tracking():
            call_count["n"] += 1
            return original()

        window._apply_interface_text_overrides = _tracking
        try:
            window.refresh_all_views()
        finally:
            window._apply_interface_text_overrides = original

        assert call_count["n"] == 0, (
            "refresh_all_views must not call apply_text_overrides — it clobbers "
            "all dynamic labels (training-mode-result, session_title, timer_badge, …)."
        )
    finally:
        window.close()
        window.facade.connection.close()
