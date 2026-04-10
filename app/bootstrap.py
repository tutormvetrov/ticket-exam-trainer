from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from application.facade import AppFacade
from application.settings_store import SettingsStore
from app.paths import get_app_root
from infrastructure.db import connect_initialized, get_database_path
from ui.main_window import MainWindow
from ui.theme import app_font, set_app_theme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", help="Save window screenshot and exit.")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument(
        "--view",
        choices=["library", "subjects", "sections", "tickets", "import", "training", "statistics", "settings"],
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    workspace_root = get_app_root()
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)

    effective_theme = args.theme or facade.settings.theme_name
    effective_view = args.view or facade.settings.startup_view

    app = QApplication(sys.argv)
    app.setApplicationName("Тренажёр билетов к вузовским экзаменам")
    app.setFont(app_font())
    set_app_theme(app, effective_theme)

    window = MainWindow(app, facade, effective_theme)
    window.switch_view(effective_view)
    window.show()

    if args.screenshot:
        def capture() -> None:
            window.grab().save(args.screenshot)
            app.quit()

        QTimer.singleShot(900, capture)

    exit_code = app.exec()
    connection.close()
    return exit_code
