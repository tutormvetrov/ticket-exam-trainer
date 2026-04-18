from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit

from application.facade import AppFacade
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.ollama.service import OllamaDiagnostics
from ui.main_window import MainWindow
from ui.theme import set_app_theme


def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        set_app_theme(app, "light")
    return app


@dataclass(slots=True)
class AppSession:
    window: MainWindow
    workspace_root: Path

    def process_events(self, timeout: float = 0.12) -> None:
        deadline = time.monotonic() + timeout
        app = qt_app()
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()

    def switch(self, key: str) -> None:
        self.window.switch_view(key)
        self.process_events()

    def close(self) -> None:
        self.window.close()
        self.process_events(0.1)
        self.window.facade.connection.close()

    def reopen(self, *, diagnostics: OllamaDiagnostics | None = None) -> AppSession:
        self.close()
        return build_app_session(self.workspace_root, diagnostics=diagnostics)

    @property
    def library(self) -> LibraryPage:
        return LibraryPage(self)

    @property
    def tickets(self) -> TicketsPage:
        return TicketsPage(self)

    @property
    def training(self) -> TrainingPage:
        return TrainingPage(self)

    @property
    def dialogue(self) -> DialoguePage:
        return DialoguePage(self)


def build_app_session(
    workspace_root: Path,
    *,
    diagnostics: OllamaDiagnostics | None = None,
) -> AppSession:
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    connection = connect_initialized(get_database_path(workspace_root))
    facade = AppFacade(workspace_root, connection, settings_store)
    window = MainWindow(
        qt_app(),
        facade,
        facade.settings.theme_name,
        suppress_startup_background_tasks=True,
    )
    window.resize(1500, 920)
    window.show()
    session = AppSession(window=window, workspace_root=workspace_root)
    if diagnostics is not None:
        window.apply_ollama_diagnostics(diagnostics)
    session.process_events(0.5)
    return session


def make_ollama_diagnostics(available: bool) -> OllamaDiagnostics:
    if available:
        return OllamaDiagnostics(
            endpoint_ok=True,
            model_ok=True,
            endpoint_message="Endpoint: OK",
            model_message="Model available",
            model_name="qwen3:4b",
            available_models=["qwen3:4b"],
            resolved_models_path="D:\\Ollama\\models",
        )
    return OllamaDiagnostics(
        endpoint_ok=False,
        model_ok=False,
        endpoint_message="Endpoint unavailable",
        model_message="Model not checked",
        model_name="qwen3:4b",
        error_text="offline",
        resolved_models_path="D:\\Ollama\\models",
    )


class LibraryPage:
    def __init__(self, session: AppSession) -> None:
        self.session = session

    @property
    def view(self):
        return self.session.window.views["library"]

    def is_empty(self) -> bool:
        return self.view.library_empty_state.isVisible()

    def select_first_document(self) -> str:
        document = self.view.documents[0]
        self.view.document_list.select_document(document.id)
        self.session.process_events()
        return document.id

    def detail_title(self) -> str:
        return self.view.detail_panel.title_label.text()

    def documents_collapsed(self) -> bool:
        return not self.view.document_list.isVisible()

    def open_reader_for_first_ticket(self) -> str:
        document = self.view.detail_panel.current_document or self.view.documents[0]
        ticket_id = document.tickets[0].ticket_id
        self.view.detail_panel.ticket_reader_requested.emit(ticket_id)
        self.session.process_events()
        return ticket_id

    def open_training_for_first_ticket(self) -> str:
        document = self.view.detail_panel.current_document or self.view.documents[0]
        ticket_id = document.tickets[0].ticket_id
        self.view.detail_panel.ticket_training_requested.emit(ticket_id)
        self.session.process_events()
        return ticket_id

    def delete_current_document(self) -> str:
        document = self.view.detail_panel.current_document or self.view.documents[0]
        self.view.detail_panel.delete_document_requested.emit(document.id)
        self.session.process_events()
        return document.id


class TicketsPage:
    def __init__(self, session: AppSession) -> None:
        self.session = session

    @property
    def view(self):
        return self.session.window.views["tickets"]

    def focus_ticket(self, ticket_id: str) -> None:
        self.view.focus_ticket(ticket_id)
        self.session.process_events()

    def current_ticket_id(self) -> str:
        return self.view.current_ticket_id

    def reading_text(self) -> str:
        label = self.view.detail_widget.findChild(QLabel, "tickets-reading-body")
        return "" if label is None else label.text()


class TrainingPage:
    def __init__(self, session: AppSession) -> None:
        self.session = session

    @property
    def view(self):
        return self.session.window.views["training"]

    def select_mode(self, mode_key: str) -> None:
        self.view.select_mode(mode_key)
        self.session.process_events()

    def current_ticket_title(self) -> str:
        return self.view.session_title.text()

    def submit_reading_understood(self) -> None:
        button = self.view.workspace_stack.currentWidget().findChild(QPushButton, "training-reading-understood")
        if button is None:
            raise RuntimeError("Reading submit button not found.")
        button.click()
        self.session.process_events()

    def result_text(self) -> str:
        label = self.view.workspace_stack.currentWidget().findChild(QLabel, "training-mode-result")
        return "" if label is None else label.text()

    def state_exam_editor_count(self) -> int:
        return len(self.view.workspace_stack.currentWidget().findChildren(QTextEdit))

    def submit_state_exam_answer(self, answer_text: str) -> None:
        workspace = self.view.workspace_stack.currentWidget()
        editors = workspace.findChildren(QTextEdit)
        if not editors:
            raise RuntimeError("State exam editors not found.")
        editors[0].setPlainText(answer_text)
        button = workspace.findChild(QPushButton, "training-state-exam-submit")
        if button is None:
            raise RuntimeError("State exam submit button not found.")
        button.click()
        self.session.process_events()


class DialoguePage:
    def __init__(self, session: AppSession) -> None:
        self.session = session

    @property
    def view(self):
        return self.session.window.views["dialogue"]

    def gate_visible(self) -> bool:
        return self.view.gate_card.isVisible()

    def status_text(self) -> str:
        return self.view.status_chip.text()
