from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from application.facade import AppFacade
from application.settings_store import SettingsStore
from app.paths import get_workspace_root
from infrastructure.db import connect_initialized, get_database_path
from ui.main_window import MainWindow
from ui.theme import app_font, set_app_theme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", help="Save window screenshot and exit.")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument(
        "--view",
        choices=["library", "subjects", "sections", "tickets", "import", "training", "statistics", "defense", "settings"],
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    workspace_root = get_workspace_root()
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)

    effective_theme = args.theme or facade.settings.theme_name
    effective_view = args.view or facade.settings.startup_view

    app = QApplication(sys.argv)
    app.setApplicationName("Тренажёр билетов к вузовским экзаменам")
    app.setFont(app_font(facade.settings.font_preset, facade.settings.font_size))
    set_app_theme(app, effective_theme, facade.settings.font_preset, facade.settings.font_size)

    screenshot_mode = bool(args.screenshot)
    window = MainWindow(
        app,
        facade,
        effective_theme,
        suppress_startup_background_tasks=screenshot_mode,
    )
    if args.width or args.height:
        target_width = max(window.minimumWidth(), args.width or window.width())
        target_height = max(window.minimumHeight(), args.height or window.height())
        window.resize(target_width, target_height)
    window.switch_view(effective_view)
    window.show()

    if screenshot_mode:
        loop = QEventLoop()
        QTimer.singleShot(900, loop.quit)
        loop.exec()
        app.processEvents()
        frame = window.frameGeometry()
        left = max(0, frame.left())
        top = max(0, frame.top())
        right = left + max(1, frame.width())
        bottom = top + max(1, frame.height())
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
            image.save(args.screenshot)
        except Exception:
            screen = window.windowHandle().screen() if window.windowHandle() is not None else app.primaryScreen()
            if screen is None:
                raise RuntimeError("No screen available for screenshot mode.")
            screen.grabWindow(window.winId()).save(args.screenshot)
        sys.stdout.flush()
        sys.stderr.flush()
        # Screenshot mode is a one-shot automation path. Hard exit avoids a native Qt
        # teardown crash in frozen builds after the screenshot has already been written.
        os._exit(0)

    exit_code = app.exec()
    connection.close()
    return exit_code
