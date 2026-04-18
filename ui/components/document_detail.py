from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from domain.models import DocumentData, SectionData, TicketData
from ui.components.common import CardFrame, ClickableFrame, EmptyStatePanel, IconBadge, TwoColumnRows
from ui.icons import apply_button_icon
from ui.theme import current_colors


class DocumentDetailPanel(CardFrame):
    delete_document_requested = Signal(str)
    ticket_reader_requested = Signal(str)
    ticket_training_requested = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        self.current_document: DocumentData | None = None
        self._tickets_loaded_for_document_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(14)

        self.badge_holder = QVBoxLayout()
        self.badge_holder.setContentsMargins(0, 0, 0, 0)
        self.badge_holder.setSpacing(0)
        header_row.addLayout(self.badge_holder)
        self.file_badge = None

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {current_colors()['text']};")
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(0)
        title_box.addWidget(self.title_label)

        self.subject_label = QLabel()
        self.subject_label.setProperty("role", "pill")
        self.subject_label.setWordWrap(True)
        title_box.addWidget(self.subject_label, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addLayout(title_box, 1)

        self.delete_button = QPushButton("Удалить")
        self.delete_button.setObjectName("document-detail-delete")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.setToolTip("Удалить документ вместе со всеми билетами, попытками и диалогами.")
        self.delete_button.clicked.connect(self._handle_delete_clicked)
        self.delete_button.hide()
        header_row.addWidget(self.delete_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        self.meta_container = QWidget()
        self.meta_layout = QVBoxLayout(self.meta_container)
        self.meta_layout.setContentsMargins(0, 0, 0, 0)
        self.meta_layout.setSpacing(10)
        layout.addWidget(self.meta_container)
        self.meta_rows = TwoColumnRows([])
        self.meta_layout.addWidget(self.meta_rows)

        self.status_row = QWidget()
        status_layout = QHBoxLayout(self.status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        self.status_dot = QLabel("●")
        status_layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setProperty("role", "status-ok")
        status_layout.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        status_layout.addStretch(1)
        self.meta_layout.addWidget(self.status_row)

        tabs = QHBoxLayout()
        tabs.setContentsMargins(0, 4, 0, 0)
        tabs.setSpacing(14)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_group.buttonClicked.connect(self._switch_tab)
        self.tab_buttons: list[QPushButton] = []
        for index, title in enumerate(("Разделы", "Билеты", "Информация")):
            button = QPushButton(title)
            button.setObjectName(f"document-detail-tab-{index}")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("variant", "tab")
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            tabs.addWidget(button)
            self.tab_group.addButton(button, index)
            self.tab_buttons.append(button)
        tabs.addStretch(1)
        layout.addLayout(tabs)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_sections_view())
        self.stack.addWidget(self._build_tickets_view())
        self.stack.addWidget(self._build_info_view())
        layout.addWidget(self.stack, 1)
        self.tab_buttons[0].setChecked(True)
        self.clear_document()

    def _build_sections_view(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setProperty("role", "subtle-card")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setProperty("role", "table-row")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(12)
        title = QLabel("Раздел")
        title.setProperty("role", "body")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        count = QLabel("Билетов")
        count.setProperty("role", "body")
        header_layout.addWidget(count)
        layout.addWidget(header)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(0)
        layout.addWidget(self.sections_container)
        return wrapper

    def _build_tickets_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tickets_widget = QWidget()
        self.tickets_layout = QVBoxLayout(self.tickets_widget)
        self.tickets_layout.setContentsMargins(0, 0, 0, 0)
        self.tickets_layout.setSpacing(10)
        scroll.setWidget(self.tickets_widget)
        return scroll

    def _build_info_view(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setProperty("role", "subtle-card")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        self.info_title = QLabel()
        self.info_title.setProperty("role", "card-title")
        self.info_text = QLabel()
        self.info_text.setWordWrap(True)
        self.info_text.setProperty("role", "body")
        layout.addWidget(self.info_title)
        layout.addWidget(self.info_text)
        self.info_empty_state = EmptyStatePanel(
            "document",
            "Выберите документ",
            "После выбора документа здесь появятся разделы, билеты и служебная информация по импорту.",
            role="subtle-card",
        )
        layout.addWidget(self.info_empty_state)
        layout.addStretch(1)
        return wrapper

    def _switch_tab(self, button: QPushButton) -> None:
        index = self.tab_group.id(button)
        self.stack.setCurrentIndex(index)
        if index == 1 and self.current_document is not None:
            self._ensure_ticket_rows_loaded()

    def set_document(self, document: DocumentData) -> None:
        self.current_document = document

        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        colors = current_colors()
        badge_color = colors["primary_soft"] if document.file_type == "DOCX" else colors["danger_soft"]
        badge_fg = colors["primary"] if document.file_type == "DOCX" else colors["danger"]
        self.file_badge = IconBadge(document.file_type, badge_color, badge_fg, size=46, radius=14, font_size=11)
        self.badge_holder.addWidget(self.file_badge)

        self.title_label.setText(document.title)
        self.subject_label.setText(document.subject)

        self.meta_layout.removeWidget(self.meta_rows)
        self.meta_rows.setParent(None)
        self.meta_rows.deleteLater()
        self.meta_rows = TwoColumnRows(
            [
                ("Импортирован:", document.imported_at),
                ("Размер:", document.size),
            ]
        )
        self.meta_layout.insertWidget(0, self.meta_rows)
        self.status_label.setText(document.status)
        self.status_label.setStyleSheet(f"color: {colors['success']}; font-size: 14px; font-weight: 700;")
        self.status_dot.setStyleSheet(f"color: {colors['success']}; font-size: 12px;")
        self.tab_buttons[1].setText(f"Билеты ({document.tickets_count})")

        self._populate_sections(document.sections)
        self._tickets_loaded_for_document_id = ""
        if self.stack.currentIndex() == 1:
            self._ensure_ticket_rows_loaded()
        else:
            self._populate_ticket_placeholder(document.tickets_count)
        self.info_title.setText("Информация о документе")
        self.info_text.setText(
            f"Документ относится к предмету «{document.subject}». "
            f"Подготовлено {document.sections_count} разделов и {document.tickets_count} билетов для чтения и тренировки."
        )
        self.info_title.show()
        self.info_text.show()
        self.info_empty_state.hide()
        self.delete_button.show()

    def clear_document(self) -> None:
        self.current_document = None
        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.title_label.setText("Документ не выбран")
        self.subject_label.setText("Нет данных")
        self.meta_layout.removeWidget(self.meta_rows)
        self.meta_rows.setParent(None)
        self.meta_rows.deleteLater()
        self.meta_rows = TwoColumnRows(
            [
                ("Импортирован:", "Нет данных"),
                ("Размер:", "Нет данных"),
            ]
        )
        self.meta_layout.insertWidget(0, self.meta_rows)
        self.status_label.setText("Ожидание выбора")
        self.status_label.setStyleSheet(f"color: {current_colors()['text_secondary']}; font-size: 14px; font-weight: 700;")
        self.status_dot.setStyleSheet(f"color: {current_colors()['text_tertiary']}; font-size: 12px;")
        self.tab_buttons[1].setText("Билеты (0)")
        self._populate_sections([])
        self._tickets_loaded_for_document_id = ""
        self._populate_tickets([])
        self.info_title.hide()
        self.info_text.hide()
        self.info_empty_state.show()
        self.delete_button.hide()

    def refresh_theme(self) -> None:
        if self.current_document is None:
            self.clear_document()
        else:
            self.set_document(self.current_document)

    def _handle_delete_clicked(self) -> None:
        document = self.current_document
        if document is None:
            return
        message = (
            f"Удалить документ «{document.title}»?\n\n"
            f"Это действие нельзя отменить. Будут удалены:\n"
            f"• {document.tickets_count} билет(ов) и все связанные разделы\n"
            "• история попыток и диалогов по этим билетам\n"
            "• отметки слабых мест, привязанные к этим билетам\n\n"
            "Остальные документы в библиотеке не пострадают."
        )
        confirmation = QMessageBox.question(
            self,
            "Удаление документа",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self.delete_document_requested.emit(document.id)

    def _ensure_ticket_rows_loaded(self) -> None:
        if self.current_document is None:
            self._populate_tickets([])
            return
        if self._tickets_loaded_for_document_id == self.current_document.id:
            return
        self._populate_tickets(self.current_document.tickets)
        self._tickets_loaded_for_document_id = self.current_document.id

    def _populate_ticket_placeholder(self, ticket_count: int) -> None:
        while self.tickets_layout.count():
            item = self.tickets_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        hint = QLabel(
            "Список билетов подгрузится при открытии этой вкладки."
            if ticket_count
            else "После импорта здесь появится список билетов."
        )
        if ticket_count:
            hint.setProperty("role", "body")
            hint.setWordWrap(True)
            self.tickets_layout.addWidget(hint)
        else:
            self.tickets_layout.addWidget(
                EmptyStatePanel(
                    "tickets",
                    "Билеты ещё не появились",
                    "После первого импорта здесь сформируется список билетов для просмотра и тренировки.",
                    role="subtle-card",
                )
            )
        self.tickets_layout.addStretch(1)

    def _populate_sections(self, sections: list[SectionData]) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not sections:
            self.sections_layout.addWidget(
                EmptyStatePanel(
                    "sections",
                    "Разделы пока не готовы",
                    "После импорта здесь появится структура документа по разделам и количество билетов в каждом блоке.",
                    role="subtle-card",
                )
            )
            return

        for index, section in enumerate(sections, start=1):
            row = ClickableFrame(role="table-row", shadow=False)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            if section.entry_ticket_id:
                row.clicked.connect(lambda ticket_id=section.entry_ticket_id: self._open_ticket_reader(ticket_id))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 12, 16, 12)
            row_layout.setSpacing(10)

            title = QLabel(f"{index}. {section.title}")
            title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {current_colors()['text']};")
            title.setWordWrap(True)
            title.setMinimumWidth(0)
            row_layout.addWidget(title, 1)

            count = QLabel(str(section.tickets_count))
            count.setProperty("role", "body")
            row_layout.addWidget(count, 0, Qt.AlignmentFlag.AlignVCenter)

            action_button = self._build_action_button("К упражнениям", "training")
            action_button.setEnabled(bool(section.entry_ticket_id))
            action_button.clicked.connect(
                lambda checked=False, ticket_id=section.entry_ticket_id: self._open_ticket_training(ticket_id)
            )
            row_layout.addWidget(action_button, 0, Qt.AlignmentFlag.AlignVCenter)
            self.sections_layout.addWidget(row)

    def _populate_tickets(self, tickets: list[TicketData]) -> None:
        while self.tickets_layout.count():
            item = self.tickets_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not tickets:
            self.tickets_layout.addWidget(
                EmptyStatePanel(
                    "tickets",
                    "Выберите документ с билетами",
                    "После выбора документа здесь появятся билеты, их статус и готовность к тренировке.",
                    role="subtle-card",
                )
            )
            self.tickets_layout.addStretch(1)
            return

        colors = current_colors()
        status_colors = {
            "готов": (colors["success_soft"], colors["success"]),
            "повторить": (colors["warning_soft"], colors["warning"]),
            "в работе": (colors["primary_soft"], colors["primary"]),
        }
        for ticket in tickets:
            row = ClickableFrame(role="subtle-card", shadow=False)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            if ticket.ticket_id:
                row.clicked.connect(lambda ticket_id=ticket.ticket_id: self._open_ticket_reader(ticket_id))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(12)
            row_layout.addWidget(IconBadge(str(ticket.number), colors["card_muted"], colors["text_secondary"], size=34, radius=11, font_size=12))

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            title = QLabel(ticket.title)
            title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
            title.setWordWrap(True)
            text_box.addWidget(title)

            if ticket.summary:
                summary = QLabel(ticket.summary)
                summary.setWordWrap(True)
                summary.setProperty("role", "body")
                text_box.addWidget(summary)

            bg, fg = status_colors.get(ticket.status, (colors["primary_soft"], colors["primary"]))
            status = QLabel(ticket.status.title())
            status.setStyleSheet(
                f"background: {bg}; color: {fg}; border-radius: 11px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )
            text_box.addWidget(status, 0, Qt.AlignmentFlag.AlignLeft)
            row_layout.addLayout(text_box, 1)

            action_col = QVBoxLayout()
            action_col.setContentsMargins(0, 0, 0, 0)
            action_col.setSpacing(8)

            read_button = self._build_action_button("Читать", "document")
            read_button.setEnabled(bool(ticket.ticket_id))
            read_button.clicked.connect(lambda checked=False, ticket_id=ticket.ticket_id: self._open_ticket_reader(ticket_id))
            action_col.addWidget(read_button)

            train_button = self._build_action_button("К упражнениям", "training")
            train_button.setEnabled(bool(ticket.ticket_id))
            train_button.clicked.connect(
                lambda checked=False, ticket_id=ticket.ticket_id: self._open_ticket_training(ticket_id)
            )
            action_col.addWidget(train_button)
            row_layout.addLayout(action_col)
            self.tickets_layout.addWidget(row)
        self.tickets_layout.addStretch(1)

    def _build_action_button(self, text: str, icon_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("variant", "secondary")
        button.setMinimumWidth(136)
        apply_button_icon(button, icon_name, size=16)
        return button

    def _open_ticket_reader(self, ticket_id: str) -> None:
        if ticket_id:
            self.ticket_reader_requested.emit(ticket_id)

    def _open_ticket_training(self, ticket_id: str) -> None:
        if ticket_id:
            self.ticket_training_requested.emit(ticket_id)
