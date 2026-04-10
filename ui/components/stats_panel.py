from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout, QComboBox, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from application.ui_data import StatisticsSnapshot
from domain.models import SessionData
from ui.components.common import CardFrame, DonutChart, MetricTile, ScoreBadge


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


class StatisticsPanel(QWidget):
    def __init__(self, shadow_color, compact: bool = False) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.snapshot = StatisticsSnapshot(0, 0, 0, 0, [])
        self.compact = compact
        self.max_recent_rows = 3 if compact else 4

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18 if compact else 16)

        overall = CardFrame(role="card", shadow_color=shadow_color, shadow=not compact)
        overall.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        overall.setMinimumHeight(304 if compact else 382)
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(0, 0, 0, 0)
        overall_layout.setSpacing(0)

        header = QWidget()
        self.header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header_layout.setContentsMargins(12 if compact else 16, 12 if compact else 16, 12 if compact else 16, 8 if compact else 10)
        self.header_layout.setSpacing(10)
        self.header_title = QLabel("Общая статистика")
        self.header_title.setProperty("role", "card-title")
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addStretch(1)
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(["Все предметы"])
        self.subject_combo.setMaximumWidth(132 if compact else 152)
        self.header_layout.addWidget(self.subject_combo)
        header.setLayout(self.header_layout)
        overall_layout.addWidget(header)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #E9EEF5;")
        overall_layout.addWidget(line)

        body = QVBoxLayout()
        body.setContentsMargins(12 if compact else 14, 12 if compact else 10, 12 if compact else 14, 14 if compact else 12)
        body.setSpacing(10 if compact else 10)
        self.chart = DonutChart(0, diameter=70 if compact else 96)
        self.chart.setFixedSize(118 if compact else 132, 92 if compact else 126)
        body.addWidget(self.chart, 0, Qt.AlignmentFlag.AlignHCenter)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10 if compact else 10)
        grid.setVerticalSpacing(10 if compact else 10)

        processed_label = "Билетов" if compact else "Отработано билетов"
        self.processed_tile = MetricTile("OK", "0", processed_label, "blue", shadow_color, compact=compact)
        self.processed_tile.setFixedHeight(58 if compact else 88)
        grid.addWidget(self.processed_tile, 0, 0)

        weak_label = "Слабых мест" if compact else "Слабых мест"
        self.weak_tile = MetricTile("!", "0", weak_label, "orange", shadow_color, compact=compact)
        self.weak_tile.setFixedHeight(58 if compact else 88)
        grid.addWidget(self.weak_tile, 0, 1)

        sessions_label = "За неделю" if compact else "Сессий за неделю"
        self.sessions_tile = MetricTile("7D", "0", sessions_label, "slate", shadow_color, compact=compact)
        self.sessions_tile.setFixedHeight(52 if compact else 74)
        grid.addWidget(self.sessions_tile, 1, 0, 1, 2)
        body.addLayout(grid)
        overall_layout.addLayout(body)
        layout.addWidget(overall)

        recent = CardFrame(role="card", shadow_color=shadow_color, shadow=not compact)
        recent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        recent.setMinimumHeight(198 if compact else 240)
        recent_layout = QVBoxLayout(recent)
        recent_layout.setContentsMargins(14 if compact else 16, 14 if compact else 16, 14 if compact else 16, 14 if compact else 16)
        recent_layout.setSpacing(10 if compact else 8)

        recent_header = QHBoxLayout()
        recent_header.setContentsMargins(0, 0, 0, 0)
        recent_title = QLabel("Последние сессии")
        recent_title.setProperty("role", "card-title")
        recent_header.addWidget(recent_title)
        recent_header.addStretch(1)
        more = QLabel("Все →")
        more.setStyleSheet("color: #2E78E6; font-size: 13px; font-weight: 600;")
        recent_header.addWidget(more)
        recent_layout.addLayout(recent_header)

        self.recent_rows = QVBoxLayout()
        self.recent_rows.setContentsMargins(0, 0, 0, 0)
        self.recent_rows.setSpacing(6 if compact else 8)
        recent_layout.addLayout(self.recent_rows)
        recent_layout.addStretch(1)
        layout.addWidget(recent)

        self.set_snapshot(self.snapshot)

    def set_snapshot(self, snapshot: StatisticsSnapshot) -> None:
        self.snapshot = snapshot
        self.chart.set_percent(snapshot.average_score)
        self.processed_tile.set_content("OK", str(snapshot.processed_tickets), "Билетов" if self.compact else "Отработано билетов", "blue")
        self.weak_tile.set_content("!", str(snapshot.weak_areas), "Слабых мест", "orange")
        self.sessions_tile.set_content("7D", str(snapshot.sessions_week), "За неделю" if self.compact else "Сессий за неделю", "slate")
        _clear_layout(self.recent_rows)

        sessions = snapshot.recent_sessions or [SessionData("Нет данных", "Сессии ещё не запускались", 0, "danger")]
        for session in sessions[: self.max_recent_rows]:
            self.recent_rows.addWidget(self._session_row(session))

    def _session_row(self, session: SessionData) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10 if self.compact else 12)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2 if self.compact else 3)
        title = QLabel(session.title)
        title.setStyleSheet(f"font-size: {13 if self.compact else 14}px; font-weight: 700;")
        title.setWordWrap(True)
        title.setMaximumHeight(40 if self.compact else 40)
        meta = QLabel(session.timestamp)
        meta.setProperty("role", "body")
        text_box.addWidget(title)
        text_box.addWidget(meta)
        layout.addLayout(text_box, 1)
        layout.addWidget(ScoreBadge(session.score, session.tone), 0, Qt.AlignmentFlag.AlignTop)
        return row

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self.compact:
            narrow = self.width() < 300
            direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
            if self.header_layout.direction() != direction:
                self.header_layout.setDirection(direction)
                self.subject_combo.setMaximumWidth(16777215 if narrow else 132)
        super().resizeEvent(event)
