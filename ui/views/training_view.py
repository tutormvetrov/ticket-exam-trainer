from __future__ import annotations

from random import Random

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QHBoxLayout, QLineEdit, QStackedWidget, QVBoxLayout, QWidget

from application.answer_profile_registry import answer_profile_label
from application.ui_data import TrainingEvaluationResult, TrainingSnapshot
from domain.knowledge import TicketKnowledgeMap
from ui.components.common import CardFrame, ClickableFrame, EmptyStatePanel
from ui.components.training_modes import TrainingModesPanel
from ui.components.training_workspaces import TrainingWorkspaceBase, create_training_workspaces
from ui.training_catalog import DEFAULT_TRAINING_MODES
from ui.training_mode_registry import TRAINING_MODE_SPECS
from ui.theme import current_colors


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
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.priority_label = QLabel(priority_text)
        self.priority_label.setWordWrap(True)
        layout.addWidget(self.priority_label)

        self.repeat_label = QLabel(repeat_text)
        self.repeat_label.setWordWrap(True)
        layout.addWidget(self.repeat_label)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        colors = current_colors()
        border = colors["primary"] if selected else colors["border"]
        background = colors["primary_soft"] if selected else colors["card_bg"]
        self.setStyleSheet(
            f"QFrame#AdaptiveQueueCard {{ background: {background}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        self.priority_label.setStyleSheet(f"font-size: 12px; color: {colors['text_secondary']}; font-weight: 600;")
        self.repeat_label.setStyleSheet(f"font-size: 12px; color: {colors['text_tertiary']};")

    def refresh_theme(self) -> None:
        self.set_selected(self.property("selected") is True)


class TrainingView(QWidget):
    evaluate_requested = Signal(str, str, str)
    open_library_requested = Signal()
    import_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.snapshot = TrainingSnapshot()
        self.selected_ticket_id = ""
        self.selected_mode = "active-recall"
        self.ticket_lookup: dict[str, TicketKnowledgeMap] = {}
        self.queue_buttons: dict[str, AdaptiveQueueCard] = {}
        self.workspaces: dict[str, TrainingWorkspaceBase] = create_training_workspaces()
        self._suppress_ticket_selector = False
        self._last_result: TrainingEvaluationResult | None = None
        self._last_result_ticket_id = ""
        self._last_result_mode = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Тренировка")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        self.modes_panel = TrainingModesPanel(DEFAULT_TRAINING_MODES, shadow_color)
        self.modes_panel.mode_selected.connect(self.select_mode)
        layout.addWidget(self.modes_panel)

        self.body = QGridLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setHorizontalSpacing(16)
        self.body.setVerticalSpacing(16)

        self.queue_card = CardFrame(role="card", shadow_color=shadow_color)
        self.queue_card.setMinimumWidth(320)
        self.queue_card.setMaximumWidth(472)
        queue_layout = QVBoxLayout(self.queue_card)
        queue_layout.setContentsMargins(18, 18, 18, 18)
        queue_layout.setSpacing(12)
        self.queue_title = QLabel("Адаптивная очередь")
        self.queue_title.setProperty("role", "section-title")
        queue_layout.addWidget(self.queue_title)
        self.queue_filter = QLineEdit()
        self.queue_filter.setPlaceholderText("Фильтр по билетам...")
        self.queue_filter.setProperty("role", "search-plain")
        self.queue_filter.setFixedHeight(36)
        self.queue_filter.textChanged.connect(self._apply_queue_filter)
        queue_layout.addWidget(self.queue_filter)
        self.queue_stack = QVBoxLayout()
        self.queue_stack.setContentsMargins(0, 0, 0, 0)
        self.queue_stack.setSpacing(10)
        queue_layout.addLayout(self.queue_stack)
        queue_layout.addStretch(1)
        self.body.addWidget(self.queue_card, 0, 0)

        self.session_card = CardFrame(role="card", shadow_color=shadow_color)
        session_layout = QVBoxLayout(self.session_card)
        session_layout.setContentsMargins(22, 20, 22, 20)
        session_layout.setSpacing(14)

        self.session_title = QLabel("Выберите билет")
        self.session_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {current_colors()['text']};")
        session_layout.addWidget(self.session_title)

        self.session_meta = QLabel("Сначала выберите билет из очереди или вручную.")
        self.session_meta.setProperty("role", "body")
        self.session_meta.setWordWrap(True)
        session_layout.addWidget(self.session_meta)

        selector_row = QHBoxLayout()
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.setSpacing(10)
        selector_label = QLabel("Билет")
        selector_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {current_colors()['text_secondary']};")
        self.ticket_selector = QComboBox()
        self.ticket_selector.currentIndexChanged.connect(self._ticket_selector_changed)
        selector_row.addWidget(selector_label)
        selector_row.addWidget(self.ticket_selector, 1)
        session_layout.addLayout(selector_row)

        self.workspace_title = QLabel(TRAINING_MODE_SPECS[self.selected_mode].workspace_title)
        self.workspace_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {current_colors()['text']};")
        self.workspace_title.setWordWrap(True)
        session_layout.addWidget(self.workspace_title)

        self.workspace_hint = QLabel(TRAINING_MODE_SPECS[self.selected_mode].workspace_hint)
        self.workspace_hint.setProperty("role", "body")
        self.workspace_hint.setWordWrap(True)
        session_layout.addWidget(self.workspace_hint)

        self.session_empty_state = EmptyStatePanel(
            "training",
            "Нет билетов для тренировки",
            "Импортируйте материалы в библиотеку, чтобы открыть тренировочные режимы и адаптивную очередь.",
            role="subtle-card",
            primary_action=("Импортировать документ", self.import_requested.emit, "primary", "import"),
            secondary_action=("Открыть библиотеку", self.open_library_requested.emit, "secondary", "library"),
        )
        session_layout.addWidget(self.session_empty_state)

        self.workspace_stack = QStackedWidget()
        for mode_key, workspace in self.workspaces.items():
            workspace.setObjectName(f"training-workspace-{mode_key}")
            workspace.evaluate_requested.connect(self._emit_evaluation)
            workspace.advance_requested.connect(self.select_next_ticket)
            workspace.random_requested.connect(self.select_random_ticket)
            self.workspace_stack.addWidget(workspace)
        session_layout.addWidget(self.workspace_stack, 1)

        self.body.addWidget(self.session_card, 0, 1)
        self.body.setColumnStretch(0, 4)
        self.body.setColumnStretch(1, 6)
        layout.addLayout(self.body, 1)

        self.modes_panel.set_selected_mode(self.selected_mode)
        self._show_workspace(self.selected_mode)
        self._apply_responsive_layout()
        self._sync_session_empty_state()

    def set_snapshot(self, snapshot: TrainingSnapshot) -> None:
        self.snapshot = snapshot
        self.ticket_lookup = {ticket.ticket_id: ticket for ticket in snapshot.tickets}
        self._populate_ticket_selector()
        self._rebuild_queue()

        if snapshot.queue_items:
            selected = self.selected_ticket_id if self.selected_ticket_id in self.ticket_lookup else snapshot.queue_items[0].ticket_id
            self.select_ticket(selected)
        elif snapshot.tickets:
            selected = self.selected_ticket_id if self.selected_ticket_id in self.ticket_lookup else snapshot.tickets[0].ticket_id
            self.select_ticket(selected)
        else:
            self.selected_ticket_id = ""
            self.session_title.setText("Нет билетов")
            self.session_meta.setText("Сначала импортируйте и обработайте материалы, затем выберите билет для тренировки.")
            self._update_workspace()
        self._sync_session_empty_state()

    def select_mode(self, mode_key: str) -> None:
        if mode_key not in self.workspaces:
            return
        current_workspace = self.workspaces.get(self.selected_mode)
        if current_workspace is not None:
            current_workspace.deactivate()

        self.selected_mode = mode_key
        self.modes_panel.set_selected_mode(mode_key)
        self._show_workspace(mode_key)

        if mode_key == "mini-exam" and self.ticket_lookup:
            self.select_random_ticket()
        else:
            self._update_workspace()
            self._sync_session_empty_state()

    def select_ticket(self, ticket_id: str) -> None:
        self.selected_ticket_id = ticket_id
        for item_id, button in self.queue_buttons.items():
            button.set_selected(item_id == ticket_id)

        ticket = self.ticket_lookup.get(ticket_id)
        if ticket is None:
            self.session_title.setText("Выберите билет")
            self.session_meta.setText("По выбранному элементу нет данных.")
            self._update_workspace()
            self._sync_session_empty_state()
            return

        self.session_title.setText(ticket.title)
        self.session_meta.setText(
            f"Профиль: {answer_profile_label(ticket.answer_profile_code)} • Атомов: {len(ticket.atoms)} • Навыков: {len(ticket.skills)} • "
            f"Ориентир устного ответа: {ticket.estimated_oral_time_sec} сек."
        )
        self._select_ticket_in_combo(ticket_id)
        self._update_workspace()
        self._sync_session_empty_state()

    def select_next_ticket(self) -> None:
        ids = self._visible_ticket_ids()
        if not ids:
            return
        if self.selected_ticket_id not in ids:
            self.select_ticket(ids[0])
            return
        index = ids.index(self.selected_ticket_id)
        self.select_ticket(ids[(index + 1) % len(ids)])

    def select_random_ticket(self) -> None:
        ids = self._visible_ticket_ids()
        if not ids:
            return
        if len(ids) == 1:
            self.select_ticket(ids[0])
            return
        random = Random(len(ids) * 31 + sum(ord(char) for char in self.selected_mode))
        candidates = [ticket_id for ticket_id in ids if ticket_id != self.selected_ticket_id]
        self.select_ticket(random.choice(candidates or ids))

    def show_evaluation(self, result: TrainingEvaluationResult) -> None:
        self._last_result = result
        self._last_result_ticket_id = self.selected_ticket_id
        self._last_result_mode = self.selected_mode
        self.workspaces[self.selected_mode].show_evaluation(result)

    def _apply_queue_filter(self, text: str) -> None:
        query = text.strip().lower()
        saved_selection = self.selected_ticket_id
        if not query:
            self._rebuild_queue()
        else:
            filtered = [item for item in self.snapshot.queue_items if query in item.ticket_title.lower()]
            current = self.snapshot
            self.snapshot = TrainingSnapshot(queue_items=filtered, tickets=current.tickets)
            self._rebuild_queue()
            self.snapshot = current
        if saved_selection in self.queue_buttons:
            self.queue_buttons[saved_selection].set_selected(True)

    def _show_workspace(self, mode_key: str) -> None:
        spec = TRAINING_MODE_SPECS[mode_key]
        self.workspace_title.setText(spec.workspace_title)
        self.workspace_hint.setText(spec.workspace_hint)
        self.workspace_stack.setCurrentWidget(self.workspaces[mode_key])

    def _update_workspace(self) -> None:
        ticket = self.ticket_lookup.get(self.selected_ticket_id)
        workspace = self.workspaces[self.selected_mode]
        workspace.set_ticket(ticket)
        if (
            self._last_result is not None
            and self._last_result_ticket_id == self.selected_ticket_id
            and self._last_result_mode == self.selected_mode
        ):
            workspace.show_evaluation(self._last_result)

    def _emit_evaluation(self, answer_text: str) -> None:
        if not self.selected_ticket_id:
            self.workspaces[self.selected_mode].show_evaluation(
                TrainingEvaluationResult(False, 0, "", [], error="Нет выбранного билета для проверки.")
            )
            return
        self.evaluate_requested.emit(self.selected_ticket_id, self.selected_mode, answer_text)

    def _rebuild_queue(self) -> None:
        self.queue_title.setText(f"Адаптивная очередь ({len(self.snapshot.queue_items)})")
        while self.queue_stack.count():
            item = self.queue_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.queue_buttons.clear()

        if not self.snapshot.queue_items:
            has_tickets = bool(self.snapshot.tickets)
            self.queue_stack.addWidget(
                EmptyStatePanel(
                    "queue",
                    "Адаптивная очередь пуста" if has_tickets else "Очередь ещё не собрана",
                    (
                        "Пока очередь пуста. Выберите билет вручную через селектор справа или сделайте первые тренировочные попытки."
                        if has_tickets
                        else "Сначала импортируйте материалы, чтобы собрать билеты и открыть адаптивную очередь."
                    ),
                    role="subtle-card",
                    primary_action=None
                    if has_tickets
                    else ("Импортировать документ", self.import_requested.emit, "primary", "import"),
                    secondary_action=None
                    if has_tickets
                    else ("Открыть библиотеку", self.open_library_requested.emit, "secondary", "library"),
                )
            )
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

    def _populate_ticket_selector(self) -> None:
        self._suppress_ticket_selector = True
        self.ticket_selector.clear()
        self.ticket_selector.addItem("Выберите билет вручную", "")
        for ticket in self.snapshot.tickets:
            self.ticket_selector.addItem(ticket.title, ticket.ticket_id)
        self._select_ticket_in_combo(self.selected_ticket_id)
        self._suppress_ticket_selector = False

    def _select_ticket_in_combo(self, ticket_id: str) -> None:
        self._suppress_ticket_selector = True
        index = self.ticket_selector.findData(ticket_id)
        self.ticket_selector.setCurrentIndex(max(index, 0))
        self._suppress_ticket_selector = False

    def _ticket_selector_changed(self) -> None:
        if self._suppress_ticket_selector:
            return
        ticket_id = self.ticket_selector.currentData()
        if ticket_id:
            self.select_ticket(ticket_id)

    def _visible_ticket_ids(self) -> list[str]:
        if self.queue_buttons:
            return list(self.queue_buttons.keys())
        return [ticket.ticket_id for ticket in self.snapshot.tickets]

    def _sync_session_empty_state(self) -> None:
        has_selected_ticket = bool(self.ticket_lookup.get(self.selected_ticket_id))
        has_any_ticket = bool(self.snapshot.tickets)
        self.session_empty_state.setVisible(not has_selected_ticket and not has_any_ticket)
        self.workspace_stack.setVisible(has_any_ticket)

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.session_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {colors['text']};")
        self.workspace_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.modes_panel.refresh_theme()
        for ticket_id, button in self.queue_buttons.items():
            button.set_selected(ticket_id == self.selected_ticket_id)
        for workspace in self.workspaces.values():
            refresh = getattr(workspace, "refresh_theme", None)
            if callable(refresh):
                refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        window_width = self.window().width() if self.window() is not None else self.width()
        narrow = window_width < 1320
        self.body.removeWidget(self.queue_card)
        self.body.removeWidget(self.session_card)
        if narrow:
            self.body.addWidget(self.queue_card, 0, 0)
            self.body.addWidget(self.session_card, 1, 0)
            self.body.setColumnStretch(0, 1)
            self.body.setColumnStretch(1, 0)
            self.queue_card.setMinimumWidth(0)
            self.queue_card.setMaximumWidth(16777215)
        else:
            self.body.addWidget(self.queue_card, 0, 0)
            self.body.addWidget(self.session_card, 0, 1)
            self.body.setColumnStretch(0, 4)
            self.body.setColumnStretch(1, 6)
            self.queue_card.setMinimumWidth(320)
            self.queue_card.setMaximumWidth(472)
