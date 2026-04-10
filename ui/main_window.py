from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from app.paths import get_readme_path
from infrastructure.ollama.service import OllamaDiagnostics
from ui.components.sidebar import Sidebar
from ui.components.title_bar import AppTitleBar
from ui.components.topbar import TopBar
from ui.theme import DARK, LIGHT, set_app_theme
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
        self.setWindowTitle("Тренажёр билетов к вузовским экзаменам")
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

        self.title_bar = AppTitleBar(self)
        root.addWidget(self.title_bar)

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
            "settings": SettingsView(self.palette_colors["shadow"], self.facade.settings, self.facade.workspace_root),
        }
        for key in self.views:
            page = self.views[key] if getattr(self.views[key], "self_scrolling", False) else self._wrap_view(self.views[key])
            self.stack_pages[key] = page
            self.stack.addWidget(page)

        self.views["library"].import_requested.connect(self.open_import_dialog)
        self.views["library"].refresh_requested.connect(self.refresh_all_views)
        self.views["library"].training_mode_selected.connect(self.open_training_mode)
        self.views["library"].ollama_settings_requested.connect(lambda: self.open_settings_section("ollama"))
        self.views["library"].recheck_requested.connect(self.refresh_sidebar_ollama_status)
        self.views["library"].readme_requested.connect(self.open_readme)
        self.views["library"].dlc_requested.connect(self.show_dlc_teaser)
        self.views["import"].import_requested.connect(self.open_import_dialog)
        self.views["import"].open_library_requested.connect(lambda: self.switch_view("library"))
        self.views["import"].open_training_requested.connect(lambda: self.switch_view("training"))
        self.views["import"].open_statistics_requested.connect(lambda: self.switch_view("statistics"))
        self.views["training"].evaluate_requested.connect(self.handle_training_evaluation)
        self.views["settings"].diagnostics_changed.connect(self.apply_ollama_diagnostics)
        self.views["settings"].settings_saved.connect(self.persist_settings)
        self.switch_view("library")
        self.topbar.set_theme_label(self.palette_name)
        self.views["library"].set_dlc_visible(self.facade.settings.show_dlc_teaser)
        if self.facade.settings.auto_check_ollama_on_start:
            self.refresh_sidebar_ollama_status()
        else:
            self._apply_manual_ollama_status()
        self.refresh_all_views()

    def switch_view(self, key: str) -> None:
        if key not in self.views:
            return
        self.current_key = key
        self.sidebar.set_current(key)
        self.stack.setCurrentWidget(self.stack_pages[key])
        self.forward_search(self.topbar.search_input.text())

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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать документ",
            str(self.facade.settings.default_import_dir),
            self._import_filter(),
        )
        if path:
            result = self.facade.import_document(path)
            self.views["import"].set_last_result(result)
            if result.ok:
                self.refresh_all_views()
                self.switch_view("import")
                warnings = "\n".join(f"• {warning}" for warning in result.warnings[:4])
                message = (
                    f"Документ импортирован: {result.document_title}\n"
                    f"Создано билетов: {result.tickets_created}\n"
                    f"Разделов: {result.sections_created}\n"
                    f"LLM assist: {'да' if result.used_llm_assist else 'нет'}"
                )
                if warnings:
                    message = f"{message}\n\nПредупреждения:\n{warnings}"
                QMessageBox.information(self, "Импорт", message)
            else:
                self.switch_view("import")
                QMessageBox.critical(self, "Импорт", result.error or "Не удалось импортировать документ.")

    def toggle_theme(self) -> None:
        self.palette_name = "dark" if self.palette_name == "light" else "light"
        self.palette_colors = set_app_theme(self.app, self.palette_name)
        self.topbar.set_theme_label(self.palette_name)
        settings = self.facade.settings
        settings.theme_name = self.palette_name
        self.facade.save_settings(settings)

    def refresh_sidebar_ollama_status(self) -> None:
        diagnostics = self.facade.inspect_ollama()
        self.apply_ollama_diagnostics(diagnostics)

    def apply_ollama_diagnostics(self, diagnostics: OllamaDiagnostics) -> None:
        self.latest_diagnostics = diagnostics
        available = diagnostics.endpoint_ok and diagnostics.model_ok
        label = "Ollama: подключено" if available else ("Ollama: endpoint OK" if diagnostics.endpoint_ok else "Ollama: недоступно")
        model_suffix = diagnostics.model_name or self.facade.settings.model
        if diagnostics.model_size_label:
            model_suffix = f"{model_suffix} • {diagnostics.model_size_label}"
        self.sidebar.set_ollama_status(
            available=available,
            label_text=label,
            model_text=f"Модель: {model_suffix}",
            url_text=self.facade.settings.base_url,
        )

    def persist_settings(self, settings: OllamaSettings) -> None:
        self.facade.save_settings(settings)
        if settings.theme_name != self.palette_name:
            self.palette_name = settings.theme_name
            self.palette_colors = set_app_theme(self.app, self.palette_name)
            self.topbar.set_theme_label(self.palette_name)
        self.views["library"].set_dlc_visible(settings.show_dlc_teaser)
        if settings.auto_check_ollama_on_start or self.latest_diagnostics is not None:
            self.refresh_sidebar_ollama_status()
        else:
            self._apply_manual_ollama_status()
        self.refresh_all_views()

    def refresh_all_views(self) -> None:
        documents = self.facade.load_documents()
        statistics = self.facade.load_statistics_snapshot()
        subjects = self.facade.load_subjects()
        sections = self.facade.load_sections_overview()
        tickets = self.facade.load_ticket_maps()
        mastery = self.facade.load_mastery_breakdowns()
        weak_areas = self.facade.load_weak_areas()
        training_snapshot = self.facade.load_training_snapshot()
        current_diagnostics = self._display_diagnostics()

        self.views["library"].set_data(documents, statistics)
        self.views["library"].set_startup_status(current_diagnostics, bool(documents))
        self.views["library"].set_dlc_visible(self.facade.settings.show_dlc_teaser)
        self.views["import"].set_documents(documents)
        self.views["subjects"].set_subjects(subjects)
        self.views["sections"].set_sections(sections)
        self.views["tickets"].set_data(tickets, mastery, weak_areas)
        self.views["training"].set_snapshot(training_snapshot)
        self.views["training"].select_mode(self.facade.settings.default_training_mode)
        self.views["statistics"].set_data(statistics, mastery, weak_areas)

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

    def show_dlc_teaser(self) -> None:
        QMessageBox.information(
            self,
            "DLC: Подготовка к защите магистерской",
            "Планируется отдельный модуль для подготовки к защите магистерской.\n\n"
            "В него войдут:\n"
            "• загрузка текста магистерской\n"
            "• разбор структуры доклада\n"
            "• short defense outline\n"
            "• тренировка ответов на вопросы комиссии\n"
            "• режимы «научрук» и «оппонент»\n\n"
            "Этот модуль не входит в текущий релиз.",
        )

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
                error_text="Автопроверка отключена. Откройте Настройки -> Ollama и нажмите «Проверить соединение».",
            )
        diagnostics = self.facade.inspect_ollama()
        self.latest_diagnostics = diagnostics
        return diagnostics

    def _apply_manual_ollama_status(self) -> None:
        self.latest_diagnostics = None
        self.sidebar.set_ollama_status(
            available=False,
            label_text="Ollama: проверка вручную",
            model_text=f"Модель: {self.facade.settings.model}",
            url_text=self.facade.settings.base_url,
            tone="warning",
        )

    def _import_filter(self) -> str:
        if self.facade.settings.preferred_import_format == "pdf":
            return "PDF (*.pdf);;Документы Word (*.docx);;Документы (*.docx *.pdf);;Все файлы (*.*)"
        return "Документы Word (*.docx);;PDF (*.pdf);;Документы (*.docx *.pdf);;Все файлы (*.*)"
