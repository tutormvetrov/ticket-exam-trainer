from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from application.ui_data import TrainingEvaluationResult, TrainingSnapshot
from domain.knowledge import TicketKnowledgeMap
from ui.components.common import CardFrame, ClickableFrame
from ui.components.training_modes import TrainingModesPanel
from ui.training_catalog import DEFAULT_TRAINING_MODES


class AdaptiveQueueCard(ClickableFrame):
    def __init__(self, title: str, priority_text: str, repeat_text: str, shadow_color) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color, shadow=False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(102)
        self.setObjectName("AdaptiveQueueCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #1F2A3B;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.priority_label = QLabel(priority_text)
        self.priority_label.setStyleSheet("font-size: 12px; color: #5F6B7A; font-weight: 600;")
        self.priority_label.setWordWrap(True)
        layout.addWidget(self.priority_label)

        self.repeat_label = QLabel(repeat_text)
        self.repeat_label.setStyleSheet("font-size: 12px; color: #7A8899;")
        self.repeat_label.setWordWrap(True)
        layout.addWidget(self.repeat_label)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        border = "#7FAEFF" if selected else "#E2EAF3"
        background = "#F6FAFF" if selected else "#FFFFFF"
        self.setStyleSheet(
            f"QFrame#AdaptiveQueueCard {{ background: {background}; border: 1px solid {border}; border-radius: 16px; }}"
        )


class TrainingView(QWidget):
    evaluate_requested = Signal(str, str, str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.snapshot = TrainingSnapshot()
        self.selected_ticket_id = ""
        self.selected_mode = "active-recall"
        self.ticket_lookup: dict[str, TicketKnowledgeMap] = {}
        self.queue_buttons: dict[str, AdaptiveQueueCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Тренировка")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        self.modes_panel = TrainingModesPanel(DEFAULT_TRAINING_MODES, shadow_color)
        self.modes_panel.mode_selected.connect(self.select_mode)
        layout.addWidget(self.modes_panel)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        self.queue_card = CardFrame(role="card", shadow_color=shadow_color)
        self.queue_card.setMinimumWidth(320)
        self.queue_card.setMaximumWidth(472)
        queue_layout = QVBoxLayout(self.queue_card)
        queue_layout.setContentsMargins(18, 18, 18, 18)
        queue_layout.setSpacing(12)
        self.queue_title = QLabel("Адаптивная очередь")
        self.queue_title.setProperty("role", "section-title")
        queue_layout.addWidget(self.queue_title)
        self.queue_stack = QVBoxLayout()
        self.queue_stack.setContentsMargins(0, 0, 0, 0)
        self.queue_stack.setSpacing(10)
        queue_layout.addLayout(self.queue_stack)
        queue_layout.addStretch(1)
        body.addWidget(self.queue_card, 4)

        self.session_card = CardFrame(role="card", shadow_color=shadow_color)
        session_layout = QVBoxLayout(self.session_card)
        session_layout.setContentsMargins(22, 20, 22, 20)
        session_layout.setSpacing(12)
        self.session_title = QLabel("Выберите билет")
        self.session_title.setStyleSheet("font-size: 20px; font-weight: 800;")
        session_layout.addWidget(self.session_title)

        self.session_meta = QLabel("Очередь пока пуста.")
        self.session_meta.setProperty("role", "body")
        self.session_meta.setWordWrap(True)
        session_layout.addWidget(self.session_meta)

        self.session_hint = QLabel(
            "Ответ можно писать в свободной форме. Оценка сохранится в БД и повлияет на адаптивное повторение."
        )
        self.session_hint.setProperty("role", "body")
        self.session_hint.setWordWrap(True)
        session_layout.addWidget(self.session_hint)

        answer_label = QLabel("Ваш ответ")
        answer_label.setProperty("role", "section-title")
        session_layout.addWidget(answer_label)

        editor_shell = QFrame()
        editor_shell.setProperty("role", "editor-shell")
        editor_layout = QVBoxLayout(editor_shell)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.setSpacing(0)
        self.answer_input = QTextEdit()
        self.answer_input.setProperty("role", "editor")
        self.answer_input.setPlaceholderText("Введите краткий или полный ответ по выбранному билету...")
        self.answer_input.setMinimumHeight(220)
        editor_layout.addWidget(self.answer_input)
        session_layout.addWidget(editor_shell)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(12)
        self.mode_label = QLabel("Режим: Active Recall")
        self.mode_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        action_row.addWidget(self.mode_label)
        action_row.addStretch(1)
        self.check_button = QPushButton("Проверить ответ")
        self.check_button.setProperty("variant", "primary")
        self.check_button.clicked.connect(self._emit_evaluation)
        action_row.addWidget(self.check_button)
        session_layout.addLayout(action_row)

        self.feedback_title = QLabel("Результат проверки")
        self.feedback_title.setProperty("role", "section-title")
        session_layout.addWidget(self.feedback_title)

        self.feedback_body = QLabel("Проверка ещё не запускалась.")
        self.feedback_body.setProperty("role", "body")
        self.feedback_body.setWordWrap(True)
        session_layout.addWidget(self.feedback_body)

        body.addWidget(self.session_card, 6)
        layout.addLayout(body, 1)

    def set_snapshot(self, snapshot: TrainingSnapshot) -> None:
        self.snapshot = snapshot
        self.ticket_lookup = {ticket.ticket_id: ticket for ticket in snapshot.tickets}
        self._rebuild_queue()
        if snapshot.queue_items:
            selected = self.selected_ticket_id if self.selected_ticket_id in self.ticket_lookup else snapshot.queue_items[0].ticket_id
            self.select_ticket(selected)
        elif snapshot.tickets:
            self.select_ticket(snapshot.tickets[0].ticket_id)
        else:
            self.selected_ticket_id = ""
            self.session_title.setText("Выберите билет")
            self.session_meta.setText("Очередь пока пуста.")

    def select_mode(self, mode_key: str) -> None:
        self.selected_mode = mode_key
        label_map = {mode.key: mode.title for mode in DEFAULT_TRAINING_MODES}
        self.mode_label.setText(f"Режим: {label_map.get(mode_key, mode_key)}")

    def select_ticket(self, ticket_id: str) -> None:
        self.selected_ticket_id = ticket_id
        for item_id, button in self.queue_buttons.items():
            button.set_selected(item_id == ticket_id)

        ticket = self.ticket_lookup.get(ticket_id)
        if ticket is None:
            self.session_title.setText("Выберите билет")
            self.session_meta.setText("По выбранному элементу нет данных.")
            return
        self.session_title.setText(ticket.title)
        self.session_meta.setText(
            f"Атомов: {len(ticket.atoms)} • Навыков: {len(ticket.skills)} • Ориентир устного ответа: {ticket.estimated_oral_time_sec} сек."
        )

    def show_evaluation(self, result: TrainingEvaluationResult) -> None:
        if not result.ok:
            self.feedback_body.setText(result.error or "Проверка завершилась ошибкой.")
            return

        lines = [f"Оценка: {result.score_percent}%"]
        if result.feedback:
            lines.append(result.feedback)
        if result.weak_points:
            lines.append("Слабые места: " + ", ".join(result.weak_points))
        if result.followup_questions:
            lines.append("Follow-up:")
            lines.extend(f"• {question}" for question in result.followup_questions[:4])
        self.feedback_body.setText("\n".join(lines))

    def _rebuild_queue(self) -> None:
        self.queue_title.setText(f"Адаптивная очередь ({len(self.snapshot.queue_items)})")
        while self.queue_stack.count():
            item = self.queue_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.queue_buttons.clear()

        if not self.snapshot.queue_items:
            empty = QLabel("После импорта и первых попыток здесь появится адаптивная очередь повторения.")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.queue_stack.addWidget(empty)
            return

        for item in self.snapshot.queue_items:
            button = AdaptiveQueueCard(
                item.ticket_title,
                f"Приоритет: {item.priority:.2f} • {item.reference_type}",
                f"Повтор: {item.due_label}",
                self.shadow_color,
            )
            button.clicked.connect(lambda ticket_id=item.ticket_id: self.select_ticket(ticket_id))
            self.queue_stack.addWidget(button)
            self.queue_buttons[item.ticket_id] = button

    def _emit_evaluation(self) -> None:
        if not self.selected_ticket_id:
            self.feedback_body.setText("Нет выбранного билета для проверки.")
            return
        self.evaluate_requested.emit(
            self.selected_ticket_id,
            self.selected_mode,
            self.answer_input.toPlainText(),
        )

    def set_search_text(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self._rebuild_queue()
            return

        filtered = [item for item in self.snapshot.queue_items if query in item.ticket_title.lower()]
        current = self.snapshot
        self.snapshot = TrainingSnapshot(queue_items=filtered, tickets=current.tickets)
        self._rebuild_queue()
        self.snapshot = current
