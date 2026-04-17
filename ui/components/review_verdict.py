from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from application.ui_data import ReviewVerdict
from ui.components.common import CardFrame, OrnamentalDivider
from ui.theme import current_colors


STATUS_COLORS_KEY = {"covered": "success", "partial": "warning", "missing": "danger"}
STATUS_TEXT = {"covered": "OK", "partial": "PART", "missing": "MISS"}
STATUS_STATE = {"covered": "correct", "partial": "partial", "missing": "incorrect"}


class ReviewVerdictWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._verdict: ReviewVerdict | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.card = CardFrame(role="atelier", shadow=False, accent_strip="moss")
        root.addWidget(self.card)
        self._layout = QVBoxLayout(self.card)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(10)

    def set_verdict(self, verdict: ReviewVerdict) -> None:
        self._verdict = verdict
        self._clear()
        colors = current_colors()

        header = QLabel(f"Рецензия: {verdict.overall_score}%")
        header.setProperty("role", "card-title")
        header.setWordWrap(True)
        self._layout.addWidget(header)

        if verdict.overall_comment:
            summary = QLabel(verdict.overall_comment)
            summary.setProperty("role", "subtitle-italic")
            summary.setWordWrap(True)
            self._layout.addWidget(summary)

        for tv in verdict.thesis_verdicts:
            self._layout.addWidget(OrnamentalDivider())
            self._layout.addWidget(self._build_thesis_card(tv, colors))

        if verdict.strengths:
            self._layout.addWidget(OrnamentalDivider())
            self._layout.addWidget(self._build_section("Сильные стороны", verdict.strengths))
        if verdict.recommendations:
            self._layout.addWidget(OrnamentalDivider())
            self._layout.addWidget(self._build_section("Рекомендации", verdict.recommendations))
        if verdict.structure_notes:
            self._layout.addWidget(OrnamentalDivider())
            self._layout.addWidget(self._build_section("Замечания по структуре", verdict.structure_notes))

    def _build_thesis_card(self, tv, colors: dict) -> QWidget:
        card = CardFrame(role="atelier", shadow=False)
        card.setProperty("answer-state", STATUS_STATE.get(tv.status, "partial"))
        card.style().unpolish(card)
        card.style().polish(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        badge = QLabel(STATUS_TEXT.get(tv.status, "?"))
        badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {colors.get(STATUS_COLORS_KEY.get(tv.status, 'danger'), colors['border'])};"
        )
        badge.setFixedWidth(36)
        top.addWidget(badge)

        label = QLabel(tv.thesis_label)
        label.setProperty("role", "card-title")
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
            excerpt.setProperty("role", "subtitle-italic")
            excerpt.setWordWrap(True)
            excerpt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(excerpt)

        return card

    def _build_section(self, title: str, items: list[str]) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)

        heading = QLabel(title)
        heading.setProperty("role", "section-title")
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
        if self._verdict is not None:
            self.set_verdict(self._verdict)
