from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from application.ui_data import SectionOverviewItem
from ui.components.common import CardFrame


class SectionsView(QWidget):
    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.sections: list[SectionOverviewItem] = []
        self.filtered: list[SectionOverviewItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("Разделы")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)
        self.combo = QComboBox()
        self.combo.addItems(["Все предметы"])
        self.combo.setFixedWidth(180)
        self.combo.currentTextChanged.connect(self._apply_filters)
        header.addWidget(self.combo)
        layout.addLayout(header)

        self.card = CardFrame(role="card", shadow_color=shadow_color)
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        layout.addWidget(self.card)
        layout.addStretch(1)

    def set_sections(self, sections: list[SectionOverviewItem]) -> None:
        self.sections = sections[:]
        subjects = ["Все предметы"] + sorted({item.subject for item in sections})
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(subjects)
        self.combo.blockSignals(False)
        self._apply_filters()

    def _apply_filters(self) -> None:
        subject = self.combo.currentText()
        if subject == "Все предметы":
            self.filtered = self.sections[:]
        else:
            self.filtered = [item for item in self.sections if item.subject == subject]
        self._rebuild()

    def _rebuild(self) -> None:
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.filtered:
            self.card.setMaximumHeight(120)
            empty = QWidget()
            empty_layout = QHBoxLayout(empty)
            empty_layout.setContentsMargins(18, 16, 18, 16)
            label = QLabel("Разделы появятся после импорта документов.")
            label.setProperty("role", "body")
            empty_layout.addWidget(label)
            self.card_layout.addWidget(empty)
            self.card_layout.addStretch(1)
            return

        for index, item in enumerate(self.filtered):
            row = QWidget()
            row.setMinimumHeight(86)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 16, 18, 16)
            title = QLabel(item.title)
            title.setStyleSheet("font-size: 15px; font-weight: 700;")
            row_layout.addWidget(title)
            row_layout.addStretch(1)
            meta = QLabel(f"{item.subject} • {item.tickets} бил.")
            meta.setProperty("role", "body")
            row_layout.addWidget(meta)
            self.card_layout.addWidget(row)
            if index != len(self.filtered) - 1:
                divider = QWidget()
                divider.setFixedHeight(1)
                divider.setStyleSheet("background: #E9EEF5;")
                self.card_layout.addWidget(divider)
        content_height = len(self.filtered) * 86 + max(0, len(self.filtered) - 1)
        self.card.setMaximumHeight(max(140, content_height + 18))

    def set_search_text(self, text: str) -> None:
        query = text.strip().lower()
        subject = self.combo.currentText()
        base = self.sections if subject == "Все предметы" else [item for item in self.sections if item.subject == subject]
        if not query:
            self.filtered = base
        else:
            self.filtered = [
                item
                for item in base
                if query in item.title.lower() or query in item.subject.lower()
            ]
        self._rebuild()
