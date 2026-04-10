from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from application.ui_data import StatisticsSnapshot
from domain.models import DocumentData
from infrastructure.ollama.service import OllamaDiagnostics
from ui.components.common import CardFrame, IconBadge
from ui.components.document_detail import DocumentDetailPanel
from ui.components.document_list import DocumentListPanel
from ui.components.stats_panel import StatisticsPanel
from ui.components.training_modes import TrainingModesPanel
from ui.training_catalog import DEFAULT_TRAINING_MODES


class LibraryView(QWidget):
    import_requested = Signal()
    refresh_requested = Signal()
    training_mode_selected = Signal(str)
    ollama_settings_requested = Signal()
    recheck_requested = Signal()
    readme_requested = Signal()
    dlc_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.documents: list[DocumentData] = []
        self.shadow_color = shadow_color
        self._startup_primary_action = lambda: None
        self._startup_secondary_action = lambda: None
        self._startup_tertiary_action = lambda: None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        title = QLabel("Библиотека документов")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)

        import_button = QPushButton("+  Импортировать")
        import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        import_button.setProperty("variant", "primary")
        import_button.clicked.connect(self.import_requested.emit)
        header.addWidget(import_button)

        refresh_button = QPushButton("⟳  Обновить")
        refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_button.setProperty("variant", "secondary")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(refresh_button)
        layout.addLayout(header)

        self.startup_card = CardFrame(role="card", shadow_color=shadow_color)
        startup_layout = QHBoxLayout(self.startup_card)
        startup_layout.setContentsMargins(18, 16, 18, 16)
        startup_layout.setSpacing(14)
        startup_layout.addWidget(IconBadge("AI", "#EEF5FF", "#2E78E6", size=44, radius=14, font_size=12), 0, Qt.AlignmentFlag.AlignTop)

        startup_text = QVBoxLayout()
        startup_text.setContentsMargins(0, 0, 0, 0)
        startup_text.setSpacing(6)
        self.startup_title = QLabel("Состояние локального ИИ")
        self.startup_title.setProperty("role", "section-title")
        startup_text.addWidget(self.startup_title)
        self.startup_body = QLabel("Проверка состояния Ollama и модели.")
        self.startup_body.setProperty("role", "body")
        self.startup_body.setWordWrap(True)
        startup_text.addWidget(self.startup_body)
        self.startup_meta = QLabel("")
        self.startup_meta.setProperty("role", "muted")
        self.startup_meta.setWordWrap(True)
        startup_text.addWidget(self.startup_meta)
        startup_layout.addLayout(startup_text, 1)

        startup_actions = QVBoxLayout()
        startup_actions.setContentsMargins(0, 0, 0, 0)
        startup_actions.setSpacing(8)
        self.startup_primary = QPushButton("Открыть настройки Ollama")
        self.startup_primary.setProperty("variant", "primary")
        self.startup_primary.clicked.connect(self._handle_startup_primary)
        startup_actions.addWidget(self.startup_primary)
        self.startup_secondary = QPushButton("Проверить снова")
        self.startup_secondary.setProperty("variant", "secondary")
        self.startup_secondary.clicked.connect(self._handle_startup_secondary)
        startup_actions.addWidget(self.startup_secondary)
        self.startup_tertiary = QPushButton("Как подготовить среду")
        self.startup_tertiary.setProperty("variant", "outline")
        self.startup_tertiary.clicked.connect(self._handle_startup_tertiary)
        startup_actions.addWidget(self.startup_tertiary)
        startup_layout.addLayout(startup_actions)
        layout.addWidget(self.startup_card)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(16)

        self.document_list = DocumentListPanel([], shadow_color)
        self.document_list.setMinimumWidth(320)
        self.document_list.setMaximumWidth(388)
        content_row.addWidget(self.document_list, 4)

        self.detail_panel = DocumentDetailPanel(shadow_color)
        self.detail_panel.setMinimumWidth(300)
        content_row.addWidget(self.detail_panel, 5)

        self.stats_panel = StatisticsPanel(shadow_color, compact=True)
        self.stats_panel.setMinimumWidth(282)
        self.stats_panel.setMaximumWidth(348)
        content_row.addWidget(self.stats_panel, 3)
        layout.addLayout(content_row, 1)

        self.training_panel = TrainingModesPanel(DEFAULT_TRAINING_MODES, shadow_color)
        self.training_panel.mode_selected.connect(self.training_mode_selected.emit)
        layout.addWidget(self.training_panel)

        self.dlc_card = CardFrame(role="card", shadow_color=shadow_color)
        dlc_layout = QHBoxLayout(self.dlc_card)
        dlc_layout.setContentsMargins(18, 16, 18, 16)
        dlc_layout.setSpacing(14)
        dlc_layout.addWidget(IconBadge("DLC", "#F5EEFF", "#7C3AED", size=44, radius=14, font_size=11), 0, Qt.AlignmentFlag.AlignTop)
        dlc_text = QVBoxLayout()
        dlc_text.setContentsMargins(0, 0, 0, 0)
        dlc_text.setSpacing(6)
        dlc_title_row = QHBoxLayout()
        dlc_title_row.setContentsMargins(0, 0, 0, 0)
        dlc_title_row.setSpacing(10)
        dlc_title = QLabel("DLC: Подготовка к защите магистерской")
        dlc_title.setProperty("role", "section-title")
        dlc_title_row.addWidget(dlc_title)
        dlc_badge = QLabel("Планируется")
        dlc_badge.setProperty("role", "pill")
        dlc_title_row.addWidget(dlc_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        dlc_title_row.addStretch(1)
        dlc_text.addLayout(dlc_title_row)
        dlc_body = QLabel(
            "Будущий модуль поможет разобрать текст магистерской, собрать short defense outline, отрепетировать доклад и вопросы комиссии."
        )
        dlc_body.setProperty("role", "body")
        dlc_body.setWordWrap(True)
        dlc_text.addWidget(dlc_body)
        dlc_meta = QLabel("Не входит в текущий релиз. Сейчас это только честный teaser будущего модуля.")
        dlc_meta.setProperty("role", "muted")
        dlc_meta.setWordWrap(True)
        dlc_text.addWidget(dlc_meta)
        dlc_layout.addLayout(dlc_text, 1)
        dlc_button = QPushButton("Что войдёт")
        dlc_button.setProperty("variant", "secondary")
        dlc_button.clicked.connect(self.dlc_requested.emit)
        dlc_layout.addWidget(dlc_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.dlc_card)

        self.document_list.document_selected.connect(self._select_document)
        self.startup_card.hide()

    def set_data(self, documents: list[DocumentData], snapshot: StatisticsSnapshot) -> None:
        self.documents = documents[:]
        self.document_list.set_documents(documents)
        self.stats_panel.set_snapshot(snapshot)
        if self.document_list.filtered:
            self._select_document(self.document_list.filtered[0].id)
        else:
            self.detail_panel.clear_document()

    def set_startup_status(self, diagnostics: OllamaDiagnostics, has_documents: bool) -> None:
        if diagnostics.endpoint_ok and diagnostics.model_ok and has_documents:
            self.startup_card.hide()
            return

        self.startup_card.show()
        if diagnostics.endpoint_ok and diagnostics.model_ok:
            self.startup_title.setText("Локальный ИИ готов, осталось загрузить билеты")
            self.startup_body.setText(
                "Mistral доступен локально. Следующий шаг: импортируйте один большой DOCX или PDF, чтобы сразу перейти к тренировке."
            )
            self.startup_meta.setText(f"Модель: {diagnostics.model_name or 'mistral:instruct'} • Endpoint: OK")
            self.startup_primary.setText("Импортировать билеты")
            self._startup_primary_action = self.import_requested.emit
            self.startup_secondary.setText("Проверить снова")
            self._startup_secondary_action = self.recheck_requested.emit
            self.startup_tertiary.setText("Настройки Ollama")
            self._startup_tertiary_action = self.ollama_settings_requested.emit
            return

        self.startup_title.setText("Локальный ИИ пока не готов")
        self.startup_body.setText(
            "До полноценной AI-тренировки нужно привести в порядок локальную среду Ollama и модель mistral:instruct."
        )
        self.startup_meta.setText(diagnostics.error_text or diagnostics.model_message or diagnostics.endpoint_message)
        self.startup_primary.setText("Открыть настройки Ollama")
        self._startup_primary_action = self.ollama_settings_requested.emit
        self.startup_secondary.setText("Проверить снова")
        self._startup_secondary_action = self.recheck_requested.emit
        self.startup_tertiary.setText("Как подготовить среду")
        self._startup_tertiary_action = self.readme_requested.emit

    def set_dlc_visible(self, visible: bool) -> None:
        self.dlc_card.setVisible(visible)

    def _select_document(self, document_id: str) -> None:
        for document in self.documents:
            if document.id == document_id:
                self.detail_panel.set_document(document)
                return
        self.detail_panel.clear_document()

    def set_search_text(self, text: str) -> None:
        self.document_list.apply_search(text)
        if self.document_list.filtered:
            self._select_document(self.document_list.filtered[0].id)
        else:
            self.detail_panel.clear_document()

    def _handle_startup_primary(self) -> None:
        self._startup_primary_action()

    def _handle_startup_secondary(self) -> None:
        self._startup_secondary_action()

    def _handle_startup_tertiary(self) -> None:
        self._startup_tertiary_action()
