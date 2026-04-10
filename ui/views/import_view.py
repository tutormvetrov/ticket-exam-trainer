from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from application.ui_data import ImportExecutionResult
from domain.models import DocumentData
from ui.components.common import CardFrame, IconBadge


class ImportView(QWidget):
    import_requested = Signal()
    open_library_requested = Signal()
    open_training_requested = Signal()
    open_statistics_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.last_result = ImportExecutionResult(False)
        self.documents: list[DocumentData] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Импорт документов")
        title.setProperty("role", "hero")
        layout.addWidget(title)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        intro_card = CardFrame(role="card", shadow_color=shadow_color)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(22, 22, 22, 22)
        intro_layout.setSpacing(12)

        intro_title = QLabel("Локальный импорт в базу знаний")
        intro_title.setProperty("role", "section-title")
        intro_layout.addWidget(intro_title)

        intro_body = QLabel(
            "Поддерживаются DOCX и PDF. После выбора файла текст извлекается, структурируется, сохраняется в SQLite и, при необходимости, уточняется локальным Mistral через Ollama."
        )
        intro_body.setWordWrap(True)
        intro_body.setProperty("role", "body")
        intro_layout.addWidget(intro_body)

        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(10)
        badges.addWidget(IconBadge("DOCX", "#EAF2FF", "#2E78E6", size=42, radius=13, font_size=10))
        badges.addWidget(IconBadge("PDF", "#FFF0F2", "#D94B63", size=42, radius=13, font_size=11))
        badges.addWidget(IconBadge("AI", "#EAF9F1", "#18B06A", size=42, radius=13, font_size=12))
        badges.addStretch(1)
        intro_layout.addLayout(badges)

        button = QPushButton("Открыть импорт")
        button.setProperty("variant", "primary")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.import_requested.emit)
        intro_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        top_row.addWidget(intro_card, 3)

        summary_card = CardFrame(role="card", shadow_color=shadow_color)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(22, 22, 22, 22)
        summary_layout.setSpacing(10)

        summary_title = QLabel("Состояние импорта")
        summary_title.setProperty("role", "section-title")
        summary_layout.addWidget(summary_title)

        self.summary_status = QLabel("Импорт ещё не выполнялся")
        self.summary_status.setStyleSheet("font-size: 15px; font-weight: 700;")
        summary_layout.addWidget(self.summary_status)

        self.summary_body = QLabel("После первого импорта здесь появится последний обработанный документ и результат разбиения.")
        self.summary_body.setWordWrap(True)
        self.summary_body.setProperty("role", "body")
        summary_layout.addWidget(self.summary_body)

        self.summary_meta = QLabel("База пока пуста.")
        self.summary_meta.setProperty("role", "body")
        self.summary_meta.setWordWrap(True)
        summary_layout.addWidget(self.summary_meta)
        self.summary_chip = QLabel("")
        self.summary_chip.setProperty("role", "pill")
        self.summary_chip.hide()
        summary_layout.addWidget(self.summary_chip, 0, Qt.AlignmentFlag.AlignLeft)
        summary_layout.addStretch(1)
        top_row.addWidget(summary_card, 2)
        layout.addLayout(top_row)

        handoff_card = CardFrame(role="subtle-card", shadow_color=shadow_color, shadow=False)
        handoff_layout = QVBoxLayout(handoff_card)
        handoff_layout.setContentsMargins(18, 16, 18, 16)
        handoff_layout.setSpacing(12)
        handoff_title = QLabel("Что делать дальше")
        handoff_title.setProperty("role", "section-title")
        handoff_layout.addWidget(handoff_title)
        self.handoff_body = QLabel(
            "После импорта откройте библиотеку, выберите документ и переходите к тренировке или статистике."
        )
        self.handoff_body.setProperty("role", "body")
        self.handoff_body.setWordWrap(True)
        handoff_layout.addWidget(self.handoff_body)
        handoff_actions = QHBoxLayout()
        handoff_actions.setContentsMargins(0, 0, 0, 0)
        handoff_actions.setSpacing(10)
        library_button = QPushButton("Открыть библиотеку")
        library_button.setProperty("variant", "primary")
        library_button.clicked.connect(self.open_library_requested.emit)
        handoff_actions.addWidget(library_button)
        training_button = QPushButton("Перейти к тренировке")
        training_button.setProperty("variant", "secondary")
        training_button.clicked.connect(self.open_training_requested.emit)
        handoff_actions.addWidget(training_button)
        statistics_button = QPushButton("Посмотреть статистику")
        statistics_button.setProperty("variant", "outline")
        statistics_button.clicked.connect(self.open_statistics_requested.emit)
        handoff_actions.addWidget(statistics_button)
        handoff_actions.addStretch(1)
        handoff_layout.addLayout(handoff_actions)
        layout.addWidget(handoff_card)

        recent_card = CardFrame(role="card", shadow_color=shadow_color)
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(22, 20, 22, 20)
        recent_layout.setSpacing(12)

        recent_title = QLabel("Последние документы")
        recent_title.setProperty("role", "section-title")
        recent_layout.addWidget(recent_title)

        self.recent_stack = QVBoxLayout()
        self.recent_stack.setContentsMargins(0, 0, 0, 0)
        self.recent_stack.setSpacing(10)
        recent_layout.addLayout(self.recent_stack)
        layout.addWidget(recent_card)
        layout.addStretch(1)

        self._refresh()

    def set_documents(self, documents: list[DocumentData]) -> None:
        self.documents = documents[:]
        self._refresh()

    def set_last_result(self, result: ImportExecutionResult) -> None:
        self.last_result = result
        self._refresh()

    def _refresh(self) -> None:
        while self.recent_stack.count():
            item = self.recent_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        latest_document = self.documents[0] if self.documents else None

        if self.last_result.ok:
            self.summary_status.setText("Последний импорт завершён успешно")
            self.summary_body.setText(
                f"Документ: {self.last_result.document_title}\n"
                f"Создано билетов: {self.last_result.tickets_created} • Разделов: {self.last_result.sections_created}"
            )
            if self.last_result.warnings:
                self.summary_meta.setText("Предупреждения:\n" + "\n".join(f"• {item}" for item in self.last_result.warnings[:3]))
            elif latest_document is not None:
                self.summary_meta.setText(
                    f"Последний документ в базе: {latest_document.title}\nИмпортирован: {latest_document.imported_at}"
                )
            else:
                self.summary_meta.setText("Данные уже сохранены в SQLite.")
            self.summary_chip.setText("LLM assist: да" if self.last_result.used_llm_assist else "LLM assist: нет")
            self.summary_chip.show()
            self.handoff_body.setText(
                "Импорт завершён. Откройте библиотеку, проверьте распознанный документ и сразу переходите к тренировке или статистике."
            )
        elif self.last_result.error:
            self.summary_status.setText("Последний импорт завершился ошибкой")
            self.summary_body.setText(self.last_result.error)
            self.summary_meta.setText("Проверьте формат файла и повторите импорт.")
            self.summary_chip.hide()
            self.handoff_body.setText("Сначала добейтесь успешного импорта, затем открывайте библиотеку и тренировку.")
        elif latest_document is not None:
            self.summary_status.setText("В базе уже есть импортированные документы")
            self.summary_body.setText(
                f"Последний документ: {latest_document.title}\nПредмет: {latest_document.subject}\nСтатус: {latest_document.status}"
            )
            self.summary_meta.setText(
                f"Импортирован: {latest_document.imported_at}\nРазмер: {latest_document.size}\nБилетов: {latest_document.tickets_count}"
            )
            self.summary_chip.hide()
            self.handoff_body.setText(
                "База уже заполнена. Откройте библиотеку для просмотра или переходите сразу в тренировку."
            )
        else:
            self.summary_status.setText("Импорт ещё не выполнялся")
            self.summary_body.setText("После первого импорта здесь появится последний обработанный документ и результат разбиения.")
            self.summary_meta.setText("База пока пуста.")
            self.summary_chip.hide()
            self.handoff_body.setText(
                "Сначала выберите большой DOCX или PDF. После успешного импорта станут доступны библиотека, тренировка и статистика."
            )

        if not self.documents:
            empty = QLabel("После первого импорта здесь появятся последние обработанные документы.")
            empty.setProperty("role", "body")
            empty.setWordWrap(True)
            self.recent_stack.addWidget(empty)
            return

        for document in self.documents[:3]:
            row = CardFrame(role="subtle-card", shadow_color=self.shadow_color, shadow=False)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(12)
            badge_color = "#EAF2FF" if document.file_type == "DOCX" else "#FFF0F2"
            badge_fg = "#2E78E6" if document.file_type == "DOCX" else "#D94B63"
            row_layout.addWidget(IconBadge(document.file_type, badge_color, badge_fg, size=38, radius=12, font_size=10))

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            title = QLabel(document.title)
            title.setStyleSheet("font-size: 14px; font-weight: 700;")
            title.setWordWrap(True)
            text_box.addWidget(title)
            meta = QLabel(f"{document.subject} • {document.imported_at} • {document.tickets_count} бил.")
            meta.setProperty("role", "body")
            meta.setWordWrap(True)
            text_box.addWidget(meta)
            row_layout.addLayout(text_box, 1)

            status = QLabel(document.status)
            status.setStyleSheet("font-size: 13px; font-weight: 700; color: #18B06A;")
            row_layout.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
            self.recent_stack.addWidget(row)

    def set_search_text(self, text: str) -> None:
        return
