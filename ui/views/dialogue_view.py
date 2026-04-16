from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from application.answer_profile_registry import answer_profile_label
from application.ui_data import (
    DialogueSessionState,
    DialogueSessionSummary,
    DialogueSnapshot,
    DialogueTicketItem,
    DialogueTurn,
)
from domain.knowledge import TicketKnowledgeMap
from infrastructure.ollama.service import OllamaDiagnostics
from ui.components.common import CardFrame, ClickableFrame, EmptyStatePanel, IconBadge, file_badge_colors, harden_plain_text
from ui.icons import apply_button_icon
from ui.theme import current_colors


class DialogueTicketRow(ClickableFrame):
    clicked_ticket = Signal(str)

    def __init__(self, ticket: DialogueTicketItem, *, selected: bool = False) -> None:
        super().__init__(role="subtle-card", shadow=False)
        self.ticket = ticket
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(92)
        self.setProperty("selected", selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)
        badge_bg, badge_fg = file_badge_colors("DOCX")
        head.addWidget(IconBadge(str(max(self.ticket.mastery_score, 0) or self.ticket.difficulty or 1), badge_bg, badge_fg, size=34, radius=11, font_size=11))

        self.title_label = QLabel(ticket.title)
        self.title_label.setWordWrap(True)
        head.addWidget(self.title_label, 1)

        self.active_chip = QLabel("ACTIVE")
        self.active_chip.setProperty("role", "pill")
        self.active_chip.setVisible(ticket.has_active_session)
        head.addWidget(self.active_chip, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)

        self.meta_label = QLabel("")
        self.meta_label.setProperty("role", "body")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        self.tail_label = QLabel("")
        self.tail_label.setProperty("role", "muted")
        self.tail_label.setWordWrap(True)
        layout.addWidget(self.tail_label)

        harden_plain_text(self.title_label, self.meta_label, self.tail_label)
        self.refresh_theme()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_ticket.emit(self.ticket.ticket_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = current_colors()
        selected = self.property("selected") is True
        border = colors["primary"] if selected else colors["border"]
        background = colors["primary_soft"] if selected else colors["card_bg"]
        self.setStyleSheet(f"QFrame {{ background: {background}; border: 1px solid {border}; border-radius: 16px; }}")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        self.meta_label.setText(
            f"{self.ticket.section_title} • Сложность: {self.ticket.difficulty} • Готовность: {self.ticket.mastery_score}%"
        )
        self.tail_label.setText(self.ticket.last_session_label or "Сессий ещё не было")


class DialogueSessionRow(ClickableFrame):
    clicked_session = Signal(str)

    def __init__(self, session: DialogueSessionSummary, *, selected: bool = False) -> None:
        super().__init__(role="subtle-card", shadow=False)
        self.session = session
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)
        self.title_label = QLabel(session.ticket_title)
        self.title_label.setWordWrap(True)
        head.addWidget(self.title_label, 1)
        self.score_chip = QLabel("—" if session.score_percent <= 0 else f"{session.score_percent}%")
        self.score_chip.setProperty("role", "pill")
        head.addWidget(self.score_chip, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)

        self.meta_label = QLabel("")
        self.meta_label.setProperty("role", "body")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        self.summary_label = QLabel("")
        self.summary_label.setProperty("role", "muted")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        harden_plain_text(self.title_label, self.meta_label, self.summary_label)
        self.refresh_theme()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_session.emit(self.session.session_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = current_colors()
        selected = self.property("selected") is True
        border = colors["primary"] if selected else colors["border"]
        background = colors["primary_soft"] if selected else colors["card_bg"]
        self.setStyleSheet(f"QFrame {{ background: {background}; border: 1px solid {border}; border-radius: 16px; }}")
        persona = "Examiner" if self.session.persona_kind == "examiner" else "Tutor"
        meta_parts = [persona, self.session.updated_label]
        if self.session.completed_label and self.session.status == "completed":
            meta_parts.append(self.session.completed_label)
        self.meta_label.setText(" • ".join(part for part in meta_parts if part))
        self.summary_label.setText(self.session.verdict or self.session.summary or "Итог появится после завершения сессии.")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")


class DialogueTurnBubble(QWidget):
    def __init__(self, turn: DialogueTurn, *, persona_kind: str) -> None:
        super().__init__()
        self.turn = turn
        self.persona_kind = persona_kind

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        if turn.speaker == "user":
            row.addStretch(1)

        self.card = QFrame()
        self.card.setObjectName("DialogueTurnBubble")
        self.card.setProperty("speaker", turn.speaker)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        self.header_label = QLabel("")
        card_layout.addWidget(self.header_label)

        self.body_label = QLabel(turn.text)
        self.body_label.setWordWrap(True)
        self.body_label.setProperty("role", "body")
        card_layout.addWidget(self.body_label)

        self.focus_label = QLabel(f"Фокус: {turn.weakness_focus}") if turn.weakness_focus else None
        if self.focus_label is not None:
            self.focus_label.setProperty("role", "muted")
            self.focus_label.setWordWrap(True)
            card_layout.addWidget(self.focus_label)
            harden_plain_text(self.body_label, self.focus_label)
        else:
            harden_plain_text(self.body_label)

        row.addWidget(self.card, 0)
        if turn.speaker != "user":
            row.addStretch(1)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = current_colors()
        if self.turn.speaker == "user":
            background = colors["primary_soft"]
            border = colors["primary"]
            header = "Вы"
        else:
            background = colors["card_bg"]
            border = colors["border"]
            header = "Examiner" if self.persona_kind == "examiner" else "Tutor"
        self.card.setMaximumWidth(560)
        self.card.setStyleSheet(
            f"QFrame#DialogueTurnBubble {{ background: {background}; border: 1px solid {border}; border-radius: 18px; }}"
        )
        self.header_label.setText(header)
        self.header_label.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {colors['text_secondary']};")


class DialogueView(QWidget):
    open_library_requested = Signal()
    open_settings_requested = Signal()
    recheck_requested = Signal()
    session_start_requested = Signal(str, str, str)
    session_requested = Signal(str)
    turn_submitted = Signal(str, str, int)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.self_scrolling = True
        self.shadow_color = shadow_color
        self.snapshot = DialogueSnapshot()
        self.ticket_maps: list[TicketKnowledgeMap] = []
        self.ticket_lookup: dict[str, TicketKnowledgeMap] = {}
        self.weak_areas: list[dict[str, str]] = []
        self.diagnostics: OllamaDiagnostics | None = None
        self.current_session: DialogueSessionState | None = None
        self.selected_ticket_id = ""
        self.persona_kind = "tutor"
        self._pending = False
        self._pending_message = ""
        self._pending_turn_text = ""
        self._retry_focus = ""
        self._ticket_rows: dict[str, DialogueTicketRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(4)
        title = QLabel("Диалог")
        title.setProperty("role", "hero")
        titles.addWidget(title)
        subtitle = QLabel("Отдельный билетный режим: grounded transcript, билетный контекст и итоговая оценка через существующий scoring pipeline.")
        subtitle.setProperty("role", "page-subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        self.status_chip = QLabel("Ollama: проверка нужна")
        self.status_chip.setProperty("role", "pill")
        header.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.gate_card = EmptyStatePanel(
            "dialogue",
            "Локальная модель недоступна",
            "Для запуска Dialogue нужен рабочий Ollama endpoint и модель. Пока проверка не пройдена, экран остаётся заблокирован.",
            shadow_color=shadow_color,
            role="card",
            primary_action=("Открыть настройки", self.open_settings_requested.emit, "primary", "settings"),
            secondary_action=("Повторить проверку", self.recheck_requested.emit, "secondary", "refresh"),
        )
        root.addWidget(self.gate_card)

        self.body_host = QWidget()
        self.body_layout = QHBoxLayout(self.body_host)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(16)
        root.addWidget(self.body_host, 1)

        self._build_left_column()
        self._build_center_column()
        self._build_right_column()
        self._apply_responsive_layout()
        self.refresh_theme()

    def _build_left_column(self) -> None:
        self.left_column = QWidget()
        self.left_column.setMinimumWidth(320)
        self.left_column.setMaximumWidth(396)
        layout = QVBoxLayout(self.left_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.active_card = CardFrame(role="card", shadow_color=self.shadow_color)
        active_layout = QVBoxLayout(self.active_card)
        active_layout.setContentsMargins(18, 16, 18, 16)
        active_layout.setSpacing(10)
        title = QLabel("Новая сессия")
        title.setProperty("role", "section-title")
        active_layout.addWidget(title)

        persona_row = QHBoxLayout()
        persona_row.setContentsMargins(0, 0, 0, 0)
        persona_row.setSpacing(8)
        self.persona_group = QButtonGroup(self)
        self.persona_group.setExclusive(True)
        self.tutor_button = QPushButton("Tutor")
        self.tutor_button.setCheckable(True)
        self.tutor_button.setProperty("variant", "tab")
        self.examiner_button = QPushButton("Examiner")
        self.examiner_button.setCheckable(True)
        self.examiner_button.setProperty("variant", "tab")
        self.persona_group.addButton(self.tutor_button)
        self.persona_group.addButton(self.examiner_button)
        self.tutor_button.clicked.connect(lambda: self._set_persona("tutor"))
        self.examiner_button.clicked.connect(lambda: self._set_persona("examiner"))
        persona_row.addWidget(self.tutor_button)
        persona_row.addWidget(self.examiner_button)
        active_layout.addLayout(persona_row)

        self.active_title = QLabel("Выберите билет")
        active_layout.addWidget(self.active_title)
        self.active_meta = QLabel("Диалог стартует только после выбора билета.")
        self.active_meta.setProperty("role", "body")
        self.active_meta.setWordWrap(True)
        active_layout.addWidget(self.active_meta)
        harden_plain_text(self.active_title, self.active_meta)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(10)
        self.start_button = QPushButton("Начать диалог")
        self.start_button.setProperty("variant", "primary")
        self.start_button.clicked.connect(self._handle_start)
        buttons_row.addWidget(self.start_button)
        self.open_active_button = QPushButton("Открыть активную")
        self.open_active_button.setProperty("variant", "secondary")
        self.open_active_button.clicked.connect(self._open_active_session)
        buttons_row.addWidget(self.open_active_button)
        active_layout.addLayout(buttons_row)
        layout.addWidget(self.active_card)

        self.recent_card = CardFrame(role="card", shadow_color=self.shadow_color)
        recent_layout = QVBoxLayout(self.recent_card)
        recent_layout.setContentsMargins(18, 16, 18, 16)
        recent_layout.setSpacing(10)
        recent_title = QLabel("Последние сессии")
        recent_title.setProperty("role", "section-title")
        recent_layout.addWidget(recent_title)
        self.recent_stack = QVBoxLayout()
        self.recent_stack.setContentsMargins(0, 0, 0, 0)
        self.recent_stack.setSpacing(10)
        recent_layout.addLayout(self.recent_stack)
        recent_layout.addStretch(1)
        layout.addWidget(self.recent_card, 1)

        self.ticket_card = CardFrame(role="card", shadow_color=self.shadow_color)
        ticket_layout = QVBoxLayout(self.ticket_card)
        ticket_layout.setContentsMargins(18, 16, 18, 16)
        ticket_layout.setSpacing(10)
        ticket_header = QHBoxLayout()
        ticket_header.setContentsMargins(0, 0, 0, 0)
        ticket_header.setSpacing(8)
        ticket_title = QLabel("Билеты")
        ticket_title.setProperty("role", "section-title")
        ticket_header.addWidget(ticket_title)
        ticket_header.addStretch(1)
        self.ticket_count_label = QLabel("0")
        self.ticket_count_label.setProperty("role", "pill")
        ticket_header.addWidget(self.ticket_count_label)
        ticket_layout.addLayout(ticket_header)

        self.ticket_search = QLineEdit()
        self.ticket_search.setPlaceholderText("Поиск билета...")
        self.ticket_search.setProperty("role", "search-plain")
        self.ticket_search.setFixedHeight(36)
        self.ticket_search.textChanged.connect(lambda _text: self._rebuild_ticket_list())
        ticket_layout.addWidget(self.ticket_search)

        self.ticket_stack = QVBoxLayout()
        self.ticket_stack.setContentsMargins(0, 0, 0, 0)
        self.ticket_stack.setSpacing(10)
        ticket_layout.addLayout(self.ticket_stack)
        ticket_layout.addStretch(1)
        layout.addWidget(self.ticket_card, 2)

        self.body_layout.addWidget(self.left_column)

    def _build_center_column(self) -> None:
        self.center_column = QWidget()
        self.center_column.setMinimumWidth(500)
        layout = QVBoxLayout(self.center_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.transcript_card = CardFrame(role="card", shadow_color=self.shadow_color)
        transcript_layout = QVBoxLayout(self.transcript_card)
        transcript_layout.setContentsMargins(18, 16, 18, 16)
        transcript_layout.setSpacing(10)
        transcript_header = QHBoxLayout()
        transcript_header.setContentsMargins(0, 0, 0, 0)
        transcript_header.setSpacing(8)
        transcript_title = QLabel("Transcript")
        transcript_title.setProperty("role", "section-title")
        transcript_header.addWidget(transcript_title)
        transcript_header.addStretch(1)
        self.transcript_chip = QLabel("0 turn")
        self.transcript_chip.setProperty("role", "pill")
        transcript_header.addWidget(self.transcript_chip)
        transcript_layout.addLayout(transcript_header)

        self.transcript_scroll = QScrollArea()
        self.transcript_scroll.setWidgetResizable(True)
        self.transcript_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.transcript_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.transcript_body = QWidget()
        self.transcript_body_layout = QVBoxLayout(self.transcript_body)
        self.transcript_body_layout.setContentsMargins(0, 0, 0, 0)
        self.transcript_body_layout.setSpacing(12)
        self.transcript_scroll.setWidget(self.transcript_body)
        transcript_layout.addWidget(self.transcript_scroll, 1)
        layout.addWidget(self.transcript_card, 1)

        self.result_card = CardFrame(role="card", shadow_color=self.shadow_color)
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setContentsMargins(18, 16, 18, 16)
        result_layout.setSpacing(8)
        result_title = QLabel("Статус и итог")
        result_title.setProperty("role", "section-title")
        result_layout.addWidget(result_title)
        self.result_head = QLabel("Сессия не начата")
        result_layout.addWidget(self.result_head)
        self.result_body = QLabel("Выберите билет и запустите Dialogue, чтобы transcript начал заполняться.")
        self.result_body.setProperty("role", "body")
        self.result_body.setWordWrap(True)
        result_layout.addWidget(self.result_body)
        harden_plain_text(self.result_head, self.result_body)
        self.retry_button = QPushButton("Повторить слабую нить")
        self.retry_button.setProperty("variant", "secondary")
        self.retry_button.clicked.connect(self._handle_retry)
        result_layout.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.result_card)

        self.composer_card = CardFrame(role="card", shadow_color=self.shadow_color)
        composer_layout = QVBoxLayout(self.composer_card)
        composer_layout.setContentsMargins(18, 16, 18, 16)
        composer_layout.setSpacing(10)
        composer_title = QLabel("Ответ")
        composer_title.setProperty("role", "section-title")
        composer_layout.addWidget(composer_title)
        self.composer_hint = QLabel("Сначала выберите билет и запустите сессию.")
        self.composer_hint.setProperty("role", "muted")
        self.composer_hint.setWordWrap(True)
        composer_layout.addWidget(self.composer_hint)
        self.composer_input = QTextEdit()
        self.composer_input.setProperty("role", "editor")
        self.composer_input.setPlaceholderText("Введите ответ по билету...")
        self.composer_input.setFixedHeight(140)
        self.composer_input.textChanged.connect(self._sync_controls)
        composer_layout.addWidget(self.composer_input)
        composer_actions = QHBoxLayout()
        composer_actions.setContentsMargins(0, 0, 0, 0)
        composer_actions.setSpacing(10)
        composer_actions.addStretch(1)
        self.submit_button = QPushButton("Отправить")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._handle_submit)
        composer_actions.addWidget(self.submit_button)
        composer_layout.addLayout(composer_actions)
        layout.addWidget(self.composer_card)

        self.body_layout.addWidget(self.center_column, 1)

    def _build_right_column(self) -> None:
        self.right_column = QWidget()
        self.right_column.setMinimumWidth(320)
        self.right_column.setMaximumWidth(420)
        layout = QVBoxLayout(self.right_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.summary_card = CardFrame(role="card", shadow_color=self.shadow_color)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(10)
        summary_title = QLabel("Summary")
        summary_title.setProperty("role", "section-title")
        summary_layout.addWidget(summary_title)
        self.summary_body = QLabel("Выберите билет, чтобы увидеть каноническое резюме.")
        self.summary_body.setProperty("role", "body")
        self.summary_body.setWordWrap(True)
        summary_layout.addWidget(self.summary_body)
        self.summary_meta = QLabel("")
        self.summary_meta.setProperty("role", "muted")
        self.summary_meta.setWordWrap(True)
        summary_layout.addWidget(self.summary_meta)
        harden_plain_text(self.summary_body, self.summary_meta)
        layout.addWidget(self.summary_card)

        self.structure_card = CardFrame(role="card", shadow_color=self.shadow_color)
        structure_layout = QVBoxLayout(self.structure_card)
        structure_layout.setContentsMargins(18, 16, 18, 16)
        structure_layout.setSpacing(10)
        structure_title = QLabel("Structure")
        structure_title.setProperty("role", "section-title")
        structure_layout.addWidget(structure_title)
        self.structure_body = QLabel("Здесь появятся answer blocks, atoms и examiner prompts.")
        self.structure_body.setProperty("role", "body")
        self.structure_body.setWordWrap(True)
        structure_layout.addWidget(self.structure_body)
        harden_plain_text(self.structure_body)
        layout.addWidget(self.structure_card)

        self.weak_card = CardFrame(role="card", shadow_color=self.shadow_color)
        weak_layout = QVBoxLayout(self.weak_card)
        weak_layout.setContentsMargins(18, 16, 18, 16)
        weak_layout.setSpacing(10)
        weak_title = QLabel("Weak Areas")
        weak_title.setProperty("role", "section-title")
        weak_layout.addWidget(weak_title)
        self.weak_body = QLabel("Для выбранного билета слабые места пока не показаны.")
        self.weak_body.setProperty("role", "body")
        self.weak_body.setWordWrap(True)
        weak_layout.addWidget(self.weak_body)
        harden_plain_text(self.weak_body)
        layout.addWidget(self.weak_card)
        layout.addStretch(1)

        self.body_layout.addWidget(self.right_column)

    def set_snapshot(
        self,
        snapshot: DialogueSnapshot | None = None,
        *,
        tickets: list[TicketKnowledgeMap] | None = None,
        weak_areas=None,
        diagnostics: OllamaDiagnostics | None = None,
    ) -> None:
        if snapshot is not None:
            self.snapshot = snapshot
        if tickets is not None:
            self.ticket_maps = tickets[:]
            self.ticket_lookup = {ticket.ticket_id: ticket for ticket in tickets}
        if weak_areas is not None:
            self.weak_areas = [dict(row) for row in weak_areas]
        if diagnostics is not None:
            self.diagnostics = diagnostics

        if self.current_session is not None:
            if self.snapshot.active_session and self.snapshot.active_session.session.session_id == self.current_session.session.session_id:
                self.current_session.session = self.snapshot.active_session.session
            else:
                for session in self.snapshot.recent_sessions:
                    if session.session_id == self.current_session.session.session_id:
                        self.current_session.session = session
                        break

        if not self.selected_ticket_id:
            if self.current_session is not None:
                self.selected_ticket_id = self.current_session.ticket.ticket_id
            elif self.snapshot.active_session is not None:
                self.selected_ticket_id = self.snapshot.active_session.ticket.ticket_id
            elif self.ticket_maps:
                self.selected_ticket_id = self.ticket_maps[0].ticket_id

        self._apply_gate()
        self._rebuild_ticket_list()
        self._rebuild_recent_sessions()
        self._rebuild_transcript()
        self._refresh_context()
        self._refresh_active_card()
        self._refresh_result_card()
        self._sync_controls()

    def show_session(self, session: DialogueSessionState) -> None:
        self.current_session = session
        self.selected_ticket_id = session.ticket.ticket_id
        self.persona_kind = session.session.persona_kind
        self._pending = False
        self._pending_message = ""
        if self._pending_turn_text:
            self.composer_input.clear()
            self._pending_turn_text = ""
        self._rebuild_ticket_list()
        self._rebuild_recent_sessions()
        self._rebuild_transcript()
        self._refresh_context()
        self._refresh_active_card()
        self._refresh_result_card()
        self._sync_controls()

    def set_pending(self, pending: bool, message: str = "") -> None:
        self._pending = pending
        self._pending_message = message
        self._refresh_result_card()
        self._sync_controls()

    def select_ticket(self, ticket_id: str) -> None:
        if not ticket_id or ticket_id not in self.ticket_lookup:
            return
        self.selected_ticket_id = ticket_id
        if self.current_session is not None and self.current_session.session.status != "active" and self.current_session.ticket.ticket_id != ticket_id:
            self.current_session = None
        self._rebuild_ticket_list()
        self._refresh_context()
        self._refresh_active_card()
        self._refresh_result_card()
        self._sync_controls()

    def refresh_theme(self) -> None:
        self._apply_theme()
        self._apply_gate()
        self._rebuild_ticket_list()
        self._rebuild_recent_sessions()
        self._rebuild_transcript()
        self._refresh_context()
        self._refresh_active_card()
        self._refresh_result_card()
        self._sync_controls()

    def _apply_theme(self) -> None:
        colors = current_colors()
        self.status_chip.setStyleSheet(
            f"background: {colors['primary_soft']}; color: {colors['primary']}; border-radius: 999px; padding: 8px 14px; "
            "font-size: 12px; font-weight: 700;"
        )
        self.active_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.result_head.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {colors['text']};")
        for button, icon_name in (
            (self.start_button, "spark"),
            (self.open_active_button, "dialogue"),
            (self.submit_button, "dialogue"),
            (self.retry_button, "refresh"),
        ):
            apply_button_icon(button, icon_name, size=18)

    def _apply_gate(self) -> None:
        available = bool(self.diagnostics and self.diagnostics.endpoint_ok and self.diagnostics.model_ok)
        if self.diagnostics is None:
            self.status_chip.setText("Ollama: проверка нужна")
        elif available:
            self.status_chip.setText("Ollama: подключено")
        elif self.diagnostics.endpoint_ok:
            self.status_chip.setText("Ollama: сервер отвечает")
        else:
            self.status_chip.setText("Ollama: недоступно")
        self.body_host.setVisible(available)
        self.gate_card.setVisible(not available)

    def _rebuild_ticket_list(self) -> None:
        while self.ticket_stack.count():
            item = self.ticket_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._ticket_rows.clear()

        merged = self._filtered_ticket_items()
        self.ticket_count_label.setText(str(len(self.ticket_maps)))
        if not merged:
            self.ticket_stack.addWidget(
                EmptyStatePanel(
                    "tickets",
                    "Билеты не найдены" if self.ticket_maps else "Билеты ещё не собраны",
                    (
                        "Измените запрос, чтобы снова увидеть билет для dialogue-сессии."
                        if self.ticket_maps
                        else "Сначала импортируйте материалы, чтобы здесь появились билеты для dialogue-режима."
                    ),
                    role="subtle-card",
                    secondary_action=None if self.ticket_maps else ("Открыть библиотеку", self.open_library_requested.emit, "secondary", "library"),
                )
            )
            return

        if self.selected_ticket_id not in {item.ticket_id for item in merged}:
            self.selected_ticket_id = merged[0].ticket_id
        for item in merged:
            row = DialogueTicketRow(item, selected=item.ticket_id == self.selected_ticket_id)
            row.clicked_ticket.connect(self.select_ticket)
            self.ticket_stack.addWidget(row)
            self._ticket_rows[item.ticket_id] = row

    def _rebuild_recent_sessions(self) -> None:
        while self.recent_stack.count():
            item = self.recent_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self.snapshot.recent_sessions:
            self.recent_stack.addWidget(
                EmptyStatePanel(
                    "queue",
                    "История появится после первой завершённой сессии",
                    "Здесь будут shown recent dialogue sessions, их score и verdict.",
                    role="subtle-card",
                )
            )
            return
        selected_id = self.current_session.session.session_id if self.current_session is not None else ""
        for session in self.snapshot.recent_sessions[:6]:
            row = DialogueSessionRow(session, selected=session.session_id == selected_id)
            row.clicked_session.connect(self.session_requested.emit)
            self.recent_stack.addWidget(row)

    def _rebuild_transcript(self) -> None:
        while self.transcript_body_layout.count():
            item = self.transcript_body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        turns = self.current_session.turns if self.current_session is not None else []
        if not turns:
            self.transcript_body_layout.addWidget(
                EmptyStatePanel(
                    "dialogue",
                    "Transcript пока пуст",
                    "Начните сессию, чтобы здесь появились вопросы, ответы и итоговый разбор.",
                    role="subtle-card",
                )
            )
            self.transcript_chip.setText("0 turn")
            return
        persona_kind = self.current_session.session.persona_kind if self.current_session is not None else self.persona_kind
        for turn in turns:
            self.transcript_body_layout.addWidget(DialogueTurnBubble(turn, persona_kind=persona_kind))
        self.transcript_body_layout.addStretch(1)
        self.transcript_chip.setText(f"{len(turns)} turn")
        self.transcript_scroll.verticalScrollBar().setValue(self.transcript_scroll.verticalScrollBar().maximum())

    def _refresh_context(self) -> None:
        ticket = self.ticket_lookup.get(self.selected_ticket_id)
        if ticket is None:
            self.summary_body.setText("Выберите билет, чтобы увидеть каноническое резюме.")
            self.summary_meta.setText("")
            self.structure_body.setText("Здесь появятся answer blocks, atoms и examiner prompts.")
            self.weak_body.setText("Слабые места выбранного билета будут показаны здесь.")
            return

        self.summary_body.setText(ticket.canonical_answer_summary or "Краткое каноническое резюме пока не сформировано.")
        self.summary_meta.setText(
            f"Профиль: {answer_profile_label(ticket.answer_profile_code)} • Атомов: {len(ticket.atoms)} • "
            f"Навыков: {len(ticket.skills)} • Examiner prompts: {len(ticket.examiner_prompts)}"
        )

        structure_lines: list[str] = []
        if ticket.answer_blocks:
            structure_lines.extend(f"• {block.title}" for block in ticket.answer_blocks[:6])
        else:
            structure_lines.extend(f"• {atom.label}" for atom in ticket.atoms[:6])
        if ticket.examiner_prompts:
            structure_lines.append("")
            structure_lines.extend(f"◦ {prompt.text}" for prompt in ticket.examiner_prompts[:3])
        self.structure_body.setText("\n".join(line for line in structure_lines if line) or "Структура ещё не подготовлена.")

        weak_lines = []
        for row in self.weak_areas:
            related_ids = self._parse_list(row.get("related_ticket_ids_json"))
            if row.get("reference_id") == ticket.ticket_id or ticket.ticket_id in related_ids:
                weak_lines.append(f"• {row.get('title', 'Без названия')}")
        if self.current_session is not None and self.current_session.result is not None:
            for weak_point in self.current_session.result.weak_points:
                line = f"• {weak_point}"
                if line not in weak_lines:
                    weak_lines.append(line)
        self.weak_body.setText("\n".join(weak_lines[:6]) if weak_lines else "Для этого билета слабые места пока не зафиксированы.")

    def _refresh_active_card(self) -> None:
        ticket = self.ticket_lookup.get(self.selected_ticket_id)
        active_summary = self._active_summary_for_selected()
        if ticket is None:
            self.active_title.setText("Выберите билет")
            self.active_meta.setText("Диалог стартует только после выбора билета.")
            return
        if active_summary is not None:
            persona = "Examiner" if active_summary.persona_kind == "examiner" else "Tutor"
            self.active_title.setText(ticket.title)
            self.active_meta.setText(
                f"Активная сессия: {persona} • turn-ов: {active_summary.last_turn_index} • обновлено {active_summary.updated_label}"
            )
        elif self.current_session is not None and self.current_session.ticket.ticket_id == ticket.ticket_id and self.current_session.session.status == "completed":
            self.active_title.setText(ticket.title)
            self.active_meta.setText("Открыт replay завершённой сессии. Можно начать новую попытку.")
        else:
            self.active_title.setText(ticket.title)
            persona = "Examiner" if self.persona_kind == "examiner" else "Tutor"
            self.active_meta.setText(f"Persona: {persona}. После старта первый вопрос создаст локальная LLM.")

    def _refresh_result_card(self) -> None:
        if self._pending and self._pending_message:
            self.result_head.setText("Идёт обработка")
            self.result_body.setText(self._pending_message)
            self.retry_button.hide()
            return
        if self.current_session is None:
            self.result_head.setText("Сессия не начата")
            readiness = self.snapshot.readiness
            if readiness is None:
                self.result_body.setText("Выберите билет и запустите Dialogue.")
            else:
                self.result_body.setText(
                    f"Готовность: {readiness.percent}% • билетов пройдено: {readiness.tickets_practiced}/{readiness.tickets_total}."
                )
            self.retry_button.hide()
            return
        if self.current_session.result is not None:
            result = self.current_session.result
            self.result_head.setText(f"Итог: {result.score_percent}%")
            self.result_body.setText(result.final_verdict or result.feedback or "Сессия завершена.")
            self.retry_button.setVisible(bool(self._current_retry_focus()))
            return
        if self.current_session.session.status == "active":
            persona = "Examiner" if self.current_session.session.persona_kind == "examiner" else "Tutor"
            self.result_head.setText(f"Активная сессия • {persona}")
            self.result_body.setText(
                f"User turns: {self.current_session.session.user_turn_count}/5 • transcript: {len(self.current_session.turns)} сообщений."
            )
            self.retry_button.hide()
            return
        self.result_head.setText("Сессия загружена")
        self.result_body.setText(self.current_session.session.summary or "Read-only transcript доступен для просмотра.")
        self.retry_button.setVisible(bool(self._current_retry_focus()))

    def _sync_controls(self) -> None:
        available = bool(self.diagnostics and self.diagnostics.endpoint_ok and self.diagnostics.model_ok)
        active_summary = self._active_summary_for_selected()
        current_active = (
            self.current_session is not None
            and self.current_session.session.status == "active"
            and self.current_session.ticket.ticket_id == self.selected_ticket_id
        )
        self.tutor_button.setChecked(self.persona_kind == "tutor")
        self.examiner_button.setChecked(self.persona_kind == "examiner")
        self.tutor_button.setEnabled(not current_active)
        self.examiner_button.setEnabled(not current_active)

        if not self.selected_ticket_id:
            self.start_button.setText("Начать диалог")
        elif current_active or active_summary is not None:
            self.start_button.setText("Продолжить диалог")
        elif self.current_session is not None and self.current_session.session.status == "completed":
            self.start_button.setText("Новый диалог")
        else:
            self.start_button.setText("Начать диалог")
        self.start_button.setEnabled(available and not self._pending and bool(self.selected_ticket_id))
        self.open_active_button.setVisible(active_summary is not None)
        self.open_active_button.setEnabled(active_summary is not None and not current_active and not self._pending)

        composer_enabled = available and current_active and not self._pending
        self.composer_input.setEnabled(composer_enabled)
        self.submit_button.setEnabled(composer_enabled and bool(self.composer_input.toPlainText().strip()))
        if current_active:
            self.composer_hint.setText("Промежуточные turn-и не меняют mastery. Итоговая оценка будет только при завершении сессии.")
        elif self.current_session is not None and self.current_session.session.status == "completed":
            self.composer_hint.setText("Открыт replay завершённой сессии. Для новой попытки используйте кнопку запуска выше.")
        else:
            self.composer_hint.setText("Сначала запустите сессию по выбранному билету.")

    def _filtered_ticket_items(self) -> list[DialogueTicketItem]:
        meta_lookup = {item.ticket_id: item for item in self.snapshot.tickets}
        merged: list[DialogueTicketItem] = []
        for ticket in self.ticket_maps:
            meta = meta_lookup.get(ticket.ticket_id)
            merged.append(
                DialogueTicketItem(
                    ticket_id=ticket.ticket_id,
                    title=ticket.title,
                    section_title=meta.section_title if meta is not None else ticket.section_id,
                    difficulty=meta.difficulty if meta is not None else ticket.difficulty,
                    mastery_score=meta.mastery_score if meta is not None else 0,
                    has_active_session=meta.has_active_session if meta is not None else False,
                    last_session_label=meta.last_session_label if meta is not None else "",
                )
            )
        query = self.ticket_search.text().strip().lower()
        if not query:
            return merged
        return [
            item for item in merged
            if query in item.title.lower()
            or query in (self.ticket_lookup[item.ticket_id].canonical_answer_summary or "").lower()
        ]

    def _active_summary_for_selected(self) -> DialogueSessionSummary | None:
        for session in self.snapshot.active_sessions:
            if session.ticket_id == self.selected_ticket_id and session.persona_kind == self.persona_kind:
                return session
        if (
            self.current_session is not None
            and self.current_session.session.status == "active"
            and self.current_session.ticket.ticket_id == self.selected_ticket_id
        ):
            return self.current_session.session
        return None

    def _current_retry_focus(self) -> str:
        if self.current_session is None:
            return ""
        if self.current_session.result and self.current_session.result.weak_points:
            return self.current_session.result.weak_points[0]
        for turn in self.current_session.turns:
            if turn.speaker == "assistant" and turn.weakness_focus:
                return turn.weakness_focus
        return ""

    def _open_active_session(self) -> None:
        active_summary = self._active_summary_for_selected()
        if active_summary is not None:
            self.session_requested.emit(active_summary.session_id)

    def _handle_start(self) -> None:
        if not self.selected_ticket_id:
            return
        self._pending = True
        self._pending_message = "Готовим новую dialogue-сессию и первое tutor/examiner сообщение."
        self._sync_controls()
        self._refresh_result_card()
        self.session_start_requested.emit(self.selected_ticket_id, self.persona_kind, self._retry_focus)
        self._retry_focus = ""

    def _handle_submit(self) -> None:
        if self.current_session is None or self.current_session.session.status != "active":
            return
        text = self.composer_input.toPlainText().strip()
        if not text:
            return
        self._pending_turn_text = text
        self._pending = True
        self._pending_message = "Отправляем ответ в dialogue-оркестратор и ждём следующий turn."
        self._sync_controls()
        self._refresh_result_card()
        self.turn_submitted.emit(
            self.current_session.session.session_id,
            text,
            self.current_session.session.last_turn_index,
        )

    def _handle_retry(self) -> None:
        if self.current_session is None:
            return
        self._retry_focus = self._current_retry_focus()
        self.persona_kind = self.current_session.session.persona_kind
        self._handle_start()

    def _set_persona(self, persona_kind: str) -> None:
        self.persona_kind = persona_kind
        self._refresh_active_card()
        self._sync_controls()

    @staticmethod
    def _parse_list(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        return list(json.loads(raw_value))

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        width = self.window().width() if self.window() is not None else self.width()
        if width < 1380:
            if self.body_layout.direction() != QBoxLayout.Direction.TopToBottom:
                self.body_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.left_column.setMinimumWidth(0)
            self.left_column.setMaximumWidth(16777215)
            self.center_column.setMinimumWidth(0)
            self.right_column.setMinimumWidth(0)
            self.right_column.setMaximumWidth(16777215)
        else:
            if self.body_layout.direction() != QBoxLayout.Direction.LeftToRight:
                self.body_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.left_column.setMinimumWidth(320)
            self.left_column.setMaximumWidth(396)
            self.center_column.setMinimumWidth(500)
            self.right_column.setMinimumWidth(320)
            self.right_column.setMaximumWidth(420)
