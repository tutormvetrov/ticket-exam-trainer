from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class TextEntry:
    key: str
    source_text: str
    override_text: str
    kind: str


def _direct_children(parent: QWidget) -> list[QWidget]:
    return [child for child in parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)]


def _skip_widget(widget: QWidget) -> bool:
    current: QWidget | None = widget
    while current is not None:
        if bool(current.property("skipTextAdmin")):
            return True
        current = current.parentWidget()
    return False


def _widget_path(widget: QWidget) -> str:
    segments: list[str] = []
    current = widget
    while current is not None:
        parent = current.parentWidget()
        segment = current.objectName()
        if not segment:
            if parent is None:
                segment = current.metaObject().className()
            else:
                siblings = [
                    child
                    for child in _direct_children(parent)
                    if child.metaObject().className() == current.metaObject().className()
                ]
                index = siblings.index(current)
                segment = f"{current.metaObject().className()}[{index}]"
        segments.append(segment)
        current = parent
    return "/".join(reversed(segments))


def _build_key(widget: QWidget, suffix: str) -> str:
    return f"{_widget_path(widget)}::{suffix}"


def _base_property_name(suffix: str) -> str:
    safe_suffix = suffix.replace("[", "_").replace("]", "").replace(":", "_").replace("/", "_")
    return f"_base_text_{safe_suffix}"


def _get_or_store_base(widget: QWidget, suffix: str, current_value: str) -> str:
    property_name = _base_property_name(suffix)
    existing = widget.property(property_name)
    if isinstance(existing, str):
        return existing
    widget.setProperty(property_name, current_value)
    return current_value


def _get_or_store_combo_items(widget: QComboBox) -> list[str]:
    existing = widget.property("_base_text_combo_items")
    if isinstance(existing, list) and len(existing) == widget.count():
        return [str(item) for item in existing]
    values = [widget.itemText(index) for index in range(widget.count())]
    widget.setProperty("_base_text_combo_items", values)
    return values


def collect_text_entries(root: QWidget, overrides: dict[str, str] | None = None) -> list[TextEntry]:
    applied = overrides or {}
    entries: list[TextEntry] = []
    seen: set[str] = set()
    for widget in root.findChildren(QWidget):
        if _skip_widget(widget):
            continue
        if isinstance(widget, QLabel):
            text = widget.text().strip()
            if text:
                key = _build_key(widget, "text")
                base_text = _get_or_store_base(widget, "text", text)
                if key not in seen:
                    seen.add(key)
                    entries.append(TextEntry(key, base_text, applied.get(key, ""), "Надпись"))
        elif isinstance(widget, QPushButton):
            text = widget.text().strip()
            if text:
                key = _build_key(widget, "text")
                base_text = _get_or_store_base(widget, "text", text)
                if key not in seen:
                    seen.add(key)
                    entries.append(TextEntry(key, base_text, applied.get(key, ""), "Кнопка"))
        elif isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText().strip()
            if placeholder:
                key = _build_key(widget, "placeholder")
                base_text = _get_or_store_base(widget, "placeholder", placeholder)
                if key not in seen:
                    seen.add(key)
                    entries.append(TextEntry(key, base_text, applied.get(key, ""), "Подсказка"))
        elif isinstance(widget, QTextEdit):
            placeholder = widget.placeholderText().strip()
            if placeholder:
                key = _build_key(widget, "placeholder")
                base_text = _get_or_store_base(widget, "placeholder", placeholder)
                if key not in seen:
                    seen.add(key)
                    entries.append(TextEntry(key, base_text, applied.get(key, ""), "Подсказка"))
        elif isinstance(widget, QComboBox):
            base_items = _get_or_store_combo_items(widget)
            for index, item_text in enumerate(base_items):
                item_text = item_text.strip()
                if item_text:
                    key = _build_key(widget, f"item[{index}]")
                    if key not in seen:
                        seen.add(key)
                        entries.append(TextEntry(key, item_text, applied.get(key, ""), "Список"))
    entries.sort(key=lambda item: (item.kind, item.key))
    return entries


def apply_text_overrides(root: QWidget, overrides: dict[str, str]) -> None:
    for widget in root.findChildren(QWidget):
        if _skip_widget(widget):
            continue
        if isinstance(widget, (QLabel, QPushButton)):
            key = _build_key(widget, "text")
            base_text = _get_or_store_base(widget, "text", widget.text())
            widget.setText(overrides[key] if key in overrides and overrides[key].strip() else base_text)
        elif isinstance(widget, QLineEdit):
            key = _build_key(widget, "placeholder")
            base_text = _get_or_store_base(widget, "placeholder", widget.placeholderText())
            widget.setPlaceholderText(overrides[key] if key in overrides and overrides[key].strip() else base_text)
        elif isinstance(widget, QTextEdit):
            key = _build_key(widget, "placeholder")
            base_text = _get_or_store_base(widget, "placeholder", widget.placeholderText())
            widget.setPlaceholderText(overrides[key] if key in overrides and overrides[key].strip() else base_text)
        elif isinstance(widget, QComboBox):
            base_items = _get_or_store_combo_items(widget)
            for index, base_text in enumerate(base_items):
                key = _build_key(widget, f"item[{index}]")
                widget.setItemText(index, overrides[key] if key in overrides and overrides[key].strip() else base_text)


def set_debug_mode(root: QWidget, enabled: bool) -> None:
    for widget in root.findChildren(QWidget):
        if _skip_widget(widget):
            continue
        if isinstance(widget, (QLabel, QPushButton)):
            suffix = "text"
        elif isinstance(widget, (QLineEdit, QTextEdit)):
            suffix = "placeholder"
        elif isinstance(widget, QComboBox):
            suffix = "items"
        else:
            continue
        widget.setProperty("debugText", enabled)
        widget.setToolTip(_build_key(widget, suffix) if enabled else "")
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class InterfaceTextEditorDialog(QDialog):
    def __init__(self, root: QWidget, overrides: dict[str, str]) -> None:
        super().__init__(root)
        self.setWindowTitle("Редактор подписей интерфейса")
        self.resize(1040, 720)
        self._root = root
        self._entries = collect_text_entries(root, overrides)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(
            "Здесь можно поправить реальные подписи, кнопки и подсказки. "
            "Пустое поле означает, что используется исходный текст."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)
        search_label = QLabel("Фильтр")
        search_row.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по ключу или тексту")
        self.search_input.textChanged.connect(self._refresh_table)
        search_row.addWidget(self.search_input, 1)
        clear_button = QPushButton("Сбросить фильтр")
        clear_button.clicked.connect(lambda: self.search_input.setText(""))
        search_row.addWidget(clear_button)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Тип", "Ключ", "Исходный текст", "Переопределение"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 360)
        self.table.setColumnWidth(2, 260)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        reset_button = QPushButton("Сбросить переопределения")
        reset_button.clicked.connect(self._reset_overrides)
        buttons.addButton(reset_button, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_table()

    def current_overrides(self) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 1).text()
            editor = self.table.cellWidget(row, 3)
            if isinstance(editor, QLineEdit):
                value = editor.text().strip()
                if value:
                    overrides[key] = value
        return overrides

    def _refresh_table(self) -> None:
        query = self.search_input.text().strip().lower()
        filtered = [
            entry
            for entry in self._entries
            if not query or query in entry.key.lower() or query in entry.source_text.lower() or query in entry.override_text.lower()
        ]
        self.table.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            type_item = QTableWidgetItem(entry.kind)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            key_item = QTableWidgetItem(entry.key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            source_item = QTableWidgetItem(entry.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, type_item)
            self.table.setItem(row, 1, key_item)
            self.table.setItem(row, 2, source_item)

            editor = QLineEdit(entry.override_text)
            editor.setPlaceholderText(entry.source_text)
            self.table.setCellWidget(row, 3, editor)

    def _reset_overrides(self) -> None:
        for row in range(self.table.rowCount()):
            editor = self.table.cellWidget(row, 3)
            if isinstance(editor, QLineEdit):
                editor.clear()
