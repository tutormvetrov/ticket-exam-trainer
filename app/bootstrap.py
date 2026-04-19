from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLabel

from application.facade import AppFacade
from application.settings_store import SettingsStore
from app.build_info import get_runtime_build_info
from app.paths import get_workspace_root
from app.runtime_logging import setup_runtime_logging
from infrastructure.db import connect_initialized, get_database_path
from ui.components.splash import BrandedSplash
from ui.main_window import MainWindow
from ui.theme import app_font, set_app_theme


_QLABEL_PLAIN_TEXT_INSTALLED = False
_LOG = logging.getLogger(__name__)


def _install_plain_text_default_for_qlabel() -> None:
    """Default QLabel.textFormat to PlainText across the whole application.

    Rationale: в приложении нет намеренного HTML в setText. Контент приходит
    из БД, импортированных документов и локальной LLM, любой из этих источников
    потенциально может содержать теги. PlainText-дефолт закрывает случайное
    рендеринг HTML/изображений по сети без ручной правки сотен setText-сайтов.
    """
    global _QLABEL_PLAIN_TEXT_INSTALLED
    if _QLABEL_PLAIN_TEXT_INSTALLED:
        return
    original_init = QLabel.__init__

    def _init_with_plain_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original_init(self, *args, **kwargs)
        self.setTextFormat(Qt.TextFormat.PlainText)

    QLabel.__init__ = _init_with_plain_text  # type: ignore[assignment]
    _QLABEL_PLAIN_TEXT_INSTALLED = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", help="Save window screenshot and exit.")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument(
        "--view",
        choices=[
            "library",
            "subjects",
            "sections",
            "tickets",
            "import",
            "training",
            "dialogue",
            "statistics",
            "defense",
            "settings",
        ],
    )
    parser.add_argument("--import-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workspace-root", help=argparse.SUPPRESS)
    parser.add_argument("--document-path", help=argparse.SUPPRESS)
    parser.add_argument("--answer-profile-code", default="standard_ticket", help=argparse.SUPPRESS)
    parser.add_argument("--resume-document-id", help=argparse.SUPPRESS)
    parser.add_argument("--max-resume-passes", type=int, default=8, help=argparse.SUPPRESS)
    return parser.parse_args()


def _should_show_splash(*, screenshot_mode: bool) -> bool:
    if screenshot_mode:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if os.environ.get("TEZIS_DISABLE_SPLASH", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() in {"offscreen", "minimal"}:
        return False
    return True


def _emit_worker_event(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def _run_import_worker(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else get_workspace_root()
    setup_runtime_logging(workspace_root, component="qt-import-worker")
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)
    _LOG.info("Import worker started workspace=%s database=%s", workspace_root, database_path)

    def _report_progress(percent: int, stage: str, detail: str = "") -> None:
        _emit_worker_event("progress", percent=int(percent), stage=stage, detail=detail)

    try:
        if args.resume_document_id:
            result = facade.complete_resume_document_import_with_progress(
                args.resume_document_id,
                progress_callback=_report_progress,
                max_resume_passes=max(1, int(args.max_resume_passes or 1)),
                generation_timeout_seconds=None,
            )
        else:
            if not args.document_path:
                raise RuntimeError("Document path is required for import worker mode.")
            result = facade.complete_import_with_progress(
                Path(args.document_path),
                answer_profile_code=args.answer_profile_code or "standard_ticket",
                progress_callback=_report_progress,
                max_resume_passes=max(0, int(args.max_resume_passes or 0)),
                generation_timeout_seconds=None,
            )
        _emit_worker_event("result", payload=asdict(result))
        return 0 if result.ok else 1
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("Import worker failed")
        _emit_worker_event("error", message=str(exc))
        return 1
    finally:
        connection.close()


def run() -> int:
    args = parse_args()
    if args.import_worker:
        return _run_import_worker(args)
    workspace_root = get_workspace_root()
    setup_runtime_logging(workspace_root, component="qt")
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)
    _LOG.info("Qt startup workspace=%s database=%s", workspace_root, database_path)

    effective_theme = args.theme or facade.settings.theme_name
    effective_view = args.view or facade.settings.startup_view

    _install_plain_text_default_for_qlabel()
    app = QApplication(sys.argv)
    app.setApplicationName("Тренажёр билетов к вузовским экзаменам")
    app.setFont(app_font(facade.settings.font_preset, facade.settings.font_size))
    set_app_theme(app, effective_theme, facade.settings.font_preset, facade.settings.font_size)

    screenshot_mode = bool(args.screenshot)
    splash: BrandedSplash | None = None
    splash_started_at = 0.0
    if _should_show_splash(screenshot_mode=screenshot_mode):
        splash = BrandedSplash(get_runtime_build_info())
        splash.center_on_screen(app.primaryScreen())
        splash.show()
        splash.raise_()
        splash_started_at = time.monotonic()
        app.processEvents()

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
    if splash is not None:
        splash.raise_()

        def _finish_splash() -> None:
            splash.close()
            splash.deleteLater()
            window.raise_()
            window.activateWindow()

        elapsed_ms = int((time.monotonic() - splash_started_at) * 1000)
        QTimer.singleShot(max(0, 360 - elapsed_ms), _finish_splash)

    if screenshot_mode:
        loop = QEventLoop()
        QTimer.singleShot(900, loop.quit)
        loop.exec()
        app.processEvents()
        # Grab the rendered widget directly — работает и в offscreen-режиме, и на
        # настоящем экране, и не рискует захватить чужое окно поверх приложения.
        pixmap = window.grab()
        if pixmap.isNull():
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
        else:
            pixmap.save(args.screenshot)
        sys.stdout.flush()
        sys.stderr.flush()
        # Screenshot mode is a one-shot automation path. Hard exit avoids a native Qt
        # teardown crash in frozen builds after the screenshot has already been written.
        os._exit(0)

    exit_code = app.exec()
    _LOG.info("Qt exit code=%s", exit_code)
    connection.close()
    return exit_code
