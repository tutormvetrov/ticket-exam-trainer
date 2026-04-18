from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from application.ui_data import SectionOverviewItem
from ui.components.common import CardFrame, EmptyStatePanel
from ui.theme import current_colors


class SectionsView(QWidget):
    open_library_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.sections: list[SectionOverviewItem] = []
        self.filtered: list[SectionOverviewItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.addStretch(1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
        header.addWidget(self.search_input)

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
        colors = current_colors()
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.filtered:
            self.card.setMaximumHeight(260)
            has_sections = bool(self.sections)
            self.card_layout.addWidget(
                EmptyStatePanel(
                    "sections",
                    "Разделы не найдены" if has_sections else "Разделы пока не сформированы",
                    (
                        "Фильтр ничего не вернул. Попробуйте другой запрос или сбросьте ограничение по предмету."
                        if has_sections
                        else "После импорта документов здесь появится структура разделов и привязка к предметам."
                    ),
                    role="subtle-card",
                    secondary_action=None
                    if has_sections
                    else ("Открыть библиотеку", self.open_library_requested.emit, "secondary", "library"),
                )
            )
            self.card_layout.addStretch(1)
            return

        for index, item in enumerate(self.filtered):
            row = QWidget()
            row.setMinimumHeight(86)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 16, 18, 16)
            title = QLabel(item.title)
            title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {colors['text']};")
            row_layout.addWidget(title)
            row_layout.addStretch(1)
            meta = QLabel(f"{item.subject} • {item.tickets} бил.")
            meta.setProperty("role", "body")
            row_layout.addWidget(meta)
            self.card_layout.addWidget(row)
            if index != len(self.filtered) - 1:
                divider = QWidget()
                divider.setFixedHeight(1)
                divider.setStyleSheet(f"background: {colors['border']};")
                self.card_layout.addWidget(divider)
        content_height = len(self.filtered) * 86 + max(0, len(self.filtered) - 1)
        self.card.setMaximumHeight(max(140, content_height + 18))

    def refresh_theme(self) -> None:
        self._rebuild()

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
