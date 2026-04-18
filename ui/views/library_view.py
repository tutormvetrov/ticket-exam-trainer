from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from application.ui_data import ReadinessScore, StatisticsSnapshot
from domain.models import DocumentData
from infrastructure.ollama.service import OllamaDiagnostics
from ui.components.common import CardFrame, DonutChart, EmptyStatePanel, IconBadge, file_badge_colors
from ui.components.document_detail import DocumentDetailPanel
from ui.components.document_list import DocumentListPanel
from ui.components.stats_panel import StatisticsPanel
from ui.components.training_modes import TrainingModesPanel
from ui.icons import apply_button_icon
from ui.training_catalog import DEFAULT_TRAINING_MODES


class LibraryView(QWidget):
    import_requested = Signal()
    refresh_requested = Signal()
    training_mode_selected = Signal(str)
    ollama_settings_requested = Signal()
    recheck_requested = Signal()
    readme_requested = Signal()
    dlc_requested = Signal()
    document_delete_requested = Signal(str)
    ticket_reader_requested = Signal(str)
    ticket_training_requested = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.documents: list[DocumentData] = []
        self.shadow_color = shadow_color
        self._startup_primary_action = lambda: None
        self._startup_secondary_action = lambda: None
        self._startup_tertiary_action = lambda: None
        self._documents_collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(16)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(14)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
        controls.addWidget(self.search_input)

        self.documents_toggle = QPushButton("Свернуть список")
        self.documents_toggle.setObjectName("library-toggle-documents")
        self.documents_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.documents_toggle.setProperty("variant", "outline")
        self.documents_toggle.clicked.connect(self._toggle_documents_panel)
        controls.addWidget(self.documents_toggle)
        controls.addStretch(1)

        self.import_button = QPushButton("Импортировать")
        self.import_button.setObjectName("library-import")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self.import_requested.emit)
        controls.addWidget(self.import_button)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("library-refresh")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setProperty("variant", "secondary")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.refresh_button)
        layout.addLayout(controls)

        self.startup_card = CardFrame(role="atelier", shadow_level="md", accent_strip="rust")
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
        self.startup_title = QLabel("Что требует внимания")
        self.startup_title.setProperty("role", "section-title")
        startup_text.addWidget(self.startup_title)

        self.startup_body = QLabel("Здесь появляются только действия, которые мешают перейти к импорту и тренировке.")
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

        self.library_empty_state = EmptyStatePanel(
            "library",
            "Библиотека пока пуста",
            "Импортируйте первый DOCX или PDF, чтобы собрать билеты, открыть чтение и тренировочные режимы.",
            shadow_color=shadow_color,
            role="card",
            primary_action=("Импортировать первый документ", self.import_requested.emit, "primary", "import"),
            secondary_action=("Как подготовить среду", self.readme_requested.emit, "outline", "spark"),
        )
        layout.addWidget(self.library_empty_state)

        self.content_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.content_row.setContentsMargins(0, 0, 0, 0)
        self.content_row.setSpacing(20)

        self.document_list = DocumentListPanel([], shadow_color)
        self.document_list.setMinimumWidth(560)
        self.document_list.setMaximumWidth(760)
        self.content_row.addWidget(self.document_list, 6)

        self.detail_panel = DocumentDetailPanel(shadow_color)
        self.detail_panel.setMinimumWidth(300)
        self.content_row.addWidget(self.detail_panel, 5)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(10)

        self.readiness_chart = DonutChart(0, diameter=70)
        self.readiness_chart.setFixedSize(106, 100)

        self.stats_panel = StatisticsPanel(shadow_color, compact=True)
        self.stats_panel.setMinimumWidth(282)
        self.stats_panel.setMaximumWidth(348)

        right_col.addWidget(self.readiness_chart, 0, Qt.AlignmentFlag.AlignHCenter)
        right_col.addWidget(self.stats_panel)
        right_col.addStretch(1)

        self.stats_column = QWidget()
        self.stats_column.setMinimumWidth(282)
        self.stats_column.setMaximumWidth(348)
        self.stats_column.setLayout(right_col)
        self.content_row.addWidget(self.stats_column, 3)
        self.content_host = QWidget()
        self.content_host.setLayout(self.content_row)
        layout.addWidget(self.content_host, 1)

        self.training_panel = TrainingModesPanel(DEFAULT_TRAINING_MODES, shadow_color)
        self.training_panel.mode_selected.connect(self.training_mode_selected.emit)
        layout.addWidget(self.training_panel)

        self.dlc_card = CardFrame(role="atelier", shadow_level="md", accent_strip="rust")
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
        dlc_title.setProperty("role", "promo-title")
        dlc_title_row.addWidget(dlc_title)
        dlc_badge = QLabel("Доступ по ключу")
        dlc_badge.setProperty("role", "promo-pill")
        dlc_title_row.addWidget(dlc_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        dlc_title_row.addStretch(1)
        dlc_text.addLayout(dlc_title_row)

        dlc_body = QLabel(
            "Платный локальный модуль разбирает текст магистерской, собирает карту защиты, "
            "помогает подготовить доклад и проводит репетицию с вопросами комиссии."
        )
        dlc_body.setProperty("role", "promo-body")
        dlc_body.setWordWrap(True)
        dlc_text.addWidget(dlc_body)

        dlc_meta = QLabel("Доступ открывается по ключу активации. Покупка внутри приложения не поддерживается.")
        dlc_meta.setProperty("role", "promo-meta")
        dlc_meta.setWordWrap(True)
        dlc_text.addWidget(dlc_meta)
        dlc_layout.addLayout(dlc_text, 1)

        self.dlc_button = QPushButton("Открыть модуль")
        self.dlc_button.setObjectName("library-dlc-teaser")
        self.dlc_button.setProperty("variant", "secondary")
        self.dlc_button.clicked.connect(self.dlc_requested.emit)
        dlc_layout.addWidget(self.dlc_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.dlc_card)

        self.document_list.document_selected.connect(self._handle_document_selected)
        self.detail_panel.delete_document_requested.connect(self.document_delete_requested.emit)
        self.detail_panel.ticket_reader_requested.connect(self.ticket_reader_requested.emit)
        self.detail_panel.ticket_training_requested.connect(self.ticket_training_requested.emit)
        self.startup_card.hide()
        self.library_empty_state.hide()
        self._apply_responsive_layout()
        self.refresh_theme()

    def set_data(self, documents: list[DocumentData], snapshot: StatisticsSnapshot) -> None:
        self.documents = documents[:]
        self.document_list.set_documents(documents)
        self.stats_panel.set_snapshot(snapshot)

        has_documents = bool(documents)
        self.import_button.setText("Импортировать" if has_documents else "Импортировать билеты")
        self.refresh_button.setVisible(has_documents)
        self.documents_toggle.setVisible(has_documents)
        self.search_input.setEnabled(has_documents)
        self.content_host.setVisible(has_documents)
        self.library_empty_state.setVisible(not has_documents)
        if not has_documents:
            self._documents_collapsed = False

        if self.document_list.filtered:
            self._select_document(self.document_list.filtered[0].id)
        else:
            self.detail_panel.clear_document()
        self._set_documents_collapsed(self._documents_collapsed if has_documents else False)

    def set_startup_status(self, diagnostics: OllamaDiagnostics, has_documents: bool) -> None:
        if diagnostics.endpoint_ok and diagnostics.model_ok and has_documents:
            self.startup_card.hide()
            return

        self.startup_card.show()
        if diagnostics.endpoint_message == "Проверка...":
            self.startup_title.setText("Фоновая проверка")
            self.startup_body.setText("Проверка Ollama идёт в фоне. Интерфейс уже доступен, ждать блокировки не нужно.")
            self.startup_meta.setText("Текущий статус модели и сервера виден в левой панели.")
            self._configure_startup_actions(
                None,
                ("Открыть настройки Ollama", self.ollama_settings_requested.emit, "secondary"),
                ("Инструкция", self.readme_requested.emit, "outline"),
            )
            return

        if diagnostics.endpoint_ok and diagnostics.model_ok:
            self.startup_title.setText("Следующий шаг")
            self.startup_body.setText(
                "Локальная модель доступна. Следующий шаг: импортируйте один большой DOCX или PDF через кнопку сверху."
            )
            self.startup_meta.setText("После первого импорта откроются билетная карта, тренировка и статистика.")
            self._configure_startup_actions(
                None,
                ("Проверить снова", self.recheck_requested.emit, "secondary"),
                ("Настройки Ollama", self.ollama_settings_requested.emit, "outline"),
            )
            return

        self.startup_title.setText("Что нужно для AI-тренировки")
        self.startup_body.setText(
            "До полноценной AI-тренировки нужно привести в порядок локальную среду Ollama и совместимую локальную модель."
        )
        self.startup_meta.setText(diagnostics.error_text or diagnostics.model_message or diagnostics.endpoint_message)
        self._configure_startup_actions(
            ("Открыть настройки Ollama", self.ollama_settings_requested.emit, "primary"),
            ("Проверить снова", self.recheck_requested.emit, "secondary"),
            ("Как подготовить среду", self.readme_requested.emit, "outline"),
        )

    def set_readiness(self, readiness: ReadinessScore) -> None:
        self.readiness_chart.animate_to(readiness.percent)

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

    def _handle_document_selected(self, document_id: str) -> None:
        self._select_document(document_id)
        if self.documents:
            self._set_documents_collapsed(True)

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

    def _toggle_documents_panel(self) -> None:
        self._set_documents_collapsed(not self._documents_collapsed)

    def _set_documents_collapsed(self, collapsed: bool) -> None:
        has_documents = bool(self.documents)
        self._documents_collapsed = bool(collapsed and has_documents)
        show_documents = has_documents and not self._documents_collapsed
        self.search_input.setVisible(show_documents)
        self.document_list.setVisible(show_documents)
        self.documents_toggle.setText("Показать документы" if self._documents_collapsed else "Свернуть список")
        self.documents_toggle.setProperty("variant", "secondary" if self._documents_collapsed else "outline")
        self.documents_toggle.style().unpolish(self.documents_toggle)
        self.documents_toggle.style().polish(self.documents_toggle)
        self.content_row.setStretchFactor(self.document_list, 0 if self._documents_collapsed else 6)
        self.content_row.setStretchFactor(self.detail_panel, 8 if self._documents_collapsed else 5)
        self.content_row.setStretchFactor(self.stats_column, 3)
        self._apply_responsive_layout()

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
        narrow = self.width() < 1180
        target_direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        if self.content_row.direction() != target_direction:
            self.content_row.setDirection(target_direction)
        if narrow:
            self.document_list.setMinimumWidth(0)
            self.document_list.setMaximumWidth(16777215)
            self.detail_panel.setMinimumWidth(0)
            self.stats_panel.setMinimumWidth(0)
            self.stats_panel.setMaximumWidth(16777215)
            self.stats_column.setMinimumWidth(0)
            self.stats_column.setMaximumWidth(16777215)
        else:
            self.document_list.setMinimumWidth(560)
            self.document_list.setMaximumWidth(760)
            self.detail_panel.setMinimumWidth(640 if self._documents_collapsed else 300)
            self.stats_panel.setMinimumWidth(282)
            self.stats_panel.setMaximumWidth(348)
            self.stats_column.setMinimumWidth(282)
            self.stats_column.setMaximumWidth(348)

    def refresh_theme(self) -> None:
        apply_button_icon(self.import_button, "import")
        apply_button_icon(self.refresh_button, "refresh")
        apply_button_icon(self.documents_toggle, "library")
        apply_button_icon(self.startup_primary, "settings")
        apply_button_icon(self.startup_secondary, "refresh")
        apply_button_icon(self.startup_tertiary, "spark")
        apply_button_icon(self.dlc_button, "defense")
        self.library_empty_state.refresh_theme()
