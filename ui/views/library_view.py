from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from application.ui_data import StatisticsSnapshot
from domain.models import DocumentData
from infrastructure.ollama.service import OllamaDiagnostics
from ui.components.common import CardFrame, IconBadge, file_badge_colors
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
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)

        title = QLabel("Библиотека документов")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)

        self.import_button = QPushButton("+  Импортировать")
        self.import_button.setObjectName("library-import")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self.import_requested.emit)
        header.addWidget(self.import_button)

        self.refresh_button = QPushButton("⟳  Обновить")
        self.refresh_button.setObjectName("library-refresh")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setProperty("variant", "secondary")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.startup_card = CardFrame(role="subtle-card", shadow_color=shadow_color, shadow=False)
        startup_layout = QHBoxLayout(self.startup_card)
        startup_layout.setContentsMargins(16, 14, 16, 14)
        startup_layout.setSpacing(14)
        ai_bg, ai_fg = file_badge_colors("AI")
        startup_layout.addWidget(
            IconBadge("AI", ai_bg, ai_fg, size=42, radius=13, font_size=12),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        startup_text = QVBoxLayout()
        startup_text.setContentsMargins(0, 0, 0, 0)
        startup_text.setSpacing(4)
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
        self.startup_primary.setObjectName("library-startup-primary")
        self.startup_primary.setProperty("variant", "primary")
        self.startup_primary.clicked.connect(self._handle_startup_primary)
        startup_actions.addWidget(self.startup_primary)

        self.startup_secondary = QPushButton("Проверить снова")
        self.startup_secondary.setObjectName("library-startup-secondary")
        self.startup_secondary.setProperty("variant", "secondary")
        self.startup_secondary.clicked.connect(self._handle_startup_secondary)
        startup_actions.addWidget(self.startup_secondary)

        self.startup_tertiary = QPushButton("Как подготовить среду")
        self.startup_tertiary.setObjectName("library-startup-tertiary")
        self.startup_tertiary.setProperty("variant", "outline")
        self.startup_tertiary.clicked.connect(self._handle_startup_tertiary)
        startup_actions.addWidget(self.startup_tertiary)
        startup_layout.addLayout(startup_actions)
        layout.addWidget(self.startup_card)

        self.content_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.content_row.setContentsMargins(0, 0, 0, 0)
        self.content_row.setSpacing(16)

        self.document_list = DocumentListPanel([], shadow_color)
        self.document_list.setMinimumWidth(320)
        self.document_list.setMaximumWidth(388)
        self.content_row.addWidget(self.document_list, 4)

        self.detail_panel = DocumentDetailPanel(shadow_color)
        self.detail_panel.setMinimumWidth(300)
        self.content_row.addWidget(self.detail_panel, 5)

        self.stats_panel = StatisticsPanel(shadow_color, compact=True)
        self.stats_panel.setMinimumWidth(282)
        self.stats_panel.setMaximumWidth(348)
        self.content_row.addWidget(self.stats_panel, 3)
        layout.addLayout(self.content_row, 1)

        self.training_panel = TrainingModesPanel(DEFAULT_TRAINING_MODES, shadow_color)
        self.training_panel.mode_selected.connect(self.training_mode_selected.emit)
        layout.addWidget(self.training_panel)

        self.dlc_card = CardFrame(role="card", shadow_color=shadow_color)
        dlc_layout = QHBoxLayout(self.dlc_card)
        dlc_layout.setContentsMargins(18, 16, 18, 16)
        dlc_layout.setSpacing(14)
        pm_bg, pm_fg = file_badge_colors("PM")
        dlc_layout.addWidget(IconBadge("PM", pm_bg, pm_fg, size=44, radius=14, font_size=11), 0, Qt.AlignmentFlag.AlignTop)

        dlc_text = QVBoxLayout()
        dlc_text.setContentsMargins(0, 0, 0, 0)
        dlc_text.setSpacing(6)
        dlc_title_row = QHBoxLayout()
        dlc_title_row.setContentsMargins(0, 0, 0, 0)
        dlc_title_row.setSpacing(10)
        dlc_title = QLabel("Платный модуль: подготовка к защите")
        dlc_title.setProperty("role", "section-title")
        dlc_title_row.addWidget(dlc_title)
        dlc_badge = QLabel("Paywall")
        dlc_badge.setProperty("role", "pill")
        dlc_title_row.addWidget(dlc_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        dlc_title_row.addStretch(1)
        dlc_text.addLayout(dlc_title_row)

        dlc_body = QLabel(
            "Платный локальный модуль разбирает текст магистерской, собирает defense dossier, "
            "готовит текст защиты и проводит репетицию защиты с вопросами комиссии."
        )
        dlc_body.setProperty("role", "body")
        dlc_body.setWordWrap(True)
        dlc_text.addWidget(dlc_body)

        dlc_meta = QLabel("Доступ открывается по ключу активации. Оплата внутри приложения не встроена.")
        dlc_meta.setProperty("role", "muted")
        dlc_meta.setWordWrap(True)
        dlc_text.addWidget(dlc_meta)
        dlc_layout.addLayout(dlc_text, 1)

        dlc_button = QPushButton("Открыть модуль")
        dlc_button.setObjectName("library-dlc-teaser")
        dlc_button.setProperty("variant", "secondary")
        dlc_button.clicked.connect(self.dlc_requested.emit)
        dlc_layout.addWidget(dlc_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.dlc_card)

        self.document_list.document_selected.connect(self._select_document)
        self.startup_card.hide()
        self._apply_responsive_layout()

    def set_data(self, documents: list[DocumentData], snapshot: StatisticsSnapshot) -> None:
        self.documents = documents[:]
        self.document_list.set_documents(documents)
        self.stats_panel.set_snapshot(snapshot)

        has_documents = bool(documents)
        self.import_button.setText("+  Импортировать" if has_documents else "+  Импортировать билеты")
        self.refresh_button.setVisible(has_documents)

        if self.document_list.filtered:
            self._select_document(self.document_list.filtered[0].id)
        else:
            self.detail_panel.clear_document()

    def set_startup_status(self, diagnostics: OllamaDiagnostics, has_documents: bool) -> None:
        if diagnostics.endpoint_ok and diagnostics.model_ok and has_documents:
            self.startup_card.hide()
            return

        self.startup_card.show()
        if diagnostics.endpoint_message == "Проверка...":
            self.startup_title.setText("Проверяем локальный ИИ")
            self.startup_body.setText("Проверка Ollama идёт в фоне. Интерфейс уже доступен, ждать блокировки не нужно.")
            self.startup_meta.setText(f"Модель по умолчанию: {diagnostics.model_name or 'локальная Qwen-модель'}")
            self._configure_startup_actions(
                None,
                ("Открыть настройки Ollama", self.ollama_settings_requested.emit, "secondary"),
                ("Инструкция", self.readme_requested.emit, "outline"),
            )
            return

        if diagnostics.endpoint_ok and diagnostics.model_ok:
            self.startup_title.setText("Локальный ИИ готов")
            self.startup_body.setText(
                "Локальная модель доступна. Следующий шаг: импортируйте один большой DOCX или PDF через кнопку сверху."
            )
            self.startup_meta.setText(f"Модель: {diagnostics.model_name or 'локальная Qwen-модель'} • Сервер: OK")
            self._configure_startup_actions(
                None,
                ("Проверить снова", self.recheck_requested.emit, "secondary"),
                ("Настройки Ollama", self.ollama_settings_requested.emit, "outline"),
            )
            return

        self.startup_title.setText("Локальный ИИ пока не готов")
        self.startup_body.setText(
            "До полноценной AI-тренировки нужно привести в порядок локальную среду Ollama и совместимую локальную модель."
        )
        self.startup_meta.setText(diagnostics.error_text or diagnostics.model_message or diagnostics.endpoint_message)
        self._configure_startup_actions(
            ("Открыть настройки Ollama", self.ollama_settings_requested.emit, "primary"),
            ("Проверить снова", self.recheck_requested.emit, "secondary"),
            ("Как подготовить среду", self.readme_requested.emit, "outline"),
        )

    def set_dlc_visible(self, visible: bool) -> None:
        self.dlc_card.setVisible(visible)

    def _configure_startup_actions(
        self,
        primary: tuple[str, Callable[[], None], str] | None,
        secondary: tuple[str, Callable[[], None], str] | None,
        tertiary: tuple[str, Callable[[], None], str] | None,
    ) -> None:
        self._apply_button_config(self.startup_primary, primary, "_startup_primary_action")
        self._apply_button_config(self.startup_secondary, secondary, "_startup_secondary_action")
        self._apply_button_config(self.startup_tertiary, tertiary, "_startup_tertiary_action")

    def _apply_button_config(self, button: QPushButton, config, action_attr: str) -> None:
        if config is None:
            button.hide()
            setattr(self, action_attr, lambda: None)
            return
        text, action, variant = config
        button.show()
        button.setText(text)
        button.setProperty("variant", variant)
        button.style().unpolish(button)
        button.style().polish(button)
        setattr(self, action_attr, action)

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

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        narrow = self.width() < 1060
        target_direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        if self.content_row.direction() != target_direction:
            self.content_row.setDirection(target_direction)
        if narrow:
            self.document_list.setMinimumWidth(0)
            self.document_list.setMaximumWidth(16777215)
            self.detail_panel.setMinimumWidth(0)
            self.stats_panel.setMinimumWidth(0)
            self.stats_panel.setMaximumWidth(16777215)
        else:
            self.document_list.setMinimumWidth(320)
            self.document_list.setMaximumWidth(388)
            self.detail_panel.setMinimumWidth(300)
            self.stats_panel.setMinimumWidth(282)
            self.stats_panel.setMaximumWidth(348)
