from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from domain.models import DocumentData, SectionData, TicketData
from ui.components.common import CardFrame, IconBadge, TwoColumnRows


class DocumentDetailPanel(CardFrame):
    def __init__(self, shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        self.current_document: DocumentData | None = None

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
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 800;")
        title_box.addWidget(self.title_label)

        self.subject_label = QLabel()
        self.subject_label.setProperty("role", "pill")
        title_box.addWidget(self.subject_label, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addLayout(title_box, 1)
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
        self.status_dot.setStyleSheet("color: #18B06A; font-size: 12px;")
        status_layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setProperty("role", "status-ok")
        status_layout.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        status_layout.addStretch(1)
        self.meta_layout.addWidget(self.status_row)

        tabs = QHBoxLayout()
        tabs.setContentsMargins(0, 4, 0, 0)
        tabs.setSpacing(22)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_group.buttonClicked.connect(self._switch_tab)
        self.tab_buttons: list[QPushButton] = []
        for index, title in enumerate(("Разделы", "Билеты", "Информация")):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("variant", "tab")
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
        layout.addStretch(1)
        return wrapper

    def _switch_tab(self, button: QPushButton) -> None:
        self.stack.setCurrentIndex(self.tab_group.id(button))

    def set_document(self, document: DocumentData) -> None:
        self.current_document = document

        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        badge_color = "#EAF2FF" if document.file_type == "DOCX" else "#FFF0F2"
        badge_fg = "#2E78E6" if document.file_type == "DOCX" else "#D94B63"
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
        self.status_label.setStyleSheet("color: #18B06A; font-size: 14px; font-weight: 700;")
        self.status_dot.setStyleSheet("color: #18B06A; font-size: 12px;")
        self.tab_buttons[1].setText(f"Билеты ({document.tickets_count})")

        self._populate_sections(document.sections)
        self._populate_tickets(document.tickets)
        self.info_title.setText("Информация о документе")
        self.info_text.setText(
            f"Документ относится к предмету «{document.subject}». "
            f"Подготовлено {document.sections_count} разделов и {document.tickets_count} билетов для тренировки."
        )

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
        self.status_label.setStyleSheet("color: #64748B; font-size: 14px; font-weight: 700;")
        self.status_dot.setStyleSheet("color: #94A3B8; font-size: 12px;")
        self.tab_buttons[1].setText("Билеты (0)")
        self._populate_sections([])
        self._populate_tickets([])
        self.info_title.setText("Информация о документе")
        self.info_text.setText("После выбора документа здесь появятся разделы, билеты и метаданные.")

    def _populate_sections(self, sections: list[SectionData]) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, section in enumerate(sections, start=1):
            row = QFrame()
            row.setProperty("role", "table-row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 14, 18, 14)
            row_layout.setSpacing(12)
            title = QLabel(f"{index}. {section.title}")
            title.setStyleSheet("font-size: 14px; font-weight: 600;")
            row_layout.addWidget(title)
            row_layout.addStretch(1)
            count = QLabel(str(section.tickets_count))
            count.setProperty("role", "body")
            row_layout.addWidget(count)
            arrow = QLabel("›")
            arrow.setStyleSheet("font-size: 22px; color: #8FA0B4;")
            row_layout.addWidget(arrow)
            self.sections_layout.addWidget(row)

    def _populate_tickets(self, tickets: list[TicketData]) -> None:
        while self.tickets_layout.count():
            item = self.tickets_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        status_colors = {
            "готов": ("#EAF9F1", "#18B06A"),
            "повторить": ("#FFF4E7", "#F59A23"),
            "в работе": ("#EEF5FF", "#2E78E6"),
        }
        for ticket in tickets:
            row = QFrame()
            row.setProperty("role", "subtle-card")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(12)
            row_layout.addWidget(IconBadge(str(ticket.number), "#F0F4FA", "#526073", size=34, radius=11, font_size=12))

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            title = QLabel(ticket.title)
            title.setStyleSheet("font-size: 14px; font-weight: 700;")
            text_box.addWidget(title)

            bg, fg = status_colors[ticket.status]
            status = QLabel(ticket.status.title())
            status.setStyleSheet(
                f"background: {bg}; color: {fg}; border-radius: 11px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )
            text_box.addWidget(status, 0, Qt.AlignmentFlag.AlignLeft)
            row_layout.addLayout(text_box, 1)
            self.tickets_layout.addWidget(row)
        self.tickets_layout.addStretch(1)
