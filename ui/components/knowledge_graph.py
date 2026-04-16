from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QRadialGradient, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from application.ui_data import TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap
from ui.theme import current_colors, mastery_band_color


def _mastery_color(score: float) -> tuple[str, str | None]:
    """Вернуть (fill, glow) для узла графа знаний.

    Тест по диапазонам тот же, что в DonutChart: 0 → нейтральный, затем
    danger → warning → midtone → success. Цвета берутся из темы, чтобы
    и light, и dark читались одинаково.
    """
    if score <= 0:
        return current_colors()["text_tertiary"], None
    percent = int(round(score * 100))
    hex_color = mastery_band_color(percent)
    return hex_color, hex_color


def _abbreviation(title: str) -> str:
    words = title.split()[:2]
    return "".join(w[0].upper() for w in words if w) or "?"


def _node_diameter(atom_count: int) -> float:
    return max(24.0, min(56.0, 20.0 + atom_count * 4.0))


class TicketNode(QGraphicsEllipseItem):
    def __init__(self, ticket_id: str, title: str, atom_count: int, mastery_score: float) -> None:
        diameter = _node_diameter(atom_count)
        super().__init__(-diameter / 2, -diameter / 2, diameter, diameter)
        self.ticket_id = ticket_id
        self.title = title
        self.diameter = diameter
        self.mastery_score = mastery_score
        self.edges: list[ConceptEdge] = []
        self.vx = 0.0
        self.vy = 0.0

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(2)

        mastery_pct = int(round(mastery_score * 100))
        self.setToolTip(f"{title}\nГотовность: {mastery_pct}%")

        self._apply_visual(mastery_score)

        label = QGraphicsSimpleTextItem(_abbreviation(title), self)
        label.setFont(QFont("Segoe UI", max(8, int(diameter * 0.22)), 700))
        label.setBrush(QBrush(QColor("#FFFFFF")))
        label_rect = label.boundingRect()
        label.setPos(-label_rect.width() / 2, -label_rect.height() / 2)

    def _apply_visual(self, score: float) -> None:
        color_hex, glow_hex = _mastery_color(score)
        base = QColor(color_hex)

        gradient = QRadialGradient(0, 0, self.diameter / 2)
        gradient.setColorAt(0.0, base.lighter(140))
        gradient.setColorAt(1.0, base.darker(120))
        self.setBrush(QBrush(gradient))
        self.setPen(QPen(base.darker(140), 1.5))

        if glow_hex:
            glow = QGraphicsDropShadowEffect()
            glow.setColor(QColor(glow_hex))
            glow.setBlurRadius(16)
            glow.setOffset(0, 0)
            self.setGraphicsEffect(glow)

    def hoverEnterEvent(self, event) -> None:
        for edge in self.edges:
            edge.set_highlighted(True)
        scene = self.scene()
        if scene is not None:
            for item in scene.items():
                if isinstance(item, ConceptEdge) and item not in self.edges:
                    item.set_highlighted(False)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        scene = self.scene()
        if scene is not None:
            for item in scene.items():
                if isinstance(item, ConceptEdge):
                    item.set_default()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_positions()
        return super().itemChange(change, value)


class ConceptEdge(QGraphicsLineItem):
    def __init__(self, source: TicketNode, target: TicketNode, concept_label: str, weight: int = 1) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.concept_label = concept_label
        self.weight = weight
        self.setToolTip(concept_label)
        self.setZValue(1)
        self._default_width = max(0.8, min(2.5, 0.5 + weight * 0.5))
        self.set_default()
        self.update_positions()
        source.edges.append(self)
        target.edges.append(self)

    def update_positions(self) -> None:
        self.setLine(
            self.source.pos().x(), self.source.pos().y(),
            self.target.pos().x(), self.target.pos().y(),
        )

    def set_highlighted(self, highlighted: bool) -> None:
        colors = current_colors()
        if highlighted:
            color_hex, _ = _mastery_color(self.source.mastery_score)
            self.setPen(QPen(QColor(color_hex), 2.5, Qt.PenStyle.SolidLine))
            self.setOpacity(1.0)
        else:
            self.setPen(QPen(QColor(colors["border"]), self._default_width, Qt.PenStyle.SolidLine))
            self.setOpacity(0.15)

    def set_default(self) -> None:
        colors = current_colors()
        self.setPen(QPen(QColor(colors["border"]), self._default_width, Qt.PenStyle.SolidLine))
        self.setOpacity(0.4)


def _run_force_iteration(
    nodes: list[TicketNode],
    edges: list[ConceptEdge],
    k: float,
    temperature: float,
) -> None:
    for node in nodes:
        node.vx = 0.0
        node.vy = 0.0

    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            dx = a.pos().x() - b.pos().x()
            dy = a.pos().y() - b.pos().y()
            dist = max(math.sqrt(dx * dx + dy * dy), 1.0)
            force = (k * k) / dist
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            a.vx += fx
            a.vy += fy
            b.vx -= fx
            b.vy -= fy

    for edge in edges:
        dx = edge.target.pos().x() - edge.source.pos().x()
        dy = edge.target.pos().y() - edge.source.pos().y()
        dist = max(math.sqrt(dx * dx + dy * dy), 1.0)
        force = (dist * dist) / k
        fx = (dx / dist) * force
        fy = (dy / dist) * force
        edge.source.vx += fx
        edge.source.vy += fy
        edge.target.vx -= fx
        edge.target.vy -= fy

    for node in nodes:
        mag = math.sqrt(node.vx * node.vx + node.vy * node.vy)
        if mag > 0:
            capped = min(mag, temperature)
            node.setPos(
                node.pos().x() + (node.vx / mag) * capped,
                node.pos().y() + (node.vy / mag) * capped,
            )

    for edge in edges:
        edge.update_positions()


class KnowledgeGraphWidget(QGraphicsView):
    node_selected = Signal(str)
    node_deselected = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(self.renderHints().Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._nodes: list[TicketNode] = []
        self._edges: list[ConceptEdge] = []
        self._node_map: dict[str, TicketNode] = {}
        self._selected_id: str = ""
        self._zoom_level: float = 1.0

        self._layout_timer = QTimer(self)
        self._layout_timer.setInterval(16)
        self._layout_timer.timeout.connect(self._layout_tick)
        self._layout_iteration = 0
        self._layout_max = 100
        self._layout_k = 120.0
        self._layout_temperature = 0.0

    def set_data(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
    ) -> None:
        self._scene.clear()
        self._nodes.clear()
        self._edges.clear()
        self._node_map.clear()
        self._selected_id = ""

        if not tickets:
            return

        rng = random.Random(42)
        area = max(400, len(tickets) * 80)

        for ticket in tickets:
            score = mastery.get(ticket.ticket_id)
            confidence = score.confidence_score if score else 0.0
            node = TicketNode(ticket.ticket_id, ticket.title, len(ticket.atoms), confidence)
            node.setPos(rng.uniform(-area / 2, area / 2), rng.uniform(-area / 2, area / 2))
            self._scene.addItem(node)
            self._nodes.append(node)
            self._node_map[ticket.ticket_id] = node

        edge_counts: dict[tuple[str, str], int] = {}
        edge_labels: dict[tuple[str, str], str] = {}
        for ticket in tickets:
            for link in ticket.cross_links_to_other_tickets:
                for related_id in link.related_ticket_ids:
                    if related_id == ticket.ticket_id:
                        continue
                    pair = tuple(sorted([ticket.ticket_id, related_id]))
                    edge_counts[pair] = edge_counts.get(pair, 0) + 1
                    edge_labels.setdefault(pair, link.concept_label)

        for (id_a, id_b), count in edge_counts.items():
            node_a = self._node_map.get(id_a)
            node_b = self._node_map.get(id_b)
            if node_a and node_b:
                edge = ConceptEdge(node_a, node_b, edge_labels.get((id_a, id_b), ""), count)
                self._scene.addItem(edge)
                self._edges.append(edge)

        self._layout_k = math.sqrt(area * area / max(len(self._nodes), 1))
        self._layout_temperature = area / 4.0
        self._layout_iteration = 0
        self._layout_timer.start()

    def _layout_tick(self) -> None:
        if self._layout_iteration >= self._layout_max or not self._nodes:
            self._layout_timer.stop()
            return
        cooling = 1.0 - (self._layout_iteration / self._layout_max)
        temp = self._layout_temperature * cooling
        _run_force_iteration(self._nodes, self._edges, self._layout_k, temp)
        self._layout_iteration += 1

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._zoom_level *= factor
        self._zoom_level = max(0.2, min(5.0, self._zoom_level))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if isinstance(item, TicketNode):
            self._selected_id = item.ticket_id
            self.node_selected.emit(item.ticket_id)
        elif isinstance(item, QGraphicsSimpleTextItem) and isinstance(item.parentItem(), TicketNode):
            node = item.parentItem()
            self._selected_id = node.ticket_id
            self.node_selected.emit(node.ticket_id)
        else:
            if self._selected_id:
                self._selected_id = ""
                self.node_deselected.emit()
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        for edge in self._edges:
            edge.set_default()
