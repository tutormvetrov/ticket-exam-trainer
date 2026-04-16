from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from application.ui_data import ReviewVerdict
from ui.theme import current_colors


STATUS_ICONS = {"covered": "✓", "partial": "◐", "missing": "✗"}
STATUS_COLORS_KEY = {"covered": "success", "partial": "warning", "missing": "danger"}


class ReviewVerdictWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_verdict(self, verdict: ReviewVerdict) -> None:
        self._clear()
        colors = current_colors()

        header = QLabel(f"Рецензия: {verdict.overall_score}% — {verdict.overall_comment}")
        header.setWordWrap(True)
        header.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {colors['text']};")
        self._layout.addWidget(header)

        for tv in verdict.thesis_verdicts:
            card = self._build_thesis_card(tv, colors)
            self._layout.addWidget(card)

        if verdict.strengths:
            self._layout.addWidget(self._build_section("Сильные стороны", verdict.strengths, colors))
        if verdict.recommendations:
            self._layout.addWidget(self._build_section("Рекомендации", verdict.recommendations, colors))
        if verdict.structure_notes:
            self._layout.addWidget(self._build_section("Замечания по структуре", verdict.structure_notes, colors))

    def _build_thesis_card(self, tv, colors: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("ThesisVerdictCard")
        color_key = STATUS_COLORS_KEY.get(tv.status, "danger")
        border_color = colors.get(color_key, colors["border"])
        card.setStyleSheet(
            f"QFrame#ThesisVerdictCard {{ background: {colors['card_soft']}; "
            f"border-left: 4px solid {border_color}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        icon = QLabel(STATUS_ICONS.get(tv.status, "?"))
        icon.setStyleSheet(f"font-size: 16px; color: {border_color};")
        icon.setFixedWidth(20)
        top.addWidget(icon)

        label = QLabel(tv.thesis_label)
        label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        label.setWordWrap(True)
        top.addWidget(label, 1)
        layout.addLayout(top)

        if tv.comment:
            comment = QLabel(tv.comment)
            comment.setProperty("role", "body")
            comment.setWordWrap(True)
            layout.addWidget(comment)

        if tv.student_excerpt:
            excerpt = QLabel(f"«{tv.student_excerpt}»")
            excerpt.setStyleSheet(f"font-size: 12px; font-style: italic; color: {colors['text_tertiary']};")
            excerpt.setWordWrap(True)
            layout.addWidget(excerpt)

        return card

    def _build_section(self, title: str, items: list[str], colors: dict) -> QFrame:
        section = QFrame()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)

        heading = QLabel(title)
        heading.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text_secondary']};")
        layout.addWidget(heading)

        for item in items[:5]:
            line = QLabel(f"• {item}")
            line.setProperty("role", "body")
            line.setWordWrap(True)
            layout.addWidget(line)

        return section

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh_theme(self) -> None:
        pass  # Rebuilt on each set_verdict call
