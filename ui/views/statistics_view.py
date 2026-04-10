from __future__ import annotations

import json

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from application.ui_data import StateExamStatisticsSnapshot, StatisticsSnapshot, TicketMasteryBreakdown
from ui.components.common import CardFrame
from ui.components.stats_panel import StatisticsPanel


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
    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Статистика")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        self.panel = StatisticsPanel(shadow_color)
        body.addWidget(self.panel, 1)

        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(16)

        self.mastery_card = CardFrame(role="card", shadow_color=shadow_color)
        self.mastery_layout = QVBoxLayout(self.mastery_card)
        self.mastery_layout.setContentsMargins(18, 18, 18, 18)
        self.mastery_layout.setSpacing(10)
        side.addWidget(self.mastery_card)

        self.weak_card = CardFrame(role="card", shadow_color=shadow_color)
        self.weak_layout = QVBoxLayout(self.weak_card)
        self.weak_layout.setContentsMargins(18, 18, 18, 18)
        self.weak_layout.setSpacing(10)
        side.addWidget(self.weak_card)

        self.state_exam_card = CardFrame(role="card", shadow_color=shadow_color)
        self.state_exam_layout = QVBoxLayout(self.state_exam_card)
        self.state_exam_layout.setContentsMargins(18, 18, 18, 18)
        self.state_exam_layout.setSpacing(10)
        side.addWidget(self.state_exam_card)

        body.addLayout(side, 1)
        layout.addLayout(body)

        self.set_data(StatisticsSnapshot(0, 0, 0, 0, []), {}, [], StateExamStatisticsSnapshot())

    def set_data(
        self,
        snapshot: StatisticsSnapshot,
        mastery: dict[str, TicketMasteryBreakdown],
        weak_areas: list,
        state_exam: StateExamStatisticsSnapshot,
    ) -> None:
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

    def set_search_text(self, text: str) -> None:
        return

    def _render_state_exam(self, state_exam: StateExamStatisticsSnapshot) -> None:
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
        subtitle.setStyleSheet("font-size: 13px; font-weight: 700; color: #243548;")
        self.state_exam_layout.addWidget(subtitle)
        for name, value in state_exam.block_scores.items():
            label = QLabel(f"• {name}: {value}%")
            label.setProperty("role", "body")
            self.state_exam_layout.addWidget(label)

        criteria_title = QLabel("Критерии оценки")
        criteria_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #243548;")
        self.state_exam_layout.addWidget(criteria_title)
        if state_exam.criterion_scores:
            for name, value in state_exam.criterion_scores.items():
                label = QLabel(f"• {name}: {value}%")
                label.setProperty("role", "body")
                label.setWordWrap(True)
                self.state_exam_layout.addWidget(label)

        if state_exam.missing_blocks:
            missing_title = QLabel("Пробелы в материалах")
            missing_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #243548;")
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
