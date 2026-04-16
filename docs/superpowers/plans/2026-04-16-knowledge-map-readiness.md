# Knowledge Map & Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive force-directed knowledge graph with visual polish (glow, gradients, animated layout) and an exam readiness score displayed on library, sidebar, and the new map view.

**Architecture:** `ReadinessService` computes a score from existing mastery data. `KnowledgeGraphWidget` (QGraphicsView) renders tickets as glowing gradient-filled nodes connected by concept edges, using an animated Fruchterman-Reingold layout. `KnowledgeMapView` combines the graph with a detail panel and readiness header. All data already exists — no new DB queries or LLM calls.

**Tech Stack:** Python 3.12+, PySide6 (QGraphicsView, QPropertyAnimation, QRadialGradient, QGraphicsDropShadowEffect), pytest

**Spec:** `docs/superpowers/specs/2026-04-16-knowledge-map-readiness-design.md`

---

### Task 1: Add ReadinessScore DTO and ReadinessService

**Files:**
- Modify: `application/ui_data.py`
- Create: `application/readiness.py`
- Test: `tests/test_scoring_and_review.py`

- [ ] **Step 1: Write test for readiness calculation**

Add to `tests/test_scoring_and_review.py`:

```python
def test_readiness_score_zero_tickets() -> None:
    from application.readiness import ReadinessService
    from application.ui_data import ReadinessScore

    service = ReadinessService()
    score = service.calculate([], {})
    assert isinstance(score, ReadinessScore)
    assert score.percent == 0
    assert score.tickets_total == 0
    assert score.tickets_practiced == 0
    assert score.weakest_area == ""


def test_readiness_score_partial_coverage() -> None:
    from application.readiness import ReadinessService
    from application.ui_data import TicketMasteryBreakdown

    ticket_a = build_ticket("Ticket A", "Content A about definitions and examples.")
    ticket_b = build_ticket("Ticket B", "Content B about processes and stages.")
    ticket_c = build_ticket("Ticket C", "Content C about classification.")

    mastery = {
        ticket_a.ticket_id: TicketMasteryBreakdown(ticket_id=ticket_a.ticket_id, confidence_score=0.8),
        ticket_b.ticket_id: TicketMasteryBreakdown(ticket_id=ticket_b.ticket_id, confidence_score=0.4),
    }

    service = ReadinessService()
    score = service.calculate([ticket_a, ticket_b, ticket_c], mastery)

    assert score.tickets_total == 3
    assert score.tickets_practiced == 2
    assert 0 < score.percent < 100
    assert score.weakest_area != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring_and_review.py::test_readiness_score_zero_tickets -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.readiness'`

- [ ] **Step 3: Add `ReadinessScore` to `application/ui_data.py`**

At the end of the file, add:

```python
@dataclass(slots=True)
class ReadinessScore:
    percent: int
    tickets_total: int
    tickets_practiced: int
    weakest_area: str
```

- [ ] **Step 4: Create `application/readiness.py`**

```python
from __future__ import annotations

from application.ui_data import ReadinessScore, TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap


class ReadinessService:
    def calculate(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
    ) -> ReadinessScore:
        if not tickets:
            return ReadinessScore(percent=0, tickets_total=0, tickets_practiced=0, weakest_area="")

        practiced = [
            t for t in tickets
            if t.ticket_id in mastery and mastery[t.ticket_id].confidence_score > 0
        ]

        if not practiced:
            return ReadinessScore(
                percent=0,
                tickets_total=len(tickets),
                tickets_practiced=0,
                weakest_area="",
            )

        avg_mastery = sum(mastery[t.ticket_id].confidence_score for t in practiced) / len(practiced)
        coverage = len(practiced) / len(tickets)
        percent = int(round(avg_mastery * coverage * 100))

        weakest = min(practiced, key=lambda t: mastery[t.ticket_id].confidence_score)
        weakest_area = weakest.title

        return ReadinessScore(
            percent=max(0, min(100, percent)),
            tickets_total=len(tickets),
            tickets_practiced=len(practiced),
            weakest_area=weakest_area,
        )
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_scoring_and_review.py -k readiness -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add application/ui_data.py application/readiness.py tests/test_scoring_and_review.py
git commit -m "feat: add ReadinessScore DTO and ReadinessService

Computes exam readiness as average_mastery × coverage. Coverage
penalty ensures partial practice doesn't inflate readiness."
```

---

### Task 2: Enhance DonutChart with animation and color gradient

**Files:**
- Modify: `ui/components/common.py` (DonutChart class)

- [ ] **Step 1: Add `animate_to` method and color interpolation to DonutChart**

In `ui/components/common.py`, modify the `DonutChart` class. Add imports at the top of the file (add to existing imports):

```python
from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation
```

Then modify the `DonutChart` class. After the existing `set_percent` method, add:

```python
    def animate_to(self, percent: int) -> None:
        target = max(0, min(100, int(percent)))
        if not hasattr(self, "_animation"):
            self._animation = QPropertyAnimation(self, b"animatedPercent", self)
            self._animation.setDuration(800)
            self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.stop()
        self._animation.setStartValue(self.percent)
        self._animation.setEndValue(target)
        self._animation.start()

    def get_animated_percent(self) -> int:
        return self.percent

    def set_animated_percent(self, value: int) -> None:
        self.percent = max(0, min(100, int(value)))
        self._update_accent_for_percent()
        self.update()

    animatedPercent = Property(int, get_animated_percent, set_animated_percent)

    def _update_accent_for_percent(self) -> None:
        if self.percent <= 30:
            self.accent = QColor("#EF5350")
        elif self.percent <= 60:
            self.accent = QColor("#FFA726")
        elif self.percent <= 80:
            self.accent = QColor("#FFEE58")
        else:
            self.accent = QColor("#66BB6A")
```

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass (DonutChart changes are backward-compatible)

- [ ] **Step 3: Commit**

```bash
git add ui/components/common.py
git commit -m "feat: add animate_to and color gradient to DonutChart

Animated percent transition over 800ms with OutCubic easing.
Accent color auto-updates based on current value: red → orange →
yellow → green."
```

---

### Task 3: Create KnowledgeGraphWidget with force layout and visual polish

This is the core visual component. Large task but self-contained in one new file.

**Files:**
- Create: `ui/components/knowledge_graph.py`

- [ ] **Step 1: Create `ui/components/knowledge_graph.py`**

```python
from __future__ import annotations

import math
import random

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QRadialGradient, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from application.ui_data import TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap
from ui.theme import current_colors


MASTERY_TIERS = [
    (0.0, "#B0BEC5", None),
    (0.01, "#EF5350", "#EF5350"),
    (0.31, "#FFA726", "#FFA726"),
    (0.61, "#FFEE58", "#FFEE58"),
    (0.81, "#66BB6A", "#66BB6A"),
]


def _mastery_color(score: float) -> tuple[str, str | None]:
    result = MASTERY_TIERS[0]
    for threshold, color, glow in MASTERY_TIERS:
        if score >= threshold:
            result = (color, glow)
    return result


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
    train_requested = Signal(str)

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
```

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass (new file, no existing code changed)

- [ ] **Step 3: Commit**

```bash
git add ui/components/knowledge_graph.py
git commit -m "feat: add KnowledgeGraphWidget with force layout and visual polish

Interactive QGraphicsView with TicketNode (gradient fill, glow
effects) and ConceptEdge (hover highlighting). Animated Fruchterman-
Reingold layout runs at 60fps. Mastery-based color scale."
```

---

### Task 4: Create KnowledgeMapView

**Files:**
- Create: `ui/views/knowledge_map_view.py`

- [ ] **Step 1: Create `ui/views/knowledge_map_view.py`**

```python
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

        self.detail_meta = QLabel("")
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
```

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add ui/views/knowledge_map_view.py
git commit -m "feat: add KnowledgeMapView with graph and detail panel

Two-panel layout: interactive graph on the left (70%), ticket detail
panel with train button on the right (30%). Readiness score in header
with animated DonutChart."
```

---

### Task 5: Wire into sidebar, main window, and facade

**Files:**
- Modify: `ui/components/sidebar.py`
- Modify: `ui/main_window.py`
- Modify: `application/facade.py`

- [ ] **Step 1: Add "Карта знаний" to sidebar NAV_ITEMS**

In `ui/components/sidebar.py`, modify `NAV_ITEMS` to insert the new item between "statistics" and "defense":

```python
NAV_ITEMS = [
    ("library", "Библиотека", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ("subjects", "Предметы", QStyle.StandardPixmap.SP_DirHomeIcon),
    ("sections", "Разделы", QStyle.StandardPixmap.SP_DirIcon),
    ("tickets", "Билеты", QStyle.StandardPixmap.SP_FileIcon),
    ("import", "Импорт документов", QStyle.StandardPixmap.SP_ArrowUp),
    ("training", "Тренировка", QStyle.StandardPixmap.SP_MediaPlay),
    ("statistics", "Статистика", QStyle.StandardPixmap.SP_FileDialogInfoView),
    ("knowledge-map", "Карта знаний", QStyle.StandardPixmap.SP_ComputerIcon),
    ("defense", "Подготовка к защите", QStyle.StandardPixmap.SP_DialogHelpButton),
    ("settings", "Настройки", QStyle.StandardPixmap.SP_FileDialogContentsView),
]
```

- [ ] **Step 2: Add readiness label to sidebar**

In `Sidebar.__init__`, after the `self.url_label` widget and before `layout.addWidget(status_card)`, add:

```python
        self.readiness_label = QLabel("Готовность: —")
        self.readiness_label.setProperty("role", "body")
        self.readiness_label.setWordWrap(True)
        status_layout.addWidget(self.readiness_label)
```

Add a public method to set readiness:

```python
    def set_readiness(self, percent: int) -> None:
        self.readiness_label.setText(f"Готовность: {percent}%")
```

- [ ] **Step 3: Add `load_readiness_score` to facade**

In `application/facade.py`, add import at the top:

```python
from application.readiness import ReadinessService
```

Add method to `AppFacade` class:

```python
    def load_readiness_score(self, tickets=None, mastery=None):
        from application.ui_data import ReadinessScore
        resolved_tickets = tickets if tickets is not None else self.load_ticket_maps()
        resolved_mastery = mastery if mastery is not None else self.load_mastery_breakdowns()
        return ReadinessService().calculate(resolved_tickets, resolved_mastery)
```

- [ ] **Step 4: Register KnowledgeMapView in MainWindow**

In `ui/main_window.py`, add the import:

```python
from ui.views.knowledge_map_view import KnowledgeMapView
```

In the `self.views` dict (around line 128-138), add between "statistics" and "defense":

```python
            "knowledge-map": KnowledgeMapView(self.palette_colors["shadow"]),
```

After the views dict, add signal connection:

```python
        self.views["knowledge-map"].train_requested.connect(self._train_from_map)
```

Add the handler method:

```python
    def _train_from_map(self, ticket_id: str) -> None:
        self.switch_view("training")
        self.views["training"].select_ticket(ticket_id)
```

- [ ] **Step 5: Pass data to knowledge map in `_refresh_lightweight_views`**

In `_refresh_lightweight_views` method, after the existing view updates (around line 597), add:

```python
        readiness = self.facade.load_readiness_score(tickets=None, mastery=mastery)
        self.views["knowledge-map"].set_data(
            self.facade.load_ticket_maps(),
            mastery,
            readiness,
        )
        self.sidebar.set_readiness(readiness.percent)
```

Note: `mastery` variable is already available in this method. `load_ticket_maps()` is called because tickets are needed for the graph but aren't stored in a local variable in the lightweight path. For heavy views, tickets are loaded separately. If performance is a concern, this can be optimized later — for now, the call is fast (SQLite, local data).

- [ ] **Step 6: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add ui/components/sidebar.py ui/main_window.py application/facade.py
git commit -m "feat: wire knowledge map into sidebar and main window

Add 'Карта знаний' to sidebar navigation. Register KnowledgeMapView.
Pass ticket/mastery/readiness data on refresh. Add readiness label
to sidebar. Train button navigates to training view."
```

---

### Task 6: Add readiness DonutChart to library view

**Files:**
- Modify: `ui/views/library_view.py`

- [ ] **Step 1: Add readiness chart to library view**

In `ui/views/library_view.py`, add import:

```python
from application.ui_data import ReadinessScore
```

In `LibraryView.__init__`, find a good place in the right-column stats area. Add a readiness DonutChart. Look for where the `StatisticsPanel(compact=True)` is created and add nearby:

```python
        self.readiness_chart = DonutChart(0, diameter=70)
        self.readiness_chart.setFixedSize(106, 100)
```

Add it to the layout near the stats panel. The exact placement depends on the current layout — add it above or below the stats panel in the right column.

Also add import for `DonutChart` if not already imported:
```python
from ui.components.common import CardFrame, DonutChart, IconBadge, file_badge_colors
```

Add a public method:

```python
    def set_readiness(self, readiness: ReadinessScore) -> None:
        self.readiness_chart.animate_to(readiness.percent)
```

- [ ] **Step 2: Wire readiness in MainWindow._refresh_lightweight_views**

In the readiness section added in Task 5, also call:

```python
        self.views["library"].set_readiness(readiness)
```

- [ ] **Step 3: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add ui/views/library_view.py ui/main_window.py
git commit -m "feat: show readiness DonutChart on library view

Animated readiness percentage in the library stats area. Updates
on every view refresh."
```

---

### Task 7: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -q`
Expected: all tests PASS

- [ ] **Step 2: Smoke-test imports**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "import sys; from PySide6.QtWidgets import QApplication; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('MainWindow import OK')"`

Expected: `MainWindow import OK`

- [ ] **Step 3: Verify knowledge map view registered**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "from ui.components.knowledge_graph import KnowledgeGraphWidget; print('KnowledgeGraphWidget import OK')"`

Expected: `KnowledgeGraphWidget import OK`

- [ ] **Step 4: Verify readiness service**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "from application.readiness import ReadinessService; print(ReadinessService().calculate([], {}))"`

Expected: `ReadinessScore(percent=0, tickets_total=0, tickets_practiced=0, weakest_area='')`

- [ ] **Step 5: Final commit (if any fixups needed)**

If any test failures were discovered and fixed, commit the fixes.
