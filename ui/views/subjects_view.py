from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from domain.models import SubjectData
from ui.components.common import CardFrame, IconBadge, MetricTile
from ui.theme import alpha_color, current_colors, is_dark_palette


class SubjectsView(QWidget):
    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.subjects: list[SubjectData] = []
        self.filtered: list[SubjectData] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Предметы")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        self.summary_card = CardFrame(role="card", shadow_color=self.shadow_color)
        summary_layout = QHBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        summary_title = QLabel("Сводка по предметам")
        summary_title.setProperty("role", "section-title")
        self.summary_body = QLabel("После импорта здесь появятся агрегированные показатели по предметам.")
        self.summary_body.setProperty("role", "body")
        self.summary_body.setWordWrap(True)
        text_box.addWidget(summary_title)
        text_box.addWidget(self.summary_body)
        summary_layout.addLayout(text_box, 1)

        self.summary_subjects = MetricTile("S", "0", "Предметов", "blue", self.shadow_color, compact=True)
        self.summary_subjects.setFixedWidth(120)
        summary_layout.addWidget(self.summary_subjects)
        self.summary_docs = MetricTile("D", "0", "Документов", "green", self.shadow_color, compact=True)
        self.summary_docs.setFixedWidth(120)
        summary_layout.addWidget(self.summary_docs)
        self.summary_tickets = MetricTile("T", "0", "Билетов", "orange", self.shadow_color, compact=True)
        self.summary_tickets.setFixedWidth(120)
        summary_layout.addWidget(self.summary_tickets)
        layout.addWidget(self.summary_card)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        layout.addLayout(self.grid)
        layout.addStretch(1)

    def set_subjects(self, subjects: list[SubjectData]) -> None:
        self.subjects = subjects[:]
        self.filtered = subjects[:]
        total_documents = sum(subject.documents for subject in subjects)
        total_tickets = sum(subject.tickets for subject in subjects)
        self.summary_subjects.set_content("S", str(len(subjects)), "Предметов", "blue")
        self.summary_docs.set_content("D", str(total_documents), "Документов", "green")
        self.summary_tickets.set_content("T", str(total_tickets), "Билетов", "orange")
        self.summary_body.setText(
            "Общий экран по импортированным предметам. Отсюда удобно быстро оценить объём базы и общий прогресс."
            if subjects
            else "После импорта здесь появятся агрегированные показатели по предметам."
        )
        self._rebuild()

    def _rebuild(self) -> None:
        colors = current_colors()
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, subject in enumerate(self.filtered):
            card = CardFrame(role="card", shadow_color=self.shadow_color)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 18, 18, 18)
            card_layout.setSpacing(12)
            badge = IconBadge(subject.name[:2].upper(), alpha_color(subject.accent, 0.22 if is_dark_palette() else 0.14), "#FFFFFF", size=42, radius=13, font_size=12)
            card_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)

            name = QLabel(subject.name)
            name.setProperty("role", "section-title")
            card_layout.addWidget(name)

            meta = QLabel(f"Документов: {subject.documents} • Разделов: {subject.sections} • Билетов: {subject.tickets}")
            meta.setProperty("role", "body")
            card_layout.addWidget(meta)

            progress = QLabel(f"Прогресс: {subject.progress}%")
            progress.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
            card_layout.addWidget(progress)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(subject.progress)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {colors['card_muted']}; border: none; border-radius: 4px; }}"
                f"QProgressBar::chunk {{ background: {subject.accent}; border-radius: 4px; }}"
            )
            card_layout.addWidget(bar)
            self.grid.addWidget(card, index // 2, index % 2)

        if not self.filtered:
            empty = QLabel("Предметы появятся после первого импорта документов.")
            empty.setProperty("role", "body")
            self.grid.addWidget(empty, 0, 0)

    def refresh_theme(self) -> None:
        self.summary_subjects.refresh_theme()
        self.summary_docs.refresh_theme()
        self.summary_tickets.refresh_theme()
        self._rebuild()

    def set_search_text(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self.filtered = self.subjects[:]
        else:
            self.filtered = [subject for subject in self.subjects if query in subject.name.lower()]
        self._rebuild()
