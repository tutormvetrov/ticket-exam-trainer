from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from application.ui_data import ReadinessScore, TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap
from ui.components.common import CardFrame, DonutChart
from ui.components.knowledge_graph import KnowledgeGraphWidget
from ui.theme import current_colors


class KnowledgeMapView(QWidget):
    train_requested = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.self_scrolling = True
        self.shadow_color = shadow_color
        self._tickets: list[TicketKnowledgeMap] = []
        self._mastery: dict[str, TicketMasteryBreakdown] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 18, 28, 14)
        header_layout.setSpacing(16)

        title = QLabel("Карта знаний")
        title.setProperty("role", "hero")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.readiness_chart = DonutChart(0, diameter=52)
        self.readiness_chart.setFixedSize(88, 80)
        header_layout.addWidget(self.readiness_chart)

        self.readiness_label = QLabel("Готовность: —")
        self.readiness_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {current_colors()['text']};")
        header_layout.addWidget(self.readiness_label)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(16, 0, 16, 16)
        body.setSpacing(12)

        graph_frame = CardFrame(role="card", shadow_color=shadow_color)
        graph_frame.setMinimumHeight(400)
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(4, 4, 4, 4)
        self.graph = KnowledgeGraphWidget()
        self.graph.node_selected.connect(self._show_detail)
        self.graph.node_deselected.connect(self._clear_detail)
        graph_layout.addWidget(self.graph)
        body.addWidget(graph_frame, 7)

        self.detail_card = CardFrame(role="card", shadow_color=shadow_color)
        self.detail_card.setMinimumWidth(280)
        self.detail_card.setMaximumWidth(380)
        self.detail_layout = QVBoxLayout(self.detail_card)
        self.detail_layout.setContentsMargins(20, 20, 20, 20)
        self.detail_layout.setSpacing(12)

        self.detail_title = QLabel("Выберите билет на графе")
        self.detail_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {current_colors()['text']};")
        self.detail_title.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_title)

        self.detail_meta = QLabel("Кликните на узел, чтобы увидеть детали билета и перейти к тренировке.")
        self.detail_meta.setProperty("role", "body")
        self.detail_meta.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_meta)

        self.detail_concepts = QLabel("")
        self.detail_concepts.setProperty("role", "body")
        self.detail_concepts.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_concepts)

        self.train_button = QPushButton("Тренировать этот билет")
        self.train_button.setProperty("variant", "primary")
        self.train_button.setObjectName("knowledge-map-train")
        self.train_button.clicked.connect(self._emit_train)
        self.train_button.setEnabled(False)
        self.detail_layout.addWidget(self.train_button)

        self.detail_layout.addStretch(1)
        body.addWidget(self.detail_card, 3)
        root.addLayout(body, 1)

        self._selected_ticket_id = ""

    def set_data(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
        readiness: ReadinessScore,
    ) -> None:
        self._tickets = tickets
        self._mastery = mastery
        self.graph.set_data(tickets, mastery)
        self.readiness_chart.animate_to(readiness.percent)
        self.readiness_label.setText(
            f"Готовность: {readiness.percent}% • {readiness.tickets_practiced}/{readiness.tickets_total} билетов"
        )
        self._clear_detail()

    def _show_detail(self, ticket_id: str) -> None:
        self._selected_ticket_id = ticket_id
        ticket = next((t for t in self._tickets if t.ticket_id == ticket_id), None)
        if ticket is None:
            self._clear_detail()
            return

        mastery_item = self._mastery.get(ticket_id)
        confidence = mastery_item.confidence_score if mastery_item else 0.0
        colors = current_colors()

        self.detail_title.setText(ticket.title)
        self.detail_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")

        self.detail_meta.setText(
            f"Готовность: {int(round(confidence * 100))}%\n"
            f"Атомов знаний: {len(ticket.atoms)}\n"
            f"Навыков: {len(ticket.skills)}"
        )

        concept_labels = list({link.concept_label for link in ticket.cross_links_to_other_tickets})
        if concept_labels:
            self.detail_concepts.setText("Связанные понятия: " + ", ".join(concept_labels[:6]))
        else:
            self.detail_concepts.setText("Нет межбилетных связей.")

        self.train_button.setEnabled(True)

    def _clear_detail(self) -> None:
        self._selected_ticket_id = ""
        colors = current_colors()
        self.detail_title.setText("Выберите билет на графе")
        self.detail_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.detail_meta.setText("Кликните на узел, чтобы увидеть детали билета и перейти к тренировке.")
        self.detail_concepts.setText("")
        self.train_button.setEnabled(False)

    def _emit_train(self) -> None:
        if self._selected_ticket_id:
            self.train_requested.emit(self._selected_ticket_id)

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.readiness_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        self.detail_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.graph.refresh_theme()
