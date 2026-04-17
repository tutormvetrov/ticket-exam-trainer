"""Regression test for QPainter warning storms during tab switching."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QElapsedTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path
from ui.components.sidebar import NAV_ITEMS
from ui.main_window import MainWindow
from ui.theme import set_app_theme


pytestmark = pytest.mark.ui

_MARKERS = (
    "A paint device can only be painted by one painter",
    "QWidgetEffectSourcePrivate::pixmap: Painter not active",
    "QPainter::worldTransform: Painter not active",
    "QPainter::setWorldTransform: Painter not active",
    "QPainter::translate: Painter not active",
)


def test_no_painter_warnings_on_tab_switching(tmp_path: Path) -> None:
    captured: list[str] = []

    def handler(mode, context, message) -> None:
        captured.append(str(message))

    previous_handler = qInstallMessageHandler(handler)
    app = QApplication.instance() or QApplication([])
    set_app_theme(app, "light")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = get_database_path(workspace)
    connection = connect_initialized(db_path)
    store = SettingsStore(workspace / "app_data" / "settings.json")
    store.save(
        replace(
            DEFAULT_OLLAMA_SETTINGS,
            auto_check_ollama_on_start=False,
            auto_check_updates_on_start=False,
        )
    )
    facade = AppFacade(workspace, connection, store)
    window = MainWindow(app, facade, "light", suppress_startup_background_tasks=True)

    try:
        window.show()
        app.processEvents()

        nav_keys = [item[0] for item in NAV_ITEMS]
        for _ in range(2):
            for key in nav_keys:
                window.switch_view(key)
                timer = QElapsedTimer()
                timer.start()
                while timer.elapsed() < 120:
                    app.processEvents()

        for marker in _MARKERS:
            matches = [message for message in captured if marker in message]
            assert not matches, (
                f"Qt painter warning {marker!r} captured {len(matches)} times. "
                f"Sample: {matches[:3]}"
            )
    finally:
        window.close()
        app.processEvents()
        connection.close()
        qInstallMessageHandler(previous_handler)
