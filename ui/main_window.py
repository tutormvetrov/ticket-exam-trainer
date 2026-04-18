from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from application.admin_access import AdminAccessStore
from application.facade import AppFacade
from application.interface_text_store import InterfaceTextStore
from application.settings import OllamaSettings
from application.settings_store import SettingsStore
from application.defense_ui_data import DefenseProcessingResult
from application.update_service import UpdateInfo, UpdateService
from application.ui_data import ImportExecutionResult
from app.meta import APP_WINDOW_TITLE, GITHUB_RELEASES_URL
from app.paths import get_readme_path
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.service import OllamaDiagnostics
from ui.background import FunctionThread, ProgressThread
from ui.admin_password_dialog import AdminPasswordDialog
from ui.components.sidebar import Sidebar
from ui.components.topbar import TopBar
from ui.theme import DARK, LIGHT, set_app_theme
from ui.text_admin import InterfaceTextEditorDialog, apply_text_overrides, set_debug_mode
from ui.views.defense_view import DefenseView
from ui.views.import_view import ImportView
from ui.views.dialogue_view import DialogueView
from ui.views.library_view import LibraryView
from ui.views.sections_view import SectionsView
from ui.views.settings_view import SettingsView
from ui.views.statistics_view import StatisticsView
from ui.views.subjects_view import SubjectsView
from ui.views.tickets_view import TicketsView
from ui.views.training_view import TrainingView


class MainWindow(QMainWindow):
    def __init__(
        self,
        app,
        facade: AppFacade,
        palette_name: str = "light",
        *,
        suppress_startup_background_tasks: bool = False,
    ) -> None:
        super().__init__()
        self.app = app
        self.facade = facade
        self.palette_name = palette_name
        self.suppress_startup_background_tasks = suppress_startup_background_tasks
        self.palette_colors = LIGHT if palette_name == "light" else DARK
        self.latest_diagnostics: OllamaDiagnostics | None = None
        self._diagnostics_thread: FunctionThread | None = None
        self._import_thread: ProgressThread | None = None
        self._defense_thread: ProgressThread | None = None
        self._defense_eval_thread: FunctionThread | None = None
        self._dialogue_thread: FunctionThread | None = None
        self._update_thread: FunctionThread | None = None
        self._is_closing = False
        self.admin_store = AdminAccessStore(self.facade.workspace_root / "app_data" / "admin_access.json")
        self.text_store = InterfaceTextStore(self.facade.workspace_root / "app_data" / "ui_text_overrides.json")
        self.update_service = UpdateService()
        self.admin_state = self.admin_store.load_state()
        self.admin_unlocked = False
        self.text_overrides = self.text_store.load()
        self.latest_update_info = UpdateInfo()
        self._update_prompted = False
        self._manual_update_check = False
        self._pending_training_mode: str | None = None

        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setMinimumSize(1280, 720)
        available = app.primaryScreen().availableGeometry()
        self.resize(
            max(1280, min(1536, available.width() - 48)),
            max(720, min(960, available.height() - 48)),
        )

        shell = QWidget()
        shell.setObjectName("AppShell")
        self.setCentralWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(body, 1)

        self.sidebar = Sidebar(self.palette_colors["shadow"])
        self.sidebar.section_selected.connect(self.switch_view)
        body_layout.addWidget(self.sidebar)

        content = QWidget()
        content.setProperty("role", "surface")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        body_layout.addWidget(content, 1)

        self.topbar = TopBar()
        self.topbar.settings_clicked.connect(lambda: self.open_settings_section("general"))
        content_layout.addWidget(self.topbar)

        self.separator = QWidget()
        self.separator.setFixedHeight(1)
        self.separator.setStyleSheet(f"background: {self.palette_colors['border']};")
        content_layout.addWidget(self.separator)

        self.stack = QStackedWidget()
        # Важно: никакого QGraphicsEffect на stack. Внутри stack живут
        # CardFrame/MetricTile с QGraphicsDropShadowEffect; вложенные
        # QGraphicsEffect'ы в Qt не поддерживаются корректно и приводят
        # к каскаду «QPainter::begin: A paint device can only be painted
        # by one painter at a time» на каждом кадре перехода.
        content_layout.addWidget(self.stack, 1)
        self.stack_pages: dict[str, QWidget] = {}
        self.current_key = "library"

        self.views = {
            "library": LibraryView(self.palette_colors["shadow"]),
            "subjects": SubjectsView(self.palette_colors["shadow"]),
            "sections": SectionsView(self.palette_colors["shadow"]),
            "tickets": TicketsView(self.palette_colors["shadow"]),
            "import": ImportView(self.palette_colors["shadow"]),
            "training": TrainingView(self.palette_colors["shadow"]),
            "dialogue": DialogueView(self.palette_colors["shadow"]),
            "statistics": StatisticsView(self.palette_colors["shadow"]),
            "defense": DefenseView(self.palette_colors["shadow"]),
            "settings": SettingsView(self.palette_colors["shadow"], self.facade.settings, self.facade.workspace_root),
        }
        for key, view in self.views.items():
            page = view if getattr(view, "self_scrolling", False) else self._wrap_view(view)
            self.stack_pages[key] = page
            self.stack.addWidget(page)

        self.views["library"].import_requested.connect(self.open_import_dialog)
        self.views["library"].refresh_requested.connect(self.refresh_all_views)
        self.views["library"].training_mode_selected.connect(self.open_training_mode)
        self.views["library"].ollama_settings_requested.connect(lambda: self.open_settings_section("ollama"))
        self.views["library"].recheck_requested.connect(self.refresh_sidebar_ollama_status)
        self.views["library"].readme_requested.connect(self.open_readme)
        self.views["library"].dlc_requested.connect(self.show_dlc_teaser)
        self.views["library"].document_delete_requested.connect(self.delete_document_from_library)
        self.views["library"].ticket_reader_requested.connect(self.open_ticket_reader)
        self.views["library"].ticket_training_requested.connect(self._open_training_ticket)
        self.views["subjects"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["sections"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["tickets"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["tickets"].dialogue_requested.connect(self.open_dialogue_ticket)
        self.views["tickets"].training_requested.connect(self._open_training_ticket)
        self.views["training"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["training"].import_requested.connect(self.open_import_dialog)
        self.views["statistics"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["dialogue"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["dialogue"].open_settings_requested.connect(lambda: self.open_settings_section("ollama"))
        self.views["dialogue"].recheck_requested.connect(self.refresh_sidebar_ollama_status)
        self.views["dialogue"].session_start_requested.connect(self.start_dialogue_session)
        self.views["dialogue"].session_requested.connect(self.open_dialogue_session)
        self.views["dialogue"].turn_submitted.connect(self.submit_dialogue_turn)
        self.views["defense"].activate_requested.connect(self.activate_defense_dlc)
        self.views["defense"].create_project_requested.connect(self.create_defense_project)
        self.views["defense"].project_selected.connect(self.refresh_defense_view)
        self.views["defense"].import_requested.connect(self.open_defense_import_dialog)
        self.views["defense"].evaluate_requested.connect(self.evaluate_defense_mock)
        self.views["defense"].gap_status_requested.connect(self.update_defense_gap_status)
        self.views["defense"].repair_task_status_requested.connect(self.update_defense_repair_task_status)

        self.views["import"].import_requested.connect(self.open_import_dialog)
        self.views["import"].resume_requested.connect(self.resume_partial_import)
        self.views["import"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["import"].open_training_requested.connect(lambda: self.switch_view("training"))
        self.views["import"].open_statistics_requested.connect(lambda: self.switch_view("statistics"))

        self.views["training"].evaluate_requested.connect(self.handle_training_evaluation)
        self.views["settings"].diagnostics_changed.connect(self.apply_ollama_diagnostics)
        self.views["settings"].settings_saved.connect(self.persist_settings)
        self.views["settings"].admin_setup_requested.connect(self.open_admin_password_dialog)
        self.views["settings"].admin_login_requested.connect(self.handle_admin_login)
        self.views["settings"].admin_logout_requested.connect(self.handle_admin_logout)
        self.views["settings"].admin_editor_requested.connect(self.open_interface_text_editor)
        self.views["settings"].admin_debug_toggled.connect(self.toggle_admin_debug_mode)
        self.views["settings"].update_check_requested.connect(lambda: self.check_for_updates(manual=True))
        self.views["settings"].open_release_requested.connect(self.open_release_page)

        self.switch_view("library")
        self.views["library"].set_dlc_visible(self.facade.settings.show_dlc_teaser)
        self.views["settings"].set_admin_state(self.admin_state, self.admin_unlocked)
        self.views["settings"].set_update_info(self.latest_update_info)
        self.refresh_all_views()

        if self.suppress_startup_background_tasks:
            self._apply_manual_ollama_status()
        elif self.facade.settings.auto_check_ollama_on_start:
            QTimer.singleShot(0, self.refresh_sidebar_ollama_status)
        else:
            self._apply_manual_ollama_status()
        if not self.suppress_startup_background_tasks and self.facade.settings.auto_check_updates_on_start:
            QTimer.singleShot(150, lambda: self.check_for_updates(manual=False))

    def switch_view(self, key: str) -> None:
        if key not in self.views:
            return
        if self.current_key == "settings" and key != "settings":
            settings_view = self.views["settings"]
            if settings_view.has_unsaved_changes():
                answer = QMessageBox.question(
                    self,
                    "Несохранённые изменения",
                    "В настройках есть несохранённые изменения. Сохранить перед выходом?",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save,
                )
                if answer == QMessageBox.StandardButton.Save:
                    settings_view.save_settings()
                elif answer == QMessageBox.StandardButton.Cancel:
                    return
                else:
                    settings_view.reset_form()
        if key == "defense":
            self.refresh_defense_view(self.views["defense"].current_project_id or None)
        if key == "dialogue" and not self.suppress_startup_background_tasks and self.latest_diagnostics is None:
            QTimer.singleShot(0, self.refresh_sidebar_ollama_status)
        self.current_key = key
        self.sidebar.set_current(key)
        self.topbar.set_current_section(key)
        self._show_stack_page(self.stack_pages[key])
        if key in {"tickets", "training"}:
            QTimer.singleShot(0, self._refresh_heavy_views)
        self._apply_interface_text_overrides()

    def open_settings_section(self, section: str) -> None:
        self.switch_view("settings")
        self.views["settings"].switch_section(section)

    def _wrap_view(self, view: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(view)
        return scroll

    def _show_stack_page(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)

    def _import_worker_command(
        self,
        *,
        document_path: Path | None = None,
        answer_profile_code: str = "standard_ticket",
        document_id: str = "",
        max_resume_passes: int = 8,
    ) -> list[str]:
        repo_root = Path(__file__).resolve().parents[1]
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--import-worker"]
        else:
            command = [sys.executable, str(repo_root / "main.py"), "--import-worker"]
        command.extend(
            [
                "--workspace-root",
                str(self.facade.workspace_root),
                "--max-resume-passes",
                str(max(1, max_resume_passes)),
            ]
        )
        if document_path is not None:
            command.extend(
                [
                    "--document-path",
                    str(document_path),
                    "--answer-profile-code",
                    answer_profile_code or "standard_ticket",
                ]
            )
        if document_id:
            command.extend(["--resume-document-id", document_id])
        return command

    def _run_import_worker_subprocess(self, command: list[str], progress_callback) -> ImportExecutionResult:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        result_payload: dict[str, object] | None = None
        worker_errors: list[str] = []
        stdout_noise: list[str] = []
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                stdout_noise.append(line)
                continue
            event_name = str(event.get("event") or "")
            if event_name == "progress":
                progress_callback(
                    int(event.get("percent", 0) or 0),
                    str(event.get("stage") or ""),
                    str(event.get("detail") or ""),
                )
            elif event_name == "result":
                payload = event.get("payload")
                if isinstance(payload, dict):
                    result_payload = payload
            elif event_name == "error":
                message = str(event.get("message") or "").strip()
                if message:
                    worker_errors.append(message)

        stderr_text = process.stderr.read().strip() if process.stderr is not None else ""
        exit_code = process.wait()

        if result_payload is not None:
            return ImportExecutionResult(**result_payload)

        error_parts = worker_errors[:]
        if stderr_text:
            error_parts.append(stderr_text)
        if stdout_noise and not error_parts:
            error_parts.extend(stdout_noise[-3:])
        if not error_parts:
            error_parts.append(f"Import worker exited with code {exit_code}.")
        raise RuntimeError(error_parts[-1])

    def open_import_dialog(self) -> None:
        if self._import_thread is not None and self._import_thread.isRunning():
            self.switch_view("import")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать документ",
            str(self.facade.settings.default_import_dir),
            self._import_filter(),
        )
        if not path:
            return

        document_path = Path(path)
        if document_path.suffix.lower() not in {".docx", ".pdf"}:
            self.switch_view("import")
            error_text = f"Unsupported document format: {document_path.suffix}"
            self.views["import"].set_last_result(ImportExecutionResult(ok=False, error=error_text))
            QMessageBox.critical(self, "Импорт", error_text)
            return

        self.switch_view("import")
        self.views["import"].set_import_pending(document_path.name)
        answer_profile_code = self.views["import"].selected_answer_profile_code()

        self._import_thread = ProgressThread(
            lambda report_progress: self._import_in_background(document_path, answer_profile_code, report_progress)
        )
        self._import_thread.progress_changed.connect(self.views["import"].set_import_progress)
        self._import_thread.succeeded.connect(self._finish_import)
        self._import_thread.failed.connect(self._fail_import)
        self._import_thread.finished.connect(self._clear_import_thread)
        self._import_thread.start()

    def _import_in_background(self, document_path: Path, answer_profile_code: str, progress_callback):
        command = self._import_worker_command(document_path=document_path, answer_profile_code=answer_profile_code)
        return self._run_import_worker_subprocess(command, progress_callback)

    def resume_partial_import(self, document_id: str) -> None:
        if not document_id:
            return
        if self._import_thread is not None and self._import_thread.isRunning():
            self.switch_view("import")
            return

        latest = self.facade.load_latest_import_result()
        remaining = latest.llm_pending_tickets + latest.llm_fallback_tickets + latest.llm_failed_tickets
        self.switch_view("import")
        self.views["import"].set_resume_pending(latest.document_title or "Документ", remaining)

        self._import_thread = ProgressThread(lambda report_progress: self._resume_in_background(document_id, report_progress))
        self._import_thread.progress_changed.connect(self.views["import"].set_import_progress)
        self._import_thread.succeeded.connect(self._finish_import)
        self._import_thread.failed.connect(self._fail_import)
        self._import_thread.finished.connect(self._clear_import_thread)
        self._import_thread.start()

    def _resume_in_background(self, document_id: str, progress_callback):
        command = self._import_worker_command(document_id=document_id)
        return self._run_import_worker_subprocess(command, progress_callback)

    def refresh_defense_view(self, project_id: str | None = None) -> None:
        self.views["defense"].set_snapshot(self.facade.load_defense_workspace_snapshot(project_id))

    def activate_defense_dlc(self, activation_code: str) -> None:
        view = self.views["defense"]
        view.set_activation_pending(True)
        try:
            self.facade.activate_defense_dlc(activation_code)
            self.refresh_defense_view(view.current_project_id or None)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Платный модуль", str(exc))
        finally:
            view.set_activation_pending(False)

    def create_defense_project(self, payload: dict[str, str]) -> None:
        if not payload.get("title"):
            self.views["defense"]._set_create_busy(False)
            QMessageBox.warning(self, "Платный модуль", "Укажите тему работы для проекта защиты.")
            return
        try:
            project = self.facade.create_defense_project(payload)
        except Exception as exc:  # noqa: BLE001
            self.views["defense"]._set_create_busy(False)
            QMessageBox.critical(self, "Платный модуль", str(exc))
            return
        self.views["defense"]._set_create_busy(False)
        self.refresh_defense_view(project.project_id)
        self.switch_view("defense")

    def open_defense_import_dialog(self, project_id: str) -> None:
        if not project_id:
            return
        if self._defense_thread is not None and self._defense_thread.isRunning():
            self.switch_view("defense")
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Импортировать материалы защиты",
            str(self.facade.settings.default_import_dir),
            "Материалы (*.docx *.pdf *.pptx *.txt *.md);;Word (*.docx);;PDF (*.pdf);;PowerPoint (*.pptx);;Текст (*.txt *.md);;Все файлы (*.*)",
        )
        if not paths:
            return

        self.switch_view("defense")
        self.views["defense"].set_processing_pending(self.views["defense"].project_title.text())
        self._defense_thread = ProgressThread(
            lambda report_progress: self._import_defense_in_background(project_id, paths, report_progress)
        )
        self._defense_thread.progress_changed.connect(self.views["defense"].set_processing_progress)
        self._defense_thread.succeeded.connect(self._finish_defense_import)
        self._defense_thread.failed.connect(self._fail_defense_import)
        self._defense_thread.finished.connect(self._clear_defense_thread)
        self._defense_thread.start()

    def _import_defense_in_background(self, project_id: str, paths: list[str], progress_callback):
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.import_defense_materials_with_progress(project_id, paths, progress_callback=progress_callback)
        finally:
            connection.close()

    def _finish_defense_import(self, result) -> None:
        if self._is_closing:
            return
        self.views["defense"].show_processing_result(result)
        self.refresh_defense_view(result.project_id or self.views["defense"].current_project_id)
        self.switch_view("defense")

    def _fail_defense_import(self, error_text: str) -> None:
        if self._is_closing:
            return
        self.views["defense"].show_processing_result(
            DefenseProcessingResult(ok=False, message="", warnings=[], llm_used=False, error=error_text)
        )
        QMessageBox.critical(self, "Платный модуль", error_text)

    def _clear_defense_thread(self) -> None:
        if self._defense_thread is not None:
            self._defense_thread.deleteLater()
        self._defense_thread = None

    def evaluate_defense_mock(self, project_id: str, mode_key: str, persona_kind: str, timer_profile_sec: int, answer_text: str) -> None:
        if self._defense_eval_thread is not None and self._defense_eval_thread.isRunning():
            return
        self.views["defense"].set_evaluation_pending(True)
        self._defense_eval_thread = FunctionThread(
            lambda: self._evaluate_defense_in_background(project_id, mode_key, persona_kind, timer_profile_sec, answer_text)
        )
        self._defense_eval_thread.succeeded.connect(self._finish_defense_evaluation)
        self._defense_eval_thread.failed.connect(self._fail_defense_evaluation)
        self._defense_eval_thread.finished.connect(self._clear_defense_eval_thread)
        self._defense_eval_thread.start()

    def _evaluate_defense_in_background(
        self,
        project_id: str,
        mode_key: str,
        persona_kind: str,
        timer_profile_sec: int,
        answer_text: str,
    ):
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.evaluate_defense_mock_with_context(
                project_id,
                mode_key,
                persona_kind,
                timer_profile_sec,
                answer_text,
            )
        finally:
            connection.close()

    def update_defense_gap_status(self, project_id: str, finding_id: str, status: str) -> None:
        if not project_id or not finding_id:
            return
        try:
            self.facade.update_defense_gap_status(project_id, finding_id, status)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Платный модуль", str(exc))
            return
        self.refresh_defense_view(project_id)

    def update_defense_repair_task_status(self, project_id: str, task_id: str, status: str) -> None:
        if not project_id or not task_id:
            return
        try:
            self.facade.update_defense_repair_task_status(project_id, task_id, status)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Платный модуль", str(exc))
            return
        self.refresh_defense_view(project_id)

    def _finish_defense_evaluation(self, result) -> None:
        if self._is_closing:
            return
        self.views["defense"].set_evaluation_pending(False)
        self.views["defense"].show_evaluation_result(result)
        self.refresh_defense_view(self.views["defense"].current_project_id or None)

    def _fail_defense_evaluation(self, error_text: str) -> None:
        if self._is_closing:
            return
        self.views["defense"].set_evaluation_pending(False)
        QMessageBox.critical(self, "Платный модуль", error_text)

    def _clear_defense_eval_thread(self) -> None:
        if self._defense_eval_thread is not None:
            self._defense_eval_thread.deleteLater()
        self._defense_eval_thread = None

    def _finish_import(self, result) -> None:
        if self._is_closing:
            return
        if not result.ok:
            self.views["import"].set_last_result(result)
            self.switch_view("import")
            QMessageBox.critical(self, "Импорт", result.error or "Не удалось импортировать документ.")
            return

        self.refresh_all_views()
        latest_result = self.facade.load_latest_import_result()
        self.views["import"].set_last_result(latest_result if latest_result.ok else result)
        self.switch_view("import")

    def _fail_import(self, error_text: str) -> None:
        if self._is_closing:
            return
        self.views["import"].set_last_result(ImportExecutionResult(ok=False, error=error_text))
        self.switch_view("import")
        QMessageBox.critical(self, "Импорт", error_text)

    def _clear_import_thread(self) -> None:
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_thread = None

    def refresh_sidebar_ollama_status(self) -> None:
        if self._diagnostics_thread is not None and self._diagnostics_thread.isRunning():
            return

        self.latest_diagnostics = None
        self.sidebar.set_ollama_status(
            available=False,
            label_text="Ollama: идёт проверка",
            model_text=f"Модель: {self.facade.settings.model}",
            url_text=self.facade.settings.base_url,
            tone="warning",
        )
        self.views["settings"].set_diagnostics_pending("Проверяем сервер и модель")
        self.refresh_all_views()

        self._diagnostics_thread = FunctionThread(self.facade.inspect_ollama)
        self._diagnostics_thread.succeeded.connect(self.apply_ollama_diagnostics)
        self._diagnostics_thread.failed.connect(self._handle_diagnostics_failure)
        self._diagnostics_thread.finished.connect(self._clear_diagnostics_thread)
        self._diagnostics_thread.start()

    def apply_ollama_diagnostics(self, diagnostics: OllamaDiagnostics) -> None:
        if self._is_closing or not self._connection_usable():
            return
        self.latest_diagnostics = diagnostics
        available = diagnostics.endpoint_ok and diagnostics.model_ok
        label = "Ollama: подключено" if available else ("Ollama: сервер отвечает" if diagnostics.endpoint_ok else "Ollama: недоступно")
        model_suffix = diagnostics.model_name or self.facade.settings.model
        if diagnostics.model_size_label:
            model_suffix = f"{model_suffix} • {diagnostics.model_size_label}"
        self.sidebar.set_ollama_status(
            available=available,
            label_text=label,
            model_text=f"Модель: {model_suffix}",
            url_text=self.facade.settings.base_url,
        )
        self.views["settings"].set_diagnostics(diagnostics)
        self.refresh_all_views()

    def persist_settings(self, settings: OllamaSettings) -> None:
        if self._is_closing or not self._connection_usable():
            return
        self.facade.save_settings(settings)
        if settings.theme_name != self.palette_name:
            self.palette_name = settings.theme_name
        self.palette_colors = set_app_theme(
            self.app,
            self.palette_name,
            settings.font_preset,
            settings.font_size,
        )
        self._refresh_theme_widgets()
        self.views["library"].set_dlc_visible(settings.show_dlc_teaser)
        self.views["settings"].set_admin_state(self.admin_state, self.admin_unlocked)
        self.views["settings"].set_update_info(self.latest_update_info)
        self.refresh_all_views()
        if self.current_key == "defense":
            self.refresh_defense_view(self.views["defense"].current_project_id or None)
        if settings.auto_check_ollama_on_start or self.latest_diagnostics is not None:
            self.refresh_sidebar_ollama_status()
        else:
            self._apply_manual_ollama_status()
        if settings.auto_check_updates_on_start:
            self.check_for_updates()

    def delete_document_from_library(self, document_id: str) -> None:
        if not document_id:
            return
        try:
            deleted = self.facade.delete_document(document_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Удаление документа", f"Не удалось удалить документ: {exc}")
            return
        if not deleted:
            QMessageBox.warning(self, "Удаление документа", "Документ уже отсутствует в базе.")
        self.refresh_all_views()

    def refresh_all_views(self) -> None:
        self._refresh_lightweight_views(include_heavy=self.current_key in {"tickets", "training"})

    def _refresh_theme_widgets(self) -> None:
        self.separator.setStyleSheet(f"background: {self.palette_colors['border']};")
        for widget in [self, *self.findChildren(QWidget)]:
            refresh = getattr(widget, "refresh_theme", None)
            if callable(refresh):
                refresh()

    def _refresh_lightweight_views(self, *, include_heavy: bool) -> None:
        if self._is_closing or not self._connection_usable():
            return
        documents = self.facade.load_documents()
        latest_import = self.facade.load_latest_import_result()
        statistics = self.facade.load_statistics_snapshot()
        subjects = self.facade.load_subjects()
        sections = self.facade.load_sections_overview()
        mastery = self.facade.load_mastery_breakdowns()
        weak_areas = self.facade.load_weak_areas()
        state_exam_statistics = self.facade.load_state_exam_statistics()
        current_diagnostics = self._display_diagnostics()

        self.views["library"].set_data(documents, statistics)
        self.views["library"].set_startup_status(current_diagnostics, bool(documents))
        self.views["library"].set_dlc_visible(self.facade.settings.show_dlc_teaser)
        self.views["import"].set_documents(documents)
        if not self.views["import"].is_busy():
            self.views["import"].set_last_result(latest_import)
        self.views["subjects"].set_subjects(subjects)
        self.views["sections"].set_sections(sections)
        self.views["statistics"].set_data(statistics, mastery, weak_areas, state_exam_statistics)
        km_tickets = self.facade.load_ticket_maps()
        readiness = self.facade.load_readiness_score(tickets=km_tickets, mastery=mastery)
        self.sidebar.set_readiness(readiness.percent)
        self.views["library"].set_readiness(readiness)
        self.views["dialogue"].set_snapshot(
            self.facade.load_dialogue_snapshot(tickets=km_tickets, mastery=mastery),
            tickets=km_tickets,
            weak_areas=weak_areas,
            diagnostics=current_diagnostics,
        )
        self.views["settings"].set_admin_state(self.admin_state, self.admin_unlocked)
        self.views["settings"].set_update_info(self.latest_update_info)
        if include_heavy:
            self._refresh_heavy_views(mastery=mastery, weak_areas=weak_areas)

    def _refresh_heavy_views(
        self,
        *,
        mastery: dict[str, TicketMasteryBreakdown] | None = None,
        weak_areas=None,
    ) -> None:
        if self._is_closing or not self._connection_usable():
            return
        resolved_mastery = mastery if mastery is not None else self.facade.load_mastery_breakdowns()
        resolved_weak_areas = weak_areas if weak_areas is not None else self.facade.load_weak_areas()
        tickets = self.facade.load_ticket_maps()
        training_snapshot = self.facade.load_training_snapshot(tickets=tickets)
        self.views["tickets"].set_data(tickets, resolved_mastery, resolved_weak_areas)
        self.views["training"].set_snapshot(training_snapshot)
        target_mode = self._pending_training_mode or self.views["training"].selected_mode or self.facade.settings.default_training_mode
        self.views["training"].select_mode(target_mode)
        self._pending_training_mode = None

    def _open_training_ticket(self, ticket_id: str) -> None:
        self.switch_view("training")
        self.views["training"].select_ticket(ticket_id)

    def open_ticket_reader(self, ticket_id: str) -> None:
        if not ticket_id:
            return
        self.switch_view("tickets")
        self.views["tickets"].focus_ticket(ticket_id)

    def open_training_mode(self, mode_key: str) -> None:
        self._pending_training_mode = mode_key
        self.switch_view("training")
        self.views["training"].select_mode(mode_key)

    def handle_training_evaluation(self, ticket_id: str, mode_key: str, answer_text: str) -> None:
        result = self.facade.evaluate_answer(ticket_id, mode_key, answer_text)
        self.views["training"].show_evaluation(result)
        if result.ok:
            self.refresh_all_views()

    def open_dialogue_ticket(self, ticket_id: str) -> None:
        if not ticket_id:
            return
        self.switch_view("dialogue")
        self.views["dialogue"].select_ticket(ticket_id)

    def open_dialogue_session(self, session_id: str) -> None:
        if not session_id:
            return
        try:
            session = self.facade.load_dialogue_session(session_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Диалог", str(exc))
            return
        self.switch_view("dialogue")
        self.views["dialogue"].show_session(session)

    def start_dialogue_session(self, ticket_id: str, persona_kind: str, seed_focus: str = "") -> None:
        if not ticket_id:
            return
        if self._dialogue_thread is not None and self._dialogue_thread.isRunning():
            return
        self.switch_view("dialogue")
        self.views["dialogue"].set_pending(True, "Создаём dialogue-сессию и готовим первое сообщение.")
        self._dialogue_thread = FunctionThread(
            lambda: self._start_dialogue_in_background(ticket_id, persona_kind, seed_focus or None)
        )
        self._dialogue_thread.succeeded.connect(self._finish_dialogue_action)
        self._dialogue_thread.failed.connect(self._fail_dialogue_action)
        self._dialogue_thread.finished.connect(self._clear_dialogue_thread)
        self._dialogue_thread.start()

    def submit_dialogue_turn(self, session_id: str, user_text: str, expected_last_turn_index: int) -> None:
        if not session_id or not user_text.strip():
            return
        if self._dialogue_thread is not None and self._dialogue_thread.isRunning():
            return
        self.views["dialogue"].set_pending(True, "Отправляем turn в локальный dialogue-оркестратор.")
        self._dialogue_thread = FunctionThread(
            lambda: self._submit_dialogue_in_background(session_id, user_text, expected_last_turn_index)
        )
        self._dialogue_thread.succeeded.connect(self._finish_dialogue_action)
        self._dialogue_thread.failed.connect(self._fail_dialogue_action)
        self._dialogue_thread.finished.connect(self._clear_dialogue_thread)
        self._dialogue_thread.start()

    def _start_dialogue_in_background(self, ticket_id: str, persona_kind: str, seed_focus: str | None):
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.start_dialogue_session(ticket_id, persona_kind, seed_focus=seed_focus)
        finally:
            connection.close()

    def _submit_dialogue_in_background(self, session_id: str, user_text: str, expected_last_turn_index: int):
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.submit_dialogue_turn(
                session_id,
                user_text,
                expected_last_turn_index=expected_last_turn_index,
            )
        finally:
            connection.close()

    def _finish_dialogue_action(self, session_state) -> None:
        if self._is_closing:
            return
        self.refresh_all_views()
        self.switch_view("dialogue")
        self.views["dialogue"].show_session(session_state)

    def _fail_dialogue_action(self, error_text: str) -> None:
        if self._is_closing:
            return
        self.views["dialogue"].set_pending(False)
        QMessageBox.critical(self, "Диалог", error_text)

    def _clear_dialogue_thread(self) -> None:
        if self._dialogue_thread is not None:
            self._dialogue_thread.deleteLater()
        self._dialogue_thread = None

    def open_readme(self) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_readme_path())))

    def open_release_page(self) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(self.latest_update_info.release_url or GITHUB_RELEASES_URL))

    def handle_admin_login(self, password: str) -> None:
        if not self.admin_state.configured:
            QMessageBox.warning(self, "Админ-доступ", "Пароль ещё не задан. Сначала создайте его через кнопку «Настроить пароль».")
            return
        if not self.admin_store.verify_password(password):
            QMessageBox.warning(self, "Админ-доступ", "Пароль не подошёл.")
            self.views["settings"].set_admin_state(self.admin_state, False)
            return
        self.admin_unlocked = True
        self.admin_state = self.admin_store.load_state()
        self.views["settings"].set_admin_state(self.admin_state, True)
        self._apply_interface_text_overrides()
        if self.admin_state.debug_mode:
            set_debug_mode(self, True)
        QMessageBox.information(self, "Админ-доступ", "Режим администратора включён.")

    def handle_admin_logout(self) -> None:
        self.admin_unlocked = False
        self.admin_state = self.admin_store.load_state()
        set_debug_mode(self, False)
        self.views["settings"].set_admin_state(self.admin_state, False)

    def open_admin_password_dialog(self) -> None:
        dialog = AdminPasswordDialog(self.admin_store, self.facade.workspace_root, self)
        if dialog.exec():
            self.admin_unlocked = False
            self.admin_state = self.admin_store.load_state()
            set_debug_mode(self, False)
            self.views["settings"].set_admin_state(self.admin_state, False)
            QMessageBox.information(self, "Админ-доступ", "Параметры админ-доступа обновлены.")

    def toggle_admin_debug_mode(self, enabled: bool) -> None:
        if not self.admin_unlocked:
            self.views["settings"].set_admin_state(self.admin_state, False)
            return
        self.admin_store.set_debug_mode(enabled)
        self.admin_state = self.admin_store.load_state()
        set_debug_mode(self, enabled)
        self.views["settings"].set_admin_state(self.admin_state, True)
        self._apply_interface_text_overrides()

    def open_interface_text_editor(self) -> None:
        if not self.admin_unlocked:
            QMessageBox.warning(self, "Админ-доступ", "Сначала войдите как администратор.")
            return
        dialog = InterfaceTextEditorDialog(self, self.text_overrides)
        if dialog.exec() != InterfaceTextEditorDialog.DialogCode.Accepted:
            return
        self.text_overrides = dialog.current_overrides()
        self.text_store.save(self.text_overrides)
        self._apply_interface_text_overrides()
        QMessageBox.information(self, "Редактор интерфейса", "Подписи интерфейса обновлены.")

    def _apply_interface_text_overrides(self) -> None:
        apply_text_overrides(self, self.text_overrides)
        set_debug_mode(self, self.admin_unlocked and self.admin_state.debug_mode)

    def check_for_updates(self, manual: bool = True) -> None:
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        self._manual_update_check = manual
        self.views["settings"].set_update_info(self.latest_update_info, pending=True)
        self._update_thread = FunctionThread(self.update_service.check)
        self._update_thread.succeeded.connect(self._finish_update_check)
        self._update_thread.failed.connect(self._fail_update_check)
        self._update_thread.finished.connect(self._clear_update_thread)
        self._update_thread.start()

    def _finish_update_check(self, update_info: UpdateInfo) -> None:
        if self._is_closing:
            return
        self.latest_update_info = update_info
        self.views["settings"].set_update_info(update_info)
        if update_info.error_text:
            if self._manual_update_check:
                QMessageBox.warning(
                    self,
                    "Обновления",
                    f"{update_info.error_text}\n\nСтраница релизов остаётся доступной из раздела «Настройки -> Продвинутые».",
                )
            return
        if update_info.update_available:
            if self._manual_update_check or not self._update_prompted:
                self._update_prompted = True
                answer = QMessageBox.question(
                    self,
                    "Обновления",
                    f"Доступна версия {update_info.latest_version}. Открыть страницу релиза?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.open_release_page()
            return
        if self._manual_update_check:
            QMessageBox.information(self, "Обновления", "Установлена актуальная версия.")

    def _fail_update_check(self, error_text: str) -> None:
        update_info = UpdateInfo(error_text=error_text)
        self.latest_update_info = update_info
        self.views["settings"].set_update_info(update_info)
        if self._manual_update_check:
            QMessageBox.warning(self, "Обновления", error_text)

    def _clear_update_thread(self) -> None:
        if self._update_thread is not None:
            self._update_thread.deleteLater()
        self._update_thread = None

    def show_dlc_teaser(self) -> None:
        self.switch_view("defense")

    def _display_diagnostics(self) -> OllamaDiagnostics:
        if self.latest_diagnostics is not None:
            return self.latest_diagnostics
        if not self.facade.settings.auto_check_ollama_on_start:
            return OllamaDiagnostics(
                endpoint_ok=False,
                model_ok=False,
                endpoint_message="Автопроверка отключена",
                model_message="Статус не проверен",
                model_name=self.facade.settings.model,
                error_text="Автопроверка отключена. Откройте Настройки → Ollama и нажмите «Проверить соединение».",
            )
        return OllamaDiagnostics(
            endpoint_ok=False,
            model_ok=False,
            endpoint_message="Проверка...",
            model_message="Ожидание ответа от локального сервера",
            model_name=self.facade.settings.model,
            error_text="Проверка...",
        )

    def _apply_manual_ollama_status(self) -> None:
        self.latest_diagnostics = None
        self.sidebar.set_ollama_status(
            available=False,
            label_text="Ollama: проверка вручную",
            model_text=f"Модель: {self.facade.settings.model}",
            url_text=self.facade.settings.base_url,
            tone="warning",
        )
        self.views["settings"].set_diagnostics_pending("Автопроверка отключена")
        self.refresh_all_views()

    def _handle_diagnostics_failure(self, error_text: str) -> None:
        diagnostics = OllamaDiagnostics(
            endpoint_ok=False,
            model_ok=False,
            endpoint_message="Сервер недоступен",
            model_message="Модель не проверена",
            model_name=self.facade.settings.model,
            error_text=error_text,
        )
        self.apply_ollama_diagnostics(diagnostics)

    def _clear_diagnostics_thread(self) -> None:
        if self._diagnostics_thread is not None:
            self._diagnostics_thread.deleteLater()
        self._diagnostics_thread = None

    def _connection_usable(self) -> bool:
        try:
            self.facade.connection.execute("SELECT 1")
        except Exception:
            return False
        return True

    def closeEvent(self, event) -> None:  # noqa: N802
        self._is_closing = True
        self._wait_for_thread_shutdown(self._diagnostics_thread)
        if self._diagnostics_thread is not None:
            try:
                self._diagnostics_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._diagnostics_thread.failed.disconnect()
            except Exception:
                pass
        self._wait_for_thread_shutdown(self._import_thread)
        if self._import_thread is not None:
            try:
                self._import_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._import_thread.failed.disconnect()
            except Exception:
                pass
            try:
                self._import_thread.progress_changed.disconnect()
            except Exception:
                pass
        self._wait_for_thread_shutdown(self._defense_thread)
        if self._defense_thread is not None:
            try:
                self._defense_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._defense_thread.failed.disconnect()
            except Exception:
                pass
            try:
                self._defense_thread.progress_changed.disconnect()
            except Exception:
                pass
        self._wait_for_thread_shutdown(self._defense_eval_thread)
        if self._defense_eval_thread is not None:
            try:
                self._defense_eval_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._defense_eval_thread.failed.disconnect()
            except Exception:
                pass
        self._wait_for_thread_shutdown(self._dialogue_thread)
        if self._dialogue_thread is not None:
            try:
                self._dialogue_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._dialogue_thread.failed.disconnect()
            except Exception:
                pass
        self._wait_for_thread_shutdown(self._update_thread)
        if self._update_thread is not None:
            try:
                self._update_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._update_thread.failed.disconnect()
            except Exception:
                pass
            try:
                self._update_thread.finished.disconnect()
            except Exception:
                pass
        super().closeEvent(event)

    @staticmethod
    def _wait_for_thread_shutdown(thread: FunctionThread | ProgressThread | None, timeout_ms: int = 3500) -> None:
        if thread is None or not thread.isRunning():
            return
        thread.wait(timeout_ms)

    def _import_filter(self) -> str:
        if self.facade.settings.preferred_import_format == "pdf":
            return "PDF (*.pdf);;Документы Word (*.docx);;Документы (*.docx *.pdf);;Все файлы (*.*)"
        return "Документы Word (*.docx);;PDF (*.pdf);;Документы (*.docx *.pdf);;Все файлы (*.*)"
