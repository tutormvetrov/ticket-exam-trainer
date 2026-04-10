from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from domain.models import DocumentData
from ui.components.common import CardFrame, ClickableFrame, IconBadge


class DocumentListItem(ClickableFrame):
    clicked = Signal(str)

    def __init__(self, document: DocumentData) -> None:
        super().__init__(role="document-item", shadow=False)
        self.document = document
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        badge_color = "#EAF2FF" if document.file_type == "DOCX" else "#FFF0F2"
        badge_fg = "#2E78E6" if document.file_type == "DOCX" else "#D94B63"
        layout.addWidget(IconBadge(document.file_type, badge_color, badge_fg, size=46, radius=14, font_size=11))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        title = QLabel(document.title)
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        text_layout.addWidget(title)

        meta = QLabel(f"{document.subject} • {document.imported_at.split(' в ')[0]}")
        meta.setProperty("role", "body")
        text_layout.addWidget(meta)

        counts = QLabel(f"Разделов: {document.sections_count} • Билетов: {document.tickets_count}")
        counts.setProperty("role", "body")
        text_layout.addWidget(counts)
        layout.addLayout(text_layout, 1)

        more = QPushButton("⋮")
        more.setFixedSize(30, 30)
        more.setProperty("variant", "toolbar-ghost")
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.document.id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class DocumentListPanel(CardFrame):
    document_selected = Signal(str)

    def __init__(self, documents: list[DocumentData], shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        self.documents = documents
        self.filtered = documents[:]
        self.items: dict[str, DocumentListItem] = {}
        self.current_id = documents[0].id if documents else ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.setSpacing(12)
        self.title_label = QLabel()
        self.title_label.setProperty("role", "card-title")
        self.header.addWidget(self.title_label)
        self.header.addStretch(1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Сортировка: по дате", "Сортировка: по названию"])
        self.sort_combo.setMaximumWidth(190)
        self.sort_combo.currentIndexChanged.connect(self._resort)
        self.header.addWidget(self.sort_combo)
        layout.addLayout(self.header)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #E9EEF5;")
        layout.addWidget(line)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.stack = QVBoxLayout(inner)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(12)
        self.scroll.setWidget(inner)
        layout.addWidget(self.scroll, 1)

        self._update_title()
        self._rebuild_items()

    def _rebuild_items(self) -> None:
        while self.stack.count():
            item = self.stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.items.clear()

        for document in self.filtered:
            item = DocumentListItem(document)
            item.clicked.connect(self.select_document)
            self.stack.addWidget(item)
            self.items[document.id] = item

        self.stack.addStretch(1)
        if self.filtered:
            selected_id = self.current_id if self.current_id in self.items else self.filtered[0].id
            self.select_document(selected_id, emit_signal=False)
        else:
            self.current_id = ""

    def _update_title(self) -> None:
        self.title_label.setText(f"Ваши документы ({len(self.documents)})")

    def set_documents(self, documents: list[DocumentData]) -> None:
        self.documents = documents[:]
        self.filtered = documents[:]
        if self.current_id not in {document.id for document in documents}:
            self.current_id = documents[0].id if documents else ""
        self._update_title()
        self._resort()

    def select_document(self, document_id: str, emit_signal: bool = True) -> None:
        self.current_id = document_id
        for item_id, item in self.items.items():
            item.set_selected(item_id == document_id)
        if emit_signal:
            self.document_selected.emit(document_id)

    def _resort(self) -> None:
        if self.sort_combo.currentIndex() == 0:
            order = {document.id: index for index, document in enumerate(self.documents)}
            self.filtered.sort(key=lambda document: order[document.id])
        else:
            self.filtered.sort(key=lambda document: document.title.lower())
        self._rebuild_items()

    def apply_search(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self.filtered = self.documents[:]
        else:
            self.filtered = [
                document
                for document in self.documents
                if query in document.title.lower() or query in document.subject.lower()
            ]
        self._resort()

    def resizeEvent(self, event) -> None:  # noqa: N802
        narrow = self.width() < 370
        direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        if self.header.direction() != direction:
            self.header.setDirection(direction)
            self.sort_combo.setMaximumWidth(16777215 if narrow else 190)
        super().resizeEvent(event)
