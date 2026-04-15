from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from application.defense_ui_data import ModelRecommendation
from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
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


def _build_window(tmp_path: Path) -> tuple[MainWindow, AppFacade]:
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
    facade = AppFacade(workspace_root, connection, settings_store)
    window = MainWindow(_qapp(), facade, "light")
    return window, facade


def test_defense_view_unlocks_and_creates_project(tmp_path: Path, monkeypatch) -> None:
    window, facade = _build_window(tmp_path)
    monkeypatch.setattr(
        type(facade.defense),
        "_build_model_recommendation",
        lambda self: ModelRecommendation(
            model_name="qwen3:8b",
            label="Рекомендуемая модель: qwen3:8b",
            rationale="Локальный тестовый профиль.",
            available=True,
        ),
    )

    window.switch_view("defense")
    view = window.views["defense"]

    assert not view.paywall_card.isHidden()
    code = facade.issue_local_defense_activation_code()
    view.activation_input.setText(code)
    view.activate_button.click()

    assert not view.workspace.isHidden()
    assert view.paywall_card.isHidden()
    assert "установки" in view.install_label.text().lower()

    view.project_title_input.setText("Тестовая защита")
    view.student_input.setText("Студент")
    view.specialty_input.setText("Менеджмент")
    view.supervisor_input.setText("Научрук")
    view.defense_date_input.setText("2026-06-01")
    view.create_button.click()

    snapshot = facade.load_defense_workspace_snapshot()
    assert len(snapshot.projects) == 1
    assert snapshot.projects[0].title == "Тестовая защита"
    assert view.persona_combo.findData("opponent") >= 0
    assert view.timer_combo.findData(420) >= 0
    assert view.gap_filter_combo.findData("weak_evidence") >= 0

    window.close()
    facade.connection.close()
