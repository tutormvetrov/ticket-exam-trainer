from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QBoxLayout, QLabel, QVBoxLayout, QWidget

from application.ui_data import StateExamStatisticsSnapshot, StatisticsSnapshot, TicketMasteryBreakdown
from ui.components.common import CardFrame, EmptyStatePanel
from ui.components.stats_panel import StatisticsPanel
from ui.theme import current_colors


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


class StatisticsView(QWidget):
    open_library_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self._snapshot = StatisticsSnapshot(0, 0, 0, 0, [])
        self._mastery_data: dict[str, TicketMasteryBreakdown] = {}
        self._weak_areas_data: list = []
        self._state_exam_data = StateExamStatisticsSnapshot()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Статистика")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        self.empty_state = EmptyStatePanel(
            "statistics",
            "Статистика пока пуста",
            "После первых тренировок здесь появятся общий результат, слабые места и детальная разбивка по микронавыкам.",
            shadow_color=shadow_color,
            role="card",
            primary_action=("Открыть библиотеку", self.open_library_requested.emit, "primary", "library"),
        )
        self.empty_state.hide()
        layout.addWidget(self.empty_state)

        self.body = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(16)

        self.panel = StatisticsPanel(shadow_color)
        self.body.addWidget(self.panel, 1)

        self.side_host = QWidget()
        self.side = QVBoxLayout(self.side_host)
        self.side.setContentsMargins(0, 0, 0, 0)
        self.side.setSpacing(16)

        self.mastery_card = CardFrame(role="card", shadow_color=shadow_color)
        self.mastery_layout = QVBoxLayout(self.mastery_card)
        self.mastery_layout.setContentsMargins(18, 18, 18, 18)
        self.mastery_layout.setSpacing(10)
        self.side.addWidget(self.mastery_card)

        self.weak_card = CardFrame(role="card", shadow_color=shadow_color)
        self.weak_layout = QVBoxLayout(self.weak_card)
        self.weak_layout.setContentsMargins(18, 18, 18, 18)
        self.weak_layout.setSpacing(10)
        self.side.addWidget(self.weak_card)

        self.state_exam_card = CardFrame(role="card", shadow_color=shadow_color)
        self.state_exam_layout = QVBoxLayout(self.state_exam_card)
        self.state_exam_layout.setContentsMargins(18, 18, 18, 18)
        self.state_exam_layout.setSpacing(10)
        self.side.addWidget(self.state_exam_card)

        self.body.addWidget(self.side_host, 1)
        self.body_host = QWidget()
        self.body_host.setLayout(self.body)
        layout.addWidget(self.body_host, 1)

        self.set_data(self._snapshot, self._mastery_data, self._weak_areas_data, self._state_exam_data)
        self._apply_responsive_layout()

    def set_data(
        self,
        snapshot: StatisticsSnapshot,
        mastery: dict[str, TicketMasteryBreakdown],
        weak_areas: list,
        state_exam: StateExamStatisticsSnapshot,
    ) -> None:
        self._snapshot = snapshot
        self._mastery_data = mastery
        self._weak_areas_data = weak_areas
        self._state_exam_data = state_exam
        has_activity = bool(snapshot.processed_tickets or snapshot.recent_sessions or mastery or weak_areas or state_exam.active)
        self.body_host.setVisible(has_activity)
        self.empty_state.setVisible(not has_activity)
        self.panel.set_snapshot(snapshot)
        self._render_mastery(mastery)
        self._render_weak_areas(weak_areas)
        self._render_state_exam(state_exam)

    def _render_mastery(self, mastery: dict[str, TicketMasteryBreakdown]) -> None:
        _clear_layout(self.mastery_layout)

        title = QLabel("Сильные и слабые стороны")
        title.setProperty("role", "section-title")
        self.mastery_layout.addWidget(title)

        if not mastery:
            empty = QLabel("Статистика по микронавыкам появится после первых тренировок.")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.mastery_layout.addWidget(empty)
            self.mastery_layout.addStretch(1)
            return

        averages = {
            "Определения": sum(item.definition_mastery for item in mastery.values()) / len(mastery),
            "Структура": sum(item.structure_mastery for item in mastery.values()) / len(mastery),
            "Примеры": sum(item.examples_mastery for item in mastery.values()) / len(mastery),
            "Признаки": sum(item.feature_mastery for item in mastery.values()) / len(mastery),
            "Процессы": sum(item.process_mastery for item in mastery.values()) / len(mastery),
            "Короткий устный": sum(item.oral_short_mastery for item in mastery.values()) / len(mastery),
            "Полный устный": sum(item.oral_full_mastery for item in mastery.values()) / len(mastery),
            "Уточняющие вопросы": sum(item.followup_mastery for item in mastery.values()) / len(mastery),
        }
        for name, value in sorted(averages.items(), key=lambda pair: pair[1]):
            label = QLabel(f"• {name}: {int(round(value * 100))}%")
            label.setProperty("role", "body")
            self.mastery_layout.addWidget(label)
        self.mastery_layout.addStretch(1)

    def _render_weak_areas(self, weak_areas: list) -> None:
        _clear_layout(self.weak_layout)

        title = QLabel("Открытые слабые места")
        title.setProperty("role", "section-title")
        self.weak_layout.addWidget(title)

        if not weak_areas:
            empty = QLabel("Слабые места появятся после оценки ответов.")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.weak_layout.addWidget(empty)
            self.weak_layout.addStretch(1)
            return

        for row in weak_areas[:8]:
            payload = dict(row)
            related = self._json_list(payload.get("related_ticket_ids_json"))
            text = (
                f"• {payload.get('title', 'Без названия')} • критичность {int(float(payload.get('severity', 0)) * 100)}% "
                f"• связанных билетов: {len(related)}"
            )
            label = QLabel(text)
            label.setProperty("role", "body")
            label.setWordWrap(True)
            self.weak_layout.addWidget(label)
        self.weak_layout.addStretch(1)

    def _render_state_exam(self, state_exam: StateExamStatisticsSnapshot) -> None:
        colors = current_colors()
        _clear_layout(self.state_exam_layout)

        title = QLabel("Госэкзаменационный профиль")
        title.setProperty("role", "section-title")
        self.state_exam_layout.addWidget(title)

        if not state_exam.active:
            empty = QLabel("Профиль госэкзамена появится после импорта билетов с профилем «Госэкзамен».")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.state_exam_layout.addWidget(empty)
            self.state_exam_layout.addStretch(1)
            return

        subtitle = QLabel("Готовность по блокам ответа")
        subtitle.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text']};")
        self.state_exam_layout.addWidget(subtitle)
        for name, value in state_exam.block_scores.items():
            label = QLabel(f"• {name}: {value}%")
            label.setProperty("role", "body")
            self.state_exam_layout.addWidget(label)

        criteria_title = QLabel("Критерии оценки")
        criteria_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text']};")
        self.state_exam_layout.addWidget(criteria_title)
        if state_exam.criterion_scores:
            for name, value in state_exam.criterion_scores.items():
                label = QLabel(f"• {name}: {value}%")
                label.setProperty("role", "body")
                label.setWordWrap(True)
                self.state_exam_layout.addWidget(label)

        if state_exam.missing_blocks:
            missing_title = QLabel("Пробелы в материалах")
            missing_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text']};")
            self.state_exam_layout.addWidget(missing_title)
            for name, value in state_exam.missing_blocks.items():
                label = QLabel(f"• {name}: {value} бил.")
                label.setProperty("role", "body")
                self.state_exam_layout.addWidget(label)
        self.state_exam_layout.addStretch(1)

    @staticmethod
    def _json_list(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        return list(json.loads(raw_value))

    def refresh_theme(self) -> None:
        self.panel.refresh_theme()
        self.set_data(self._snapshot, self._mastery_data, self._weak_areas_data, self._state_exam_data)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        direction = QBoxLayout.Direction.TopToBottom if self.width() < 1180 else QBoxLayout.Direction.LeftToRight
        if self.body.direction() != direction:
            self.body.setDirection(direction)
