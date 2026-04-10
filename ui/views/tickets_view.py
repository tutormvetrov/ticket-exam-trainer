from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from application.ui_data import TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap
from ui.components.common import CardFrame, ClickableFrame, IconBadge


class TicketListItem(ClickableFrame):
    clicked_ticket = Signal(str)

    def __init__(self, ticket: TicketKnowledgeMap) -> None:
        super().__init__(role="document-item", shadow=False)
        self.ticket = ticket
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        top.addWidget(IconBadge(str(len(ticket.atoms)), "#EEF5FF", "#2E78E6", size=34, radius=11, font_size=11))
        title = QLabel(ticket.title)
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        title.setWordWrap(True)
        top.addWidget(title, 1)
        layout.addLayout(top)

        meta = QLabel(
            f"Атомов: {len(ticket.atoms)} • Навыков: {len(ticket.skills)} • Сложность: {ticket.difficulty}"
        )
        meta.setProperty("role", "body")
        meta.setWordWrap(True)
        layout.addWidget(meta)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_ticket.emit(self.ticket.ticket_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class TicketsView(QWidget):
    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.tickets: list[TicketKnowledgeMap] = []
        self.filtered: list[TicketKnowledgeMap] = []
        self.mastery: dict[str, TicketMasteryBreakdown] = {}
        self.weak_areas: list[dict[str, str]] = []
        self.current_ticket_id = ""
        self.list_items: dict[str, TicketListItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Билеты")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        self.left_card = CardFrame(role="card", shadow_color=shadow_color)
        self.left_card.setFixedWidth(360)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        self.counter_label = QLabel("Карта билетов")
        self.counter_label.setProperty("role", "card-title")
        left_layout.addWidget(self.counter_label)

        self.ticket_list = QVBoxLayout()
        self.ticket_list.setContentsMargins(0, 0, 0, 0)
        self.ticket_list.setSpacing(10)
        left_layout.addLayout(self.ticket_list)
        left_layout.addStretch(1)
        body.addWidget(self.left_card)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_widget = QWidget()
        self.detail_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(16)
        self.detail_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.detail_scroll.setWidget(self.detail_widget)
        body.addWidget(self.detail_scroll, 1)
        layout.addLayout(body, 1)

        self._render_placeholder()

    def set_data(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
        weak_areas: list,
    ) -> None:
        self.tickets = tickets[:]
        self.filtered = tickets[:]
        self.mastery = mastery
        self.weak_areas = [dict(row) for row in weak_areas]
        self._rebuild_list()
        if self.filtered:
            selected = self.current_ticket_id if self.current_ticket_id in {ticket.ticket_id for ticket in self.filtered} else self.filtered[0].ticket_id
            self._select_ticket(selected)
        else:
            self._render_placeholder()

    def _rebuild_list(self) -> None:
        self.counter_label.setText(f"Карта билетов ({len(self.filtered)})")
        while self.ticket_list.count():
            item = self.ticket_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.list_items.clear()

        if not self.filtered:
            empty = QLabel("Билеты появятся после импорта документов.")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.ticket_list.addWidget(empty)
            return

        for ticket in self.filtered:
            item = TicketListItem(ticket)
            item.clicked_ticket.connect(self._select_ticket)
            self.ticket_list.addWidget(item)
            self.list_items[ticket.ticket_id] = item

    def _select_ticket(self, ticket_id: str) -> None:
        self.current_ticket_id = ticket_id
        for item_id, item in self.list_items.items():
            item.set_selected(item_id == ticket_id)
        for ticket in self.filtered:
            if ticket.ticket_id == ticket_id:
                self._render_ticket(ticket)
                return
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(10)
        title = QLabel("Детали билета")
        title.setProperty("role", "section-title")
        body = QLabel("Выберите билет слева, чтобы увидеть карту ответа, атомы знания, навыки, слабые места и межбилетные связи.")
        body.setProperty("role", "body")
        body.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(body)
        self.detail_layout.addWidget(card)
        self.detail_layout.addStretch(1)
        self.detail_scroll.verticalScrollBar().setValue(0)

    def _render_ticket(self, ticket: TicketKnowledgeMap) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.detail_layout.addWidget(self._hero_card(ticket))
        self.detail_layout.addWidget(self._mastery_card(ticket))
        self.detail_layout.addWidget(self._atoms_card(ticket))
        self.detail_layout.addWidget(self._weakness_card(ticket))
        self.detail_layout.addWidget(self._links_card(ticket))
        self.detail_layout.addWidget(self._prompts_card(ticket))
        self.detail_layout.addStretch(1)
        self.detail_scroll.verticalScrollBar().setValue(0)

    def _hero_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel(ticket.title)
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta = QLabel(
            f"Сложность: {ticket.difficulty} • Устный ответ: {ticket.estimated_oral_time_sec} сек. • Уверенность структуры: {int(ticket.source_confidence * 100)}%"
        )
        meta.setProperty("role", "body")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        summary = QLabel(ticket.canonical_answer_summary or "Краткое каноническое резюме пока не сформировано.")
        summary.setWordWrap(True)
        summary.setProperty("role", "body")
        layout.addWidget(summary)
        return card

    def _mastery_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        profile = self.mastery.get(ticket.ticket_id, TicketMasteryBreakdown(ticket.ticket_id))
        rows = [
            ("Определения", profile.definition_mastery),
            ("Структура", profile.structure_mastery),
            ("Примеры", profile.examples_mastery),
            ("Признаки", profile.feature_mastery),
            ("Процессы", profile.process_mastery),
            ("Короткий устный", profile.oral_short_mastery),
            ("Полный устный", profile.oral_full_mastery),
            ("Follow-up", profile.followup_mastery),
        ]

        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("Профиль микронавыков")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        overall = QLabel(f"Общая уверенность: {int(profile.confidence_score * 100)}%")
        overall.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(overall)

        for label_text, value in rows:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)
            label = QLabel(label_text)
            label.setFixedWidth(140)
            row_layout.addWidget(label)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(round(value * 100)))
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setStyleSheet(
                "QProgressBar { background: #EEF3F8; border: none; border-radius: 5px; }"
                "QProgressBar::chunk { background: #2E78E6; border-radius: 5px; }"
            )
            row_layout.addWidget(bar, 1)
            percent = QLabel(f"{int(round(value * 100))}%")
            percent.setStyleSheet("font-size: 13px; font-weight: 700;")
            row_layout.addWidget(percent)
            layout.addWidget(row)
        return card

    def _atoms_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Карта ответа")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        for atom in ticket.atoms[:8]:
            row = QFrame()
            row.setProperty("role", "subtle-card")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(6)
            chip = QLabel(atom.type.value.replace("_", " "))
            chip.setStyleSheet(
                "background: #EEF5FF; color: #2E78E6; border-radius: 11px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
            )
            row_layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignLeft)
            label = QLabel(atom.label)
            label.setStyleSheet("font-size: 14px; font-weight: 700;")
            row_layout.addWidget(label)
            text = QLabel(atom.text)
            text.setWordWrap(True)
            text.setProperty("role", "body")
            row_layout.addWidget(text)
            layout.addWidget(row)
        return card

    def _weakness_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Слабые места")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        related = []
        for row in self.weak_areas:
            related_ids = self._json_list(row.get("related_ticket_ids_json"))
            if row.get("reference_id") == ticket.ticket_id or ticket.ticket_id in related_ids:
                related.append(row)

        if not related:
            empty = QLabel("По этому билету ещё нет зафиксированных слабых мест.")
            empty.setProperty("role", "body")
            layout.addWidget(empty)
            return card

        for row in related[:6]:
            item = QLabel(f"• {row.get('title', 'Без названия')} ({int(float(row.get('severity', 0)) * 100)}%)")
            item.setWordWrap(True)
            item.setProperty("role", "body")
            layout.addWidget(item)
        return card

    def _links_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Межбилетные связи")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        if not ticket.cross_links_to_other_tickets:
            empty = QLabel("Связанные концепты пока не выявлены.")
            empty.setProperty("role", "body")
            layout.addWidget(empty)
            return card

        for link in ticket.cross_links_to_other_tickets[:5]:
            text = QLabel(
                f"• {link.concept_label} • связанных билетов: {len(link.related_ticket_ids)} • сила: {int(link.strength * 100)}%"
            )
            text.setProperty("role", "body")
            text.setWordWrap(True)
            layout.addWidget(text)
        return card

    def _prompts_card(self, ticket: TicketKnowledgeMap) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Вопросы экзаменатора")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        prompts = ticket.examiner_prompts or []
        if not prompts:
            empty = QLabel("Уточняющие вопросы ещё не подготовлены.")
            empty.setProperty("role", "body")
            layout.addWidget(empty)
            return card

        for prompt in prompts[:4]:
            text = QLabel(f"• {prompt.text}")
            text.setWordWrap(True)
            text.setProperty("role", "body")
            layout.addWidget(text)
        return card

    def set_search_text(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self.filtered = self.tickets[:]
        else:
            self.filtered = [
                ticket
                for ticket in self.tickets
                if query in ticket.title.lower() or query in ticket.canonical_answer_summary.lower()
            ]
        self._rebuild_list()
        if self.filtered:
            self._select_ticket(self.filtered[0].ticket_id)
        else:
            self._render_placeholder()

    @staticmethod
    def _json_list(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        return list(json.loads(raw_value))
