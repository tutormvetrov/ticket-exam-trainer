from __future__ import annotations

from pathlib import Path

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
from ui.components.sidebar import Sidebar
from ui.components.topbar import TopBar
from ui.theme import DARK, LIGHT, set_app_theme
from ui.text_admin import InterfaceTextEditorDialog, apply_text_overrides, set_debug_mode
from ui.views.defense_view import DefenseView
from ui.views.import_view import ImportView
from ui.views.library_view import LibraryView
from ui.views.sections_view import SectionsView
from ui.views.settings_view import SettingsView
from ui.views.statistics_view import StatisticsView
from ui.views.subjects_view import SubjectsView
from ui.views.tickets_view import TicketsView
from ui.views.training_view import TrainingView


class MainWindow(QMainWindow):
    def __init__(self, app, facade: AppFacade, palette_name: str = "light") -> None:
        super().__init__()
        self.app = app
        self.facade = facade
        self.palette_name = palette_name
        self.palette_colors = LIGHT if palette_name == "light" else DARK
        self.latest_diagnostics: OllamaDiagnostics | None = None
        self._diagnostics_thread: FunctionThread | None = None
        self._import_thread: ProgressThread | None = None
        self._defense_thread: ProgressThread | None = None
        self._defense_eval_thread: FunctionThread | None = None
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
        self.topbar.ollama_clicked.connect(lambda: self.open_settings_section("ollama"))
        self.topbar.theme_clicked.connect(self.toggle_theme)
        self.topbar.search_changed.connect(self.forward_search)
        content_layout.addWidget(self.topbar)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #DFE7F0;")
        content_layout.addWidget(separator)

        self.stack = QStackedWidget()
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
        self.views["defense"].activate_requested.connect(self.activate_defense_dlc)
        self.views["defense"].create_project_requested.connect(self.create_defense_project)
        self.views["defense"].project_selected.connect(self.refresh_defense_view)
        self.views["defense"].import_requested.connect(self.open_defense_import_dialog)
        self.views["defense"].evaluate_requested.connect(self.evaluate_defense_mock)

        self.views["import"].import_requested.connect(self.open_import_dialog)
        self.views["import"].resume_requested.connect(self.resume_partial_import)
        self.views["import"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["import"].open_training_requested.connect(lambda: self.switch_view("training"))
        self.views["import"].open_statistics_requested.connect(lambda: self.switch_view("statistics"))

        self.views["training"].evaluate_requested.connect(self.handle_training_evaluation)
        self.views["settings"].diagnostics_changed.connect(self.apply_ollama_diagnostics)
        self.views["settings"].settings_saved.connect(self.persist_settings)
        self.views["settings"].admin_login_requested.connect(self.handle_admin_login)
        self.views["settings"].admin_logout_requested.connect(self.handle_admin_logout)
        self.views["settings"].admin_editor_requested.connect(self.open_interface_text_editor)
        self.views["settings"].admin_debug_toggled.connect(self.toggle_admin_debug_mode)
        self.views["settings"].update_check_requested.connect(lambda: self.check_for_updates(manual=True))
        self.views["settings"].open_release_requested.connect(self.open_release_page)

        self.switch_view("library")
        self.topbar.set_theme_label(self.palette_name)
        self.views["library"].set_dlc_visible(self.facade.settings.show_dlc_teaser)
        self.views["settings"].set_admin_state(self.admin_state, self.admin_unlocked)
        self.views["settings"].set_update_info(self.latest_update_info)
        self.refresh_all_views()

        if self.facade.settings.auto_check_ollama_on_start:
            QTimer.singleShot(0, self.refresh_sidebar_ollama_status)
        else:
            self._apply_manual_ollama_status()
        if self.facade.settings.auto_check_updates_on_start:
            QTimer.singleShot(150, lambda: self.check_for_updates(manual=False))

    def switch_view(self, key: str) -> None:
        if key not in self.views:
            return
        if key == "defense":
            self.refresh_defense_view(self.views["defense"].current_project_id or None)
        self.current_key = key
        self.sidebar.set_current(key)
        self.stack.setCurrentWidget(self.stack_pages[key])
        self.forward_search(self.topbar.search_input.text())
        self._apply_interface_text_overrides()

    def open_settings_section(self, section: str) -> None:
        self.switch_view("settings")
        self.views["settings"].switch_section(section)

    def forward_search(self, text: str) -> None:
        current = self.views.get(self.current_key)
        if hasattr(current, "set_search_text"):
            current.set_search_text(text)

    def _wrap_view(self, view: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(view)
        return scroll

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
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.import_document_with_progress(
                document_path,
                answer_profile_code=answer_profile_code,
                progress_callback=progress_callback,
            )
        finally:
            connection.close()

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
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.resume_document_import_with_progress(document_id, progress_callback=progress_callback)
        finally:
            connection.close()

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
            QMessageBox.warning(self, "Платный модуль", "Укажите тему работы для проекта защиты.")
            return
        try:
            project = self.facade.create_defense_project(payload)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Платный модуль", str(exc))
            return
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

    def evaluate_defense_mock(self, project_id: str, mode_key: str, answer_text: str) -> None:
        if self._defense_eval_thread is not None and self._defense_eval_thread.isRunning():
            return
        self.views["defense"].set_evaluation_pending(True)
        self._defense_eval_thread = FunctionThread(
            lambda: self._evaluate_defense_in_background(project_id, mode_key, answer_text)
        )
        self._defense_eval_thread.succeeded.connect(self._finish_defense_evaluation)
        self._defense_eval_thread.failed.connect(self._fail_defense_evaluation)
        self._defense_eval_thread.finished.connect(self._clear_defense_eval_thread)
        self._defense_eval_thread.start()

    def _evaluate_defense_in_background(self, project_id: str, mode_key: str, answer_text: str):
        database_path = get_database_path(self.facade.workspace_root)
        connection = connect_initialized(database_path)
        settings_store = SettingsStore(self.facade.workspace_root / "app_data" / "settings.json")
        worker_facade = AppFacade(self.facade.workspace_root, connection, settings_store)
        try:
            return worker_facade.evaluate_defense_mock(project_id, mode_key, answer_text)
        finally:
            connection.close()

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

    def toggle_theme(self) -> None:
        self.palette_name = "dark" if self.palette_name == "light" else "light"
        settings = self.facade.settings
        settings.theme_name = self.palette_name
        self.palette_colors = set_app_theme(
            self.app,
            self.palette_name,
            settings.font_preset,
            settings.font_size,
        )
        self.topbar.set_theme_label(self.palette_name)
        self.facade.save_settings(settings)

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
        self.topbar.set_theme_label(self.palette_name)
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

    def refresh_all_views(self) -> None:
        if self._is_closing or not self._connection_usable():
            return
        documents = self.facade.load_documents()
        latest_import = self.facade.load_latest_import_result()
        statistics = self.facade.load_statistics_snapshot()
        subjects = self.facade.load_subjects()
        sections = self.facade.load_sections_overview()
        tickets = self.facade.load_ticket_maps()
        mastery = self.facade.load_mastery_breakdowns()
        weak_areas = self.facade.load_weak_areas()
        training_snapshot = self.facade.load_training_snapshot()
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
        self.views["tickets"].set_data(tickets, mastery, weak_areas)
        self.views["training"].set_snapshot(training_snapshot)
        self.views["training"].select_mode(self.facade.settings.default_training_mode)
        self.views["statistics"].set_data(statistics, mastery, weak_areas, state_exam_statistics)
        self.views["settings"].set_admin_state(self.admin_state, self.admin_unlocked)
        self.views["settings"].set_update_info(self.latest_update_info)
        self._apply_interface_text_overrides()

    def open_training_mode(self, mode_key: str) -> None:
        self.switch_view("training")
        self.views["training"].select_mode(mode_key)

    def handle_training_evaluation(self, ticket_id: str, mode_key: str, answer_text: str) -> None:
        result = self.facade.evaluate_answer(ticket_id, mode_key, answer_text)
        self.views["training"].show_evaluation(result)
        if result.ok:
            self.refresh_all_views()

    def open_readme(self) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_readme_path())))

    def open_release_page(self) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(self.latest_update_info.release_url or GITHUB_RELEASES_URL))

    def handle_admin_login(self, password: str) -> None:
        if not self.admin_state.configured:
            QMessageBox.warning(self, "Админ-доступ", "Пароль ещё не задан. Сначала настройте его через локальную утилиту.")
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
                QMessageBox.warning(self, "Обновления", update_info.error_text)
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
        if self._diagnostics_thread is not None:
            try:
                self._diagnostics_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._diagnostics_thread.failed.disconnect()
            except Exception:
                pass
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
        if self._defense_eval_thread is not None:
            try:
                self._defense_eval_thread.succeeded.disconnect()
            except Exception:
                pass
            try:
                self._defense_eval_thread.failed.disconnect()
            except Exception:
                pass
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
            self._update_thread.wait(3500)
        super().closeEvent(event)

    def _import_filter(self) -> str:
        if self.facade.settings.preferred_import_format == "pdf":
            return "PDF (*.pdf);;Документы Word (*.docx);;Документы (*.docx *.pdf);;Все файлы (*.*)"
        return "Документы Word (*.docx);;PDF (*.pdf);;Документы (*.docx *.pdf);;Все файлы (*.*)"
