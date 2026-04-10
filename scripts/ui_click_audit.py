from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from application.defense_service import DefenseService
from application.defense_ui_data import ModelRecommendation
from application.facade import AppFacade
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.service import OllamaDiagnostics
from scripts.seed_ui_smoke_data import build_docs
from ui.components.settings_widgets import SettingsNavItem
from ui.components.training_modes import TrainingModeCard
from ui.main_window import MainWindow
from ui.theme import set_app_theme


@dataclass(slots=True)
class AuditEvent:
    kind: str
    payload: str


@dataclass(slots=True)
class AuditResult:
    status: str
    screen: str
    area: str
    message: str


class FakeDiagnosticsService:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    def inspect(self, model_name: str) -> OllamaDiagnostics:
        return OllamaDiagnostics(
            endpoint_ok=True,
            model_ok=True,
            endpoint_message="Endpoint отвечает",
            model_message="Модель загружена",
            model_name=model_name or self.model,
            model_size_label="demo",
            checked_at=datetime.now(),
            available_models=[model_name or self.model, self.model],
            latency_ms=420,
            error_text="",
            resolved_models_path="C:/mock-ollama/models",
        )


def fake_defense_recommendation(_self) -> ModelRecommendation:
    return ModelRecommendation(
        model_name="mistral:instruct",
        label="Рекомендуемая модель: mistral:instruct",
        rationale="Локальный тестовый профиль для UI-аудита.",
        available=True,
    )


def fake_defense_llm(_self, _service, _system: str, prompt: str, *, model: str):
    if "extract a defense dossier" in prompt:
        return {
            "claims": [
                {"kind": "relevance", "text": "Актуальность защиты подтверждена материалами проекта.", "confidence": 0.82, "needs_review": False},
                {"kind": "goal", "text": "Цель защиты состоит в ясном объяснении результатов работы.", "confidence": 0.78, "needs_review": False},
                {"kind": "methods", "text": "Методы и база исследования описаны в загруженных материалах.", "confidence": 0.74, "needs_review": False},
                {"kind": "results", "text": "Результаты дают прикладной эффект и могут быть защищены перед комиссией.", "confidence": 0.8, "needs_review": False},
            ],
            "risk_topics": [{"text": "Новизна раскрыта слишком кратко", "confidence": 0.61}],
        }
    if "build a defense speech outline" in prompt:
        return {
            "segments": [
                {"title": "Актуальность", "talking_points": "Кратко объяснить, почему тема важна.", "target_seconds": 60},
                {"title": "Методы", "talking_points": "Показать логику выбора методов.", "target_seconds": 70},
                {"title": "Результаты", "talking_points": "Выделить ключевые выводы и пользу.", "target_seconds": 90},
            ]
        }
    if "create a slide storyboard" in prompt:
        return {
            "slides": [
                {"title": "Тема и актуальность", "purpose": "Открыть доклад", "talking_points": ["Контекст темы"], "evidence_links": ["thesis:1"]},
                {"title": "Результаты", "purpose": "Показать выводы", "talking_points": ["Главный результат"], "evidence_links": ["thesis:2"]},
            ]
        }
    if "generate defense follow-up questions" in prompt:
        return {
            "questions": [
                {"topic": "Новизна", "difficulty": 2, "question_text": "В чём состоит новизна работы?", "risk_tag": "novelty"},
                {"topic": "Методы", "difficulty": 2, "question_text": "Почему выбран именно этот набор методов?", "risk_tag": "methods"},
            ]
        }
    if "score a thesis defense answer" in prompt:
        return {
            "summary": "Mock-защита прошла, но новизну и ограничения нужно раскрывать увереннее.",
            "followups": [
                "Чем ваша новизна отличается от предыдущих подходов?",
                "Какие ограничения работы вы готовы признать сразу?",
            ],
            "scores": {},
            "weak_points": [],
        }
    return None


class UiClickAudit:
    def __init__(self, workspace_root: Path, report_path: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.report_path = report_path
        self.events: list[AuditEvent] = []
        self.results: list[AuditResult] = []
        self.app = QApplication.instance() or QApplication(sys.argv)
        set_app_theme(self.app, "light")

        database_path = get_database_path(workspace_root)
        self.connection = connect_initialized(database_path)
        self.settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
        self.facade = AppFacade(workspace_root, self.connection, self.settings_store)
        settings = self.facade.settings
        settings.auto_check_ollama_on_start = False
        settings.import_llm_assist = False
        settings.show_dlc_teaser = True
        self.facade.save_settings(settings)

        self.sample_paths = build_docs(workspace_root / "sample_data")
        self.defense_notes_path = workspace_root / "sample_data" / "defense_notes.md"
        self.defense_notes_path.write_text(
            "Тезисы для защиты:\n- актуальность темы\n- методы\n- ключевой результат\n- ограничения работы",
            encoding="utf-8",
        )
        for path in self.sample_paths[:2]:
            result = self.facade.import_document(path)
            if not result.ok:
                raise RuntimeError(f"Не удалось подготовить тестовые данные: {path.name}: {result.error}")

        tickets = self.facade.load_ticket_maps()
        for ticket in tickets[:2]:
            atoms = " ".join(atom.text for atom in ticket.atoms[:2])
            self.facade.evaluate_answer(ticket.ticket_id, "active-recall", atoms or ticket.canonical_answer_summary)

        self.window = MainWindow(self.app, self.facade, "light")
        self.window.views["settings"]._build_diagnostics_service = lambda: FakeDiagnosticsService(  # type: ignore[attr-defined]
            self.window.facade.settings.base_url,
            self.window.facade.settings.model,
        )
        self._original_facade_inspect = AppFacade.inspect_ollama
        self._original_defense_recommendation = DefenseService._build_model_recommendation
        self._original_defense_llm = DefenseService._call_llm_json
        AppFacade.inspect_ollama = lambda facade: self._fake_diagnostics()  # type: ignore[assignment]

        self._original_messagebox = (
            QMessageBox.information,
            QMessageBox.warning,
            QMessageBox.critical,
        )
        self._original_open_url = QDesktopServices.openUrl
        self._original_get_open_file_name = QFileDialog.getOpenFileName
        self._original_get_open_file_names = QFileDialog.getOpenFileNames
        self._original_get_existing_directory = QFileDialog.getExistingDirectory

    def run(self) -> int:
        try:
            self._patch_external_calls()
            self.window.show()
            self._pump()
            self._audit_topbar()
            self._audit_sidebar_navigation()
            self._audit_library()
            self._audit_subjects()
            self._audit_sections()
            self._audit_tickets()
            self._audit_import()
            self._audit_training()
            self._audit_statistics()
            self._audit_defense()
            self._audit_settings()
        finally:
            self._restore_external_calls()
            self.window.close()
            self.connection.close()

        self._write_report()
        failures = [item for item in self.results if item.status != "PASS"]
        return 1 if failures else 0

    def _patch_external_calls(self) -> None:
        def fake_messagebox(_parent, title: str, text: str, *args, **kwargs):
            self.events.append(AuditEvent("message", f"{title}: {text.splitlines()[0]}"))
            return QMessageBox.StandardButton.Ok

        def fake_open_url(url: QUrl) -> bool:
            self.events.append(AuditEvent("open-url", url.toString()))
            return True

        sample_import = str(self.sample_paths[2])
        defense_imports = [str(self.sample_paths[0]), str(self.defense_notes_path)]

        def fake_get_open_file_name(*args, **kwargs):
            return sample_import, ""

        def fake_get_open_file_names(*args, **kwargs):
            return defense_imports, ""

        def fake_get_existing_directory(*args, **kwargs):
            return str(self.workspace_root / "sample_data")

        DefenseService._build_model_recommendation = fake_defense_recommendation  # type: ignore[assignment]
        DefenseService._call_llm_json = fake_defense_llm  # type: ignore[assignment]
        QMessageBox.information = fake_messagebox  # type: ignore[assignment]
        QMessageBox.warning = fake_messagebox  # type: ignore[assignment]
        QMessageBox.critical = fake_messagebox  # type: ignore[assignment]
        QDesktopServices.openUrl = fake_open_url  # type: ignore[assignment]
        QFileDialog.getOpenFileName = fake_get_open_file_name  # type: ignore[assignment]
        QFileDialog.getOpenFileNames = fake_get_open_file_names  # type: ignore[assignment]
        QFileDialog.getExistingDirectory = fake_get_existing_directory  # type: ignore[assignment]

        import app.platform as platform_helpers

        self._original_launch_script = platform_helpers.launch_support_script

        def fake_launch_script(path: Path) -> None:
            self.events.append(AuditEvent("launch-script", str(path)))

        platform_helpers.launch_support_script = fake_launch_script  # type: ignore[assignment]

    def _restore_external_calls(self) -> None:
        AppFacade.inspect_ollama = self._original_facade_inspect  # type: ignore[assignment]
        DefenseService._build_model_recommendation = self._original_defense_recommendation  # type: ignore[assignment]
        DefenseService._call_llm_json = self._original_defense_llm  # type: ignore[assignment]
        QMessageBox.information, QMessageBox.warning, QMessageBox.critical = self._original_messagebox
        QDesktopServices.openUrl = self._original_open_url  # type: ignore[assignment]
        QFileDialog.getOpenFileName = self._original_get_open_file_name  # type: ignore[assignment]
        QFileDialog.getOpenFileNames = self._original_get_open_file_names  # type: ignore[assignment]
        QFileDialog.getExistingDirectory = self._original_get_existing_directory  # type: ignore[assignment]

        import app.platform as platform_helpers

        platform_helpers.launch_support_script = self._original_launch_script  # type: ignore[assignment]

    def _fake_diagnostics(self) -> OllamaDiagnostics:
        return FakeDiagnosticsService(self.facade.settings.base_url, self.facade.settings.model).inspect(self.facade.settings.model)

    def _pump(self, delay_ms: int = 40) -> None:
        self.app.processEvents()
        QTest.qWait(delay_ms)
        self.app.processEvents()

    def _wait_for(self, predicate, timeout_seconds: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self._pump(40)
            if predicate():
                return True
        self._pump(40)
        return predicate()

    def _record(self, status: str, screen: str, area: str, message: str) -> None:
        self.results.append(AuditResult(status, screen, area, message))

    def _click_button(self, button: QPushButton, screen: str, area: str) -> None:
        if button is None:
            self._record("FAIL", screen, area, "Кнопка не найдена")
            return
        if not button.isEnabled():
            self._record("FAIL", screen, area, "Кнопка отключена")
            return
        button.click()
        self._pump()

    def _click_widget(self, widget, screen: str, area: str) -> None:
        if widget is None:
            self._record("FAIL", screen, area, "Виджет не найден")
            return
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        self._pump()

    def _find_button(self, view, object_name: str) -> QPushButton | None:
        return view.findChild(QPushButton, object_name)

    def _audit_topbar(self) -> None:
        self.window.switch_view("library")
        self._pump()

        self._click_button(self.window.topbar.settings_button, "topbar", "settings button")
        if self.window.current_key == "settings":
            self._record("PASS", "topbar", "settings button", "Открывает экран настроек")
        else:
            self._record("FAIL", "topbar", "settings button", "Не открыл экран настроек")

        self._click_button(self.window.topbar.ollama_button, "topbar", "ollama button")
        settings_view = self.window.views["settings"]
        if self.window.current_key == "settings" and settings_view.settings_stack.currentIndex() == 3:
            self._record("PASS", "topbar", "ollama button", "Открывает раздел Ollama")
        else:
            self._record("FAIL", "topbar", "ollama button", "Не открыл раздел Ollama")

        initial_theme = self.window.palette_name
        self._click_button(self.window.topbar.theme_button, "topbar", "theme button")
        if self.window.palette_name != initial_theme:
            self._record("PASS", "topbar", "theme button", "Переключает тему")
        else:
            self._record("FAIL", "topbar", "theme button", "Не переключил тему")
        self._click_button(self.window.topbar.theme_button, "topbar", "theme button restore")

        self.window.switch_view("library")
        self.window.topbar.search_input.setText("право")
        self._pump()
        matches = self.window.views["library"].document_list.filtered
        if matches and all("право" in item.title.lower() or "право" in item.subject.lower() for item in matches):
            self._record("PASS", "topbar", "search", "Фильтрация работает на библиотеке")
        else:
            self._record("FAIL", "topbar", "search", "Поиск не отфильтровал библиотеку")
        self.window.topbar.search_input.clear()
        self._pump()

    def _audit_sidebar_navigation(self) -> None:
        for key, button in self.window.sidebar.buttons.items():
            self._click_button(button, "sidebar", key)
            if self.window.current_key == key:
                self._record("PASS", "sidebar", key, "Пункт меню открывает свой экран")
            else:
                self._record("FAIL", "sidebar", key, f"Остался экран {self.window.current_key}")

    def _audit_library(self) -> None:
        self.window.switch_view("library")
        self._pump()
        view = self.window.views["library"]

        document_ids = list(view.document_list.items.keys())
        if len(document_ids) >= 2:
            second = view.document_list.items[document_ids[1]]
            self._click_widget(second, "library", "document selection")
            current = view.detail_panel.current_document.id if view.detail_panel.current_document else ""
            if current == document_ids[1]:
                self._record("PASS", "library", "document selection", "Выбор документа обновляет центральную панель")
            else:
                self._record("FAIL", "library", "document selection", "Центральная панель не обновилась")
        else:
            self._record("FAIL", "library", "document selection", "Недостаточно тестовых документов")

        for index, button in enumerate(view.detail_panel.tab_buttons):
            self._click_button(button, "library", f"detail tab {index}")
            if view.detail_panel.stack.currentIndex() == index:
                self._record("PASS", "library", f"detail tab {index}", "Переключает вкладку документа")
            else:
                self._record("FAIL", "library", f"detail tab {index}", "Вкладка не переключилась")

        self._click_button(view.refresh_button, "library", "refresh")
        self._record("PASS", "library", "refresh", "Кнопка обновления не роняет экран")

        if view.startup_card.isVisible():
            self._click_button(view.startup_primary, "library", "startup primary")
            if self.window.current_key == "settings":
                self._record("PASS", "library", "startup primary", "Переводит в настройки Ollama")
            else:
                self._record("FAIL", "library", "startup primary", "Не открыл настройки Ollama")
            self.window.switch_view("library")
            self._click_button(view.startup_secondary, "library", "startup secondary")
            diagnostics_ready = self._wait_for(lambda: self.window.latest_diagnostics is not None)
            if diagnostics_ready and self.window.latest_diagnostics.endpoint_ok:
                self._record("PASS", "library", "startup secondary", "Повторная проверка обновляет статус Ollama")
            else:
                self._record("FAIL", "library", "startup secondary", "Статус Ollama не обновился")
            event_count = len(self.events)
            self._click_button(view.startup_tertiary, "library", "startup tertiary")
            if len(self.events) > event_count and self.events[-1].kind == "open-url":
                self._record("PASS", "library", "startup tertiary", "Открывает README")
            else:
                self._record("FAIL", "library", "startup tertiary", "README не открылся")

        mode_cards = view.training_panel.findChildren(TrainingModeCard)
        if mode_cards:
            self._click_widget(mode_cards[0], "library", "training mode card")
            training_view = self.window.views["training"]
            if self.window.current_key == "training" and training_view.selected_mode == mode_cards[0].mode.key:
                self._record("PASS", "library", "training mode card", "Карточка режима ведёт в тренировку")
            else:
                self._record("FAIL", "library", "training mode card", "Карточка режима не открыла тренировку")
            self.window.switch_view("library")

        event_count = len(self.events)
        self._click_button(self._find_button(view, "library-dlc-teaser"), "library", "dlc teaser")
        if self.window.current_key == "defense":
            self._record("PASS", "library", "dlc teaser", "Карточка DLC ведёт в отдельный paywalled workspace")
        else:
            self._record("FAIL", "library", "dlc teaser", "Карточка DLC не открыла отдельный workspace")
        self.window.switch_view("library")

        before_count = len(self.facade.load_documents())
        self._click_button(self._find_button(view, "library-import"), "library", "import")
        completed = self._wait_for(lambda: not self.window.views["import"].is_busy(), timeout_seconds=15.0)
        after_count = len(self.facade.load_documents())
        if completed and after_count == before_count + 1 and self.window.views["import"].last_result.ok:
            self._record("PASS", "library", "import", "Импорт из библиотеки завершился и попал в базу")
        else:
            self._record("FAIL", "library", "import", f"Импорт не завершился честно. documents before={before_count} after={after_count}")

    def _audit_subjects(self) -> None:
        self.window.switch_view("subjects")
        self._pump()
        view = self.window.views["subjects"]
        if len(view.filtered) >= 2:
            self._record("PASS", "subjects", "render", "Экран предметов заполняется реальными данными")
        else:
            self._record("FAIL", "subjects", "render", "На экране предметов недостаточно тестовых данных")

    def _audit_sections(self) -> None:
        self.window.switch_view("sections")
        self._pump()
        view = self.window.views["sections"]
        if view.combo.count() > 1:
            view.combo.setCurrentIndex(1)
            self._pump()
            selected_subject = view.combo.currentText()
            valid = all(item.subject == selected_subject for item in view.filtered)
            if valid:
                self._record("PASS", "sections", "filter combo", "Фильтр по предмету работает")
            else:
                self._record("FAIL", "sections", "filter combo", "Фильтр по предмету не применился")
            view.combo.setCurrentIndex(0)
            self._pump()
        else:
            self._record("FAIL", "sections", "filter combo", "Нет второго предмета для проверки фильтра")

    def _audit_tickets(self) -> None:
        self.window.switch_view("tickets")
        self._pump()
        view = self.window.views["tickets"]
        ticket_ids = list(view.list_items.keys())
        if len(ticket_ids) >= 2:
            self._click_widget(view.list_items[ticket_ids[1]], "tickets", "ticket selection")
            if view.current_ticket_id == ticket_ids[1]:
                self._record("PASS", "tickets", "ticket selection", "Выбор билета обновляет карту")
            else:
                self._record("FAIL", "tickets", "ticket selection", "Карта билета не обновилась")
        else:
            self._record("FAIL", "tickets", "ticket selection", "Недостаточно билетов для аудита")

    def _audit_import(self) -> None:
        self.window.switch_view("import")
        self._pump()
        view = self.window.views["import"]

        self._click_button(self._find_button(view, "import-open-library"), "import", "open library")
        if self.window.current_key == "library":
            self._record("PASS", "import", "open library", "Кнопка handoff ведёт в библиотеку")
        else:
            self._record("FAIL", "import", "open library", "Не открыла библиотеку")

        self.window.switch_view("import")
        self._click_button(self._find_button(view, "import-open-training"), "import", "open training")
        if self.window.current_key == "training":
            self._record("PASS", "import", "open training", "Кнопка handoff ведёт в тренировку")
        else:
            self._record("FAIL", "import", "open training", "Не открыла тренировку")

        self.window.switch_view("import")
        self._click_button(self._find_button(view, "import-open-statistics"), "import", "open statistics")
        if self.window.current_key == "statistics":
            self._record("PASS", "import", "open statistics", "Кнопка handoff ведёт в статистику")
        else:
            self._record("FAIL", "import", "open statistics", "Не открыла статистику")

    def _audit_training(self) -> None:
        self.window.switch_view("training")
        self._pump()
        view = self.window.views["training"]
        queue_ids = list(view.queue_buttons.keys())
        if len(queue_ids) >= 2:
            self._click_widget(view.queue_buttons[queue_ids[1]], "training", "queue selection")
            if view.selected_ticket_id == queue_ids[1]:
                self._record("PASS", "training", "queue selection", "Выбор карточки меняет активный билет")
            else:
                self._record("FAIL", "training", "queue selection", "Активный билет не сменился")
        else:
            self._record("FAIL", "training", "queue selection", "Недостаточно элементов adaptive queue")

        mode_cards = view.modes_panel.findChildren(TrainingModeCard)
        if mode_cards:
            for card in mode_cards[:3]:
                self._click_widget(card, "training", f"mode {card.mode.key}")
                if view.selected_mode == card.mode.key:
                    self._record("PASS", "training", f"mode {card.mode.key}", "Режим переключается")
                else:
                    self._record("FAIL", "training", f"mode {card.mode.key}", "Режим не переключился")

        before_processed = self.facade.load_statistics_snapshot().processed_tickets
        answer = "Короткий тестовый ответ по билету для smoke-аудита."
        view.answer_input.setPlainText(answer)
        self._click_button(self._find_button(view, "training-check"), "training", "check answer")
        after_processed = self.facade.load_statistics_snapshot().processed_tickets
        if "Оценка:" in view.feedback_body.text() and after_processed >= before_processed:
            self._record("PASS", "training", "check answer", "Оценка ответа обновляет UI и статистику")
        else:
            self._record("FAIL", "training", "check answer", "Проверка ответа не дала результата")

    def _audit_statistics(self) -> None:
        self.window.switch_view("statistics")
        self._pump()
        snapshot = self.facade.load_statistics_snapshot()
        if snapshot.processed_tickets > 0:
            self._record("PASS", "statistics", "snapshot", "Экран статистики показывает реальные попытки")
        else:
            self._record("FAIL", "statistics", "snapshot", "После тренировки статистика не обновилась")

    def _audit_defense(self) -> None:
        self.window.switch_view("defense")
        self._pump()
        view = self.window.views["defense"]

        if view.paywall_card.isVisible() and not view.workspace.isVisible():
            self._record("PASS", "defense", "paywall", "DLC честно закрыт paywall до активации")
        else:
            self._record("FAIL", "defense", "paywall", "Экран DLC не показывает честный paywall")

        activation_code = self.facade.issue_local_defense_activation_code()
        view.activation_input.setText(activation_code)
        self._click_button(view.activate_button, "defense", "activate")
        if view.workspace.isVisible() and not view.paywall_card.isVisible():
            self._record("PASS", "defense", "activate", "Ключ активации открывает DLC-workspace")
        else:
            self._record("FAIL", "defense", "activate", "Активация не открыла DLC-workspace")

        view.project_title_input.setText("Mock защита ГМУ")
        view.student_input.setText("Тестовый студент")
        view.specialty_input.setText("Государственное и муниципальное управление")
        view.supervisor_input.setText("Научный руководитель")
        view.defense_date_input.setText("2026-06-01")
        self._click_button(view.create_button, "defense", "create project")
        snapshot = self.facade.load_defense_workspace_snapshot()
        if snapshot.projects and snapshot.active_project is not None:
            self._record("PASS", "defense", "create project", "Проект защиты создаётся и появляется в workspace")
        else:
            self._record("FAIL", "defense", "create project", "Проект защиты не сохранился")
            return

        self._click_button(view.import_button, "defense", "import materials")
        ready = self._wait_for(lambda: self.window._defense_thread is None and not view.is_processing(), timeout_seconds=20.0)
        snapshot = self.facade.load_defense_workspace_snapshot(view.current_project_id or None)
        if ready and snapshot.active_project and snapshot.active_project.claims and snapshot.active_project.questions:
            self._record("PASS", "defense", "import materials", "Импорт материалов DLC строит dossier и вопросы комиссии")
        else:
            self._record("FAIL", "defense", "import materials", "Импорт материалов DLC не собрал рабочий артефакт")

        view.answer_input.setPlainText("Актуальность темы подтверждена, методы выбраны под задачу, результаты прикладные.")
        self._click_button(view.evaluate_button, "defense", "evaluate mock defense")
        completed = self._wait_for(lambda: self.window._defense_eval_thread is None, timeout_seconds=12.0)
        if completed and ("Слабые места:" in view.evaluation_label.text() or "Следующие вопросы комиссии:" in view.evaluation_label.text()):
            self._record("PASS", "defense", "evaluate mock defense", "Mock-защита даёт разбор и follow-up вопросы")
        else:
            self._record("FAIL", "defense", "evaluate mock defense", "Mock-защита не вернула разбор ответа")

    def _audit_settings(self) -> None:
        self.window.switch_view("settings")
        self._pump()
        view = self.window.views["settings"]
        mapping = {
            "general": 0,
            "documents": 1,
            "training": 2,
            "ollama": 3,
            "data": 4,
            "advanced": 5,
        }

        for key, item in view.nav_panel.items.items():
            self._click_widget(item, "settings", f"nav {key}")
            if view.settings_stack.currentIndex() == mapping[key]:
                self._record("PASS", "settings", f"nav {key}", "Левая навигация секций работает")
            else:
                self._record("FAIL", "settings", f"nav {key}", "Секция настроек не открылась")

        view.switch_section("general")
        self._pump()
        original_toggle = view.auto_check_card.toggle.isChecked()
        self._click_button(view.auto_check_card.toggle, "settings", "general auto-check toggle")
        if view.auto_check_card.toggle.isChecked() != original_toggle:
            self._record("PASS", "settings", "general auto-check toggle", "Переключатель реально меняет состояние")
        else:
            self._record("FAIL", "settings", "general auto-check toggle", "Переключатель не изменил состояние")

        view.switch_section("documents")
        self._pump()
        self._click_button(self._find_button(view, "settings-select-import-dir"), "settings", "documents select dir")
        if Path(view.default_import_dir_input.text()) == self.workspace_root / "sample_data":
            self._record("PASS", "settings", "documents select dir", "Диалог папки применяет путь")
        else:
            self._record("FAIL", "settings", "documents select dir", "Путь импорта не обновился")

        view.switch_section("training")
        self._pump()
        current_mode = view.training_mode_combo.currentData()
        next_index = 0 if view.training_mode_combo.currentIndex() != 0 else min(1, view.training_mode_combo.count() - 1)
        view.training_mode_combo.setCurrentIndex(next_index)
        self._pump()
        if view.training_mode_combo.currentData() != current_mode:
            self._record("PASS", "settings", "training default mode", "Комбо режима тренировки переключается")
        else:
            self._record("FAIL", "settings", "training default mode", "Комбо режима не переключилось")

        view.switch_section("ollama")
        self._pump()
        for object_name, area in (
            ("settings-open-models-folder-inline", "ollama open models inline"),
            ("settings-refresh-models", "ollama refresh models"),
            ("settings-start-ollama", "ollama start server"),
            ("settings-check-connection", "ollama check connection"),
            ("settings-run-setup", "ollama run setup"),
            ("settings-open-models-folder", "ollama open models"),
            ("settings-open-install-help", "ollama install help"),
            ("settings-readme-link", "ollama readme link"),
        ):
            before_events = len(self.events)
            self._click_button(self._find_button(view, object_name), "settings", area)
            if area in {"ollama refresh models", "ollama start server", "ollama check connection"}:
                ready = self._wait_for(lambda: view.status_pill.text() != "Проверка...", timeout_seconds=5.0)
                if ready and "Подключено" in view.status_pill.text():
                    self._record("PASS", "settings", area, "Диагностика завершилась и обновила статус")
                else:
                    self._record("FAIL", "settings", area, "Диагностика не обновила статус")
            elif len(self.events) > before_events:
                self._record("PASS", "settings", area, "Кнопка вызвала ожидаемое действие")
            else:
                self._record("FAIL", "settings", area, "Кнопка не вызвала наблюдаемого действия")

        view.switch_section("data")
        self._pump()
        for object_name, area in (
            ("settings-open-app-folder", "data open app folder"),
            ("settings-open-db-folder", "data open db folder"),
            ("settings-create-backup", "data create backup"),
            ("settings-open-backups", "data open backups"),
        ):
            before_events = len(self.events)
            self._click_button(self._find_button(view, object_name), "settings", area)
            if area == "data create backup":
                backups = list((self.workspace_root / "backups").glob("*.db"))
                if backups:
                    self._record("PASS", "settings", area, "Backup реально создаётся")
                else:
                    self._record("FAIL", "settings", area, "Backup не создался")
            elif len(self.events) > before_events:
                self._record("PASS", "settings", area, "Кнопка вызвала ожидаемое действие")
            else:
                self._record("FAIL", "settings", area, "Кнопка не вызвала наблюдаемого действия")

        view.switch_section("advanced")
        self._pump()
        for object_name, area in (
            ("settings-open-audit", "advanced open audit"),
            ("settings-open-docs", "advanced open docs"),
            ("settings-run-check-script", "advanced run check script"),
            ("settings-open-readme", "advanced open readme"),
        ):
            before_events = len(self.events)
            self._click_button(self._find_button(view, object_name), "settings", area)
            if len(self.events) > before_events:
                self._record("PASS", "settings", area, "Кнопка вызвала ожидаемое действие")
            else:
                self._record("FAIL", "settings", area, "Кнопка не вызвала наблюдаемого действия")

        before_message_count = len([item for item in self.events if item.kind == "message"])
        self._click_button(self._find_button(view, "settings-save"), "settings", "save")
        after_message_count = len([item for item in self.events if item.kind == "message"])
        if after_message_count > before_message_count and self.workspace_root.joinpath("app_data", "settings.json").exists():
            self._record("PASS", "settings", "save", "Сохранение пишет файл настроек и даёт подтверждение")
        else:
            self._record("FAIL", "settings", "save", "Сохранение не оставило подтверждаемого результата")

        self._click_button(self._find_button(view, "settings-reset"), "settings", "reset")
        if view.url_input.text():
            self._record("PASS", "settings", "reset", "Сброс перезаполняет форму")
        else:
            self._record("FAIL", "settings", "reset", "Сброс оставил пустую форму")

    def _write_report(self) -> None:
        lines = [
            "# UI Click Audit",
            "",
            f"- workspace: `{self.workspace_root}`",
            "",
            "## Results",
            "",
        ]
        for item in self.results:
            lines.append(f"- `{item.status}` [{item.screen}] {item.area}: {item.message}")
        lines.extend(["", "## Observed External Events", ""])
        if not self.events:
            lines.append("- none")
        else:
            for event in self.events:
                lines.append(f"- `{event.kind}` {event.payload}")
        report_text = "\n".join(lines) + "\n"
        if self.report_path is not None:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(report_text, encoding="utf-8")
        print(report_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    parser.add_argument("--keep-workspace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = Path(tempfile.mkdtemp(prefix="tezis-ui-audit-"))
    audit = UiClickAudit(workspace_root, args.report)
    try:
        return audit.run()
    finally:
        if not args.keep_workspace:
            shutil.rmtree(workspace_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
