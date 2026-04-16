from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QElapsedTimer, Property, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from application.ui_data import ImportExecutionResult
from domain.models import DocumentData
from ui.components.common import CardFrame, IconBadge, file_badge_colors, tone_pair
from ui.theme import current_colors


class ImportView(QWidget):
    import_requested = Signal()
    resume_requested = Signal(str)
    open_library_requested = Signal()
    open_training_requested = Signal()
    open_statistics_requested = Signal()

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.last_result = ImportExecutionResult(False)
        self.documents: list[DocumentData] = []
        self._import_pending = False
        self._pending_file_name = ""
        self._progress_percent = 0
        self._progress_stage = ""
        self._progress_detail = ""
        self._elapsed_timer = QElapsedTimer()
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1000)
        self._progress_timer.timeout.connect(self._refresh_progress_meta)

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
            "Поддерживаются DOCX и PDF. После выбора файла текст извлекается, "
            "сохраняется в SQLite и по ходу обработки превращается в билеты, карты знаний "
            "и упражнения. Уже сохранённые результаты не теряются, даже если LLM-хвост "
            "придётся доделывать отдельно."
        )
        intro_body.setWordWrap(True)
        intro_body.setProperty("role", "body")
        intro_layout.addWidget(intro_body)

        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(10)
        docx_bg, docx_fg = file_badge_colors("DOCX")
        pdf_bg, pdf_fg = file_badge_colors("PDF")
        ai_bg, ai_fg = file_badge_colors("AI")
        badges.addWidget(IconBadge("DOCX", docx_bg, docx_fg, size=42, radius=13, font_size=10))
        badges.addWidget(IconBadge("PDF", pdf_bg, pdf_fg, size=42, radius=13, font_size=11))
        badges.addWidget(IconBadge("AI", ai_bg, ai_fg, size=42, radius=13, font_size=12))
        badges.addStretch(1)
        intro_layout.addLayout(badges)

        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(10)
        profile_label = QLabel("Профиль ответа")
        profile_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {current_colors()['text']};")
        self.answer_profile_combo = QComboBox()
        self.answer_profile_combo.setObjectName("import-answer-profile")
        self.answer_profile_combo.addItem("Обычный билет", "standard_ticket")
        self.answer_profile_combo.addItem("Госэкзамен", "state_exam_public_admin")
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.answer_profile_combo, 1)
        intro_layout.addLayout(profile_row)

        self.open_import_button = QPushButton("Открыть импорт")
        self.open_import_button.setObjectName("import-open")
        self.open_import_button.setProperty("variant", "primary")
        self.open_import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_import_button.clicked.connect(self.import_requested.emit)
        intro_layout.addWidget(self.open_import_button, 0, Qt.AlignmentFlag.AlignLeft)
        top_row.addWidget(intro_card, 3)

        summary_card = CardFrame(role="card", shadow_color=shadow_color)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(22, 22, 22, 22)
        summary_layout.setSpacing(10)

        summary_title = QLabel("Состояние импорта")
        summary_title.setProperty("role", "section-title")
        summary_layout.addWidget(summary_title)

        self.summary_status = QLabel("Импорт ещё не выполнялся")
        self.summary_status.setProperty("skipTextAdmin", True)
        self.summary_status.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
        summary_layout.addWidget(self.summary_status)

        self.summary_body = QLabel(
            "После первого импорта здесь появится последний обработанный документ и честный статус его состояния."
        )
        self.summary_body.setProperty("skipTextAdmin", True)
        self.summary_body.setWordWrap(True)
        self.summary_body.setProperty("role", "body")
        summary_layout.addWidget(self.summary_body)

        self.summary_meta = QLabel("База пока пуста.")
        self.summary_meta.setProperty("skipTextAdmin", True)
        self.summary_meta.setProperty("role", "body")
        self.summary_meta.setWordWrap(True)
        summary_layout.addWidget(self.summary_meta)

        self.summary_chip = QLabel("")
        self.summary_chip.setProperty("skipTextAdmin", True)
        self.summary_chip.setProperty("role", "pill")
        self.summary_chip.hide()
        summary_layout.addWidget(self.summary_chip, 0, Qt.AlignmentFlag.AlignLeft)

        self.progress_stage_label = QLabel("")
        self.progress_stage_label.setProperty("skipTextAdmin", True)
        self.progress_stage_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {current_colors()['text']};")
        self.progress_stage_label.hide()
        summary_layout.addWidget(self.progress_stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self._apply_progress_styles()
        self.progress_bar.hide()
        summary_layout.addWidget(self.progress_bar)

        self._progress_animation = QPropertyAnimation(self, b"animatedProgress", self)
        self._progress_animation.setDuration(480)
        self._progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.progress_meta_label = QLabel("")
        self.progress_meta_label.setProperty("skipTextAdmin", True)
        self.progress_meta_label.setProperty("role", "body")
        self.progress_meta_label.setWordWrap(True)
        self.progress_meta_label.hide()
        summary_layout.addWidget(self.progress_meta_label)

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
            "После импорта откройте библиотеку, проверьте документ и переходите к тренировке или статистике."
        )
        self.handoff_body.setProperty("skipTextAdmin", True)
        self.handoff_body.setProperty("role", "body")
        self.handoff_body.setWordWrap(True)
        handoff_layout.addWidget(self.handoff_body)

        handoff_actions = QHBoxLayout()
        handoff_actions.setContentsMargins(0, 0, 0, 0)
        handoff_actions.setSpacing(10)

        self.library_button = QPushButton("Открыть библиотеку")
        self.library_button.setObjectName("import-open-library")
        self.library_button.setProperty("variant", "primary")
        self.library_button.clicked.connect(self.open_library_requested.emit)
        handoff_actions.addWidget(self.library_button)

        self.training_button = QPushButton("Перейти к тренировке")
        self.training_button.setObjectName("import-open-training")
        self.training_button.setProperty("variant", "secondary")
        self.training_button.clicked.connect(self.open_training_requested.emit)
        handoff_actions.addWidget(self.training_button)

        self.statistics_button = QPushButton("Посмотреть статистику")
        self.statistics_button.setObjectName("import-open-statistics")
        self.statistics_button.setProperty("variant", "outline")
        self.statistics_button.clicked.connect(self.open_statistics_requested.emit)
        handoff_actions.addWidget(self.statistics_button)

        self.resume_button = QPushButton("Доделать локально")
        self.resume_button.setObjectName("import-resume")
        self.resume_button.setProperty("variant", "secondary")
        self.resume_button.clicked.connect(self._emit_resume_requested)
        self.resume_button.hide()
        handoff_actions.addWidget(self.resume_button)

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

    def _apply_progress_styles(self) -> None:
        colors = current_colors()
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: {colors["card_muted"]};
                border: 1px solid {colors["border"]};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {colors["primary_hover"]}, stop:1 {colors["primary"]});
                border-radius: 5px;
            }}
            """
        )

    def is_busy(self) -> bool:
        return self._import_pending

    def selected_answer_profile_code(self) -> str:
        return str(self.answer_profile_combo.currentData() or "standard_ticket")

    def set_documents(self, documents: list[DocumentData]) -> None:
        self.documents = documents[:]
        self._refresh()

    def set_last_result(self, result: ImportExecutionResult) -> None:
        self.last_result = result
        self._import_pending = False
        self._pending_file_name = ""
        self._set_actions_enabled(True)
        self._progress_timer.stop()
        self._refresh()

    def set_import_pending(self, file_name: str) -> None:
        self._import_pending = True
        self._pending_file_name = file_name
        self._progress_percent = 2
        self._progress_stage = "Подготовка импорта"
        self._progress_detail = "Открываем файл и запускаем фоновую обработку"
        self._elapsed_timer.restart()
        self._progress_timer.start()
        self._set_actions_enabled(False)
        self.answer_profile_combo.setEnabled(False)
        self._refresh()

    def set_resume_pending(self, document_title: str, remaining: int) -> None:
        self._import_pending = True
        self._pending_file_name = document_title
        self._progress_percent = 6
        self._progress_stage = "Локальная доработка хвоста"
        self._progress_detail = f"Осталось доработать билетов: {remaining}"
        self._elapsed_timer.restart()
        self._progress_timer.start()
        self._set_actions_enabled(False)
        self.answer_profile_combo.setEnabled(False)
        self._refresh()

    def set_import_progress(self, percent: int, stage: str, detail: str = "") -> None:
        bounded = max(0, min(100, int(percent)))
        self._progress_percent = bounded
        self._progress_stage = stage
        self._progress_detail = detail
        if self._import_pending and not self._elapsed_timer.isValid():
            self._elapsed_timer.restart()
        if self._import_pending and not self._progress_timer.isActive():
            self._progress_timer.start()
        self._animate_progress_to(bounded)
        self._refresh_progress_meta()
        self._refresh()

    def _emit_resume_requested(self) -> None:
        if self.last_result.document_id:
            self.resume_requested.emit(self.last_result.document_id)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.open_import_button.setEnabled(enabled)
        self.library_button.setEnabled(enabled)
        self.training_button.setEnabled(enabled)
        self.statistics_button.setEnabled(enabled)
        self.resume_button.setEnabled(enabled)
        self.answer_profile_combo.setEnabled(enabled)

    def _refresh_progress_meta(self) -> None:
        if not self._import_pending or not self._elapsed_timer.isValid():
            self.progress_meta_label.hide()
            return
        elapsed_seconds = max(1, int(self._elapsed_timer.elapsed() / 1000))
        elapsed_label = self._format_seconds(elapsed_seconds)
        if 8 <= self._progress_percent < 100:
            estimated_total = int(round(elapsed_seconds * 100 / max(1, self._progress_percent)))
            remaining = max(0, estimated_total - elapsed_seconds)
            self.progress_meta_label.setText(
                f"Прошло: {elapsed_label} • Осталось примерно: {self._format_seconds(remaining)}"
            )
        else:
            self.progress_meta_label.setText(
                f"Прошло: {elapsed_label} • Оценка оставшегося времени появится после первых этапов"
            )
        self.progress_meta_label.show()

    def _animate_progress_to(self, percent: int) -> None:
        self._progress_animation.stop()
        self._progress_animation.setStartValue(self.progress_bar.value())
        self._progress_animation.setEndValue(percent)
        self._progress_animation.start()

    def get_animated_progress(self) -> int:
        return self.progress_bar.value()

    def set_animated_progress(self, value: int) -> None:
        self.progress_bar.setValue(max(0, min(100, int(value))))

    animatedProgress = Property(int, get_animated_progress, set_animated_progress)

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        minutes, secs = divmod(max(0, seconds), 60)
        if minutes:
            return f"{minutes} мин {secs:02d} с"
        return f"{secs} с"

    def _render_finished_state(self) -> None:
        result = self.last_result
        warnings_text = ""
        if result.warnings:
            warnings_text = "Предупреждения:\n" + "\n".join(f"• {item}" for item in result.warnings[:4])

        llm_meta = (
            f"LLM: обработано {result.llm_done_tickets}"
            f" • резервный режим {result.llm_fallback_tickets}"
            f" • ошибки {result.llm_failed_tickets}"
            f" • ожидают {result.llm_pending_tickets}"
        )

        if result.status == "structured":
            self.summary_status.setText("Последний импорт завершён полностью")
            self.summary_body.setText(
                f"Документ: {result.document_title}\n"
                f"Профиль: {result.answer_profile_label}\n"
                f"Создано билетов: {result.tickets_created} • Разделов: {result.sections_created}"
            )
            self.summary_meta.setText(warnings_text or "Все этапы импорта и LLM-структурирования завершены.")
            self.summary_chip.setText(llm_meta if result.used_llm_assist else "LLM-помощь: не использовалась")
            self.handoff_body.setText(
                "Импорт завершён. Откройте библиотеку, проверьте документ и переходите к тренировке или статистике."
            )
        elif result.status == "partial_llm":
            self.summary_status.setText("Импорт сохранён, но LLM-хвост не добит")
            self.summary_body.setText(
                f"Документ: {result.document_title}\n"
                f"Профиль: {result.answer_profile_label}\n"
                f"Создано билетов: {result.tickets_created} • Готово LLM: {result.llm_done_tickets}"
            )
            self.summary_meta.setText(
                warnings_text
                or "Часть билетов сохранена через fallback или осталась без локальной LLM-доработки."
            )
            self.summary_chip.setText(llm_meta)
            self.handoff_body.setText(
                "Базовый импорт уже в SQLite. Можно открыть библиотеку и одновременно локально доделать только хвост."
            )
        elif result.status == "importing":
            self.summary_status.setText("Предыдущий импорт прервался")
            self.summary_body.setText(
                f"Документ: {result.document_title}\n"
                f"Уже сохранено билетов: {result.llm_done_tickets or result.tickets_created}"
            )
            self.summary_meta.setText(
                warnings_text or "Результат в SQLite уже есть. Можно продолжить локальную доработку с места остановки."
            )
            self.summary_chip.setText(llm_meta)
            self.handoff_body.setText("Нажмите «Доделать локально», чтобы продолжить только недообработанный хвост.")
        else:
            self.summary_status.setText("Импорт завершился с ошибкой")
            self.summary_body.setText(result.error or "Во время импорта произошла ошибка.")
            self.summary_meta.setText(warnings_text or "Уже сохранённый результат в SQLite не удалён.")
            self.summary_chip.setText(llm_meta)
            self.handoff_body.setText(
                "Если часть билетов уже сохранена, можно попробовать локально доделать только хвост."
            )

        self.summary_chip.show()
        self.resume_button.setVisible(result.resume_available)
        self.progress_stage_label.hide()
        self.progress_bar.hide()
        self.progress_meta_label.hide()

    def _refresh(self) -> None:
        colors = current_colors()
        while self.recent_stack.count():
            item = self.recent_stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        latest_document = self.documents[0] if self.documents else None

        if self._import_pending:
            self.summary_status.setText("Идёт импорт документа")
            self.summary_body.setText(
                f"Файл: {self._pending_file_name}\nИмпорт и разбор идут в фоне. Окно не должно зависать."
            )
            self.summary_meta.setText(
                self._progress_detail or "Можно оставаться на этом экране. Результат появится после завершения обработки."
            )
            self.summary_chip.setText(f"{self._progress_percent}%")
            self.summary_chip.show()
            self.progress_stage_label.setText(self._progress_stage or "Фоновая обработка")
            self.progress_stage_label.show()
            self.progress_bar.show()
            self.progress_meta_label.show()
            self.resume_button.hide()
            self.handoff_body.setText(
                "Дождитесь завершения текущего шага. Уже обработанные билеты сохраняются в SQLite по ходу работы."
            )
        elif self.last_result.ok:
            self._render_finished_state()
        elif self.last_result.error:
            self.summary_status.setText("Последний импорт завершился ошибкой")
            self.summary_body.setText(self.last_result.error)
            self.summary_meta.setText("Проверьте формат файла и попробуйте снова.")
            self.summary_chip.hide()
            self.progress_stage_label.hide()
            self.progress_bar.hide()
            self.progress_meta_label.hide()
            self.resume_button.hide()
            self.handoff_body.setText("Сначала добейтесь успешного импорта, затем переходите в библиотеку и тренировку.")
        elif latest_document is not None:
            self.summary_status.setText("В базе уже есть импортированные документы")
            self.summary_body.setText(
                f"Последний документ: {latest_document.title}\n"
                f"Предмет: {latest_document.subject}\n"
                f"Статус: {latest_document.status}"
            )
            self.summary_meta.setText(
                f"Импортирован: {latest_document.imported_at}\n"
                f"Размер: {latest_document.size}\n"
                f"Билетов: {latest_document.tickets_count}"
            )
            self.summary_chip.hide()
            self.progress_stage_label.hide()
            self.progress_bar.hide()
            self.progress_meta_label.hide()
            self.resume_button.hide()
            self.handoff_body.setText(
                "База уже заполнена. Откройте библиотеку для просмотра или переходите сразу в тренировку."
            )
        else:
            self.summary_status.setText("Импорт ещё не выполнялся")
            self.summary_body.setText(
                "После первого импорта здесь появится последний обработанный документ и результат разбиения."
            )
            self.summary_meta.setText("База пока пуста.")
            self.summary_chip.hide()
            self.progress_stage_label.hide()
            self.progress_bar.hide()
            self.progress_meta_label.hide()
            self.resume_button.hide()
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

            badge_color, badge_fg = file_badge_colors(document.file_type)
            row_layout.addWidget(IconBadge(document.file_type, badge_color, badge_fg, size=38, radius=12, font_size=10))

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            title = QLabel(document.title)
            title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
            title.setWordWrap(True)
            text_box.addWidget(title)
            meta = QLabel(f"{document.subject} • {document.imported_at} • {document.tickets_count} бил.")
            meta.setProperty("role", "body")
            meta.setWordWrap(True)
            text_box.addWidget(meta)
            row_layout.addLayout(text_box, 1)

            status = QLabel(document.status)
            status_bg, status_fg = tone_pair("success" if document.status in {"structured", "ready", "done"} else "warning")
            status.setStyleSheet(
                f"background: {status_bg}; color: {status_fg}; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
            )
            row_layout.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
            self.recent_stack.addWidget(row)

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.summary_status.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {colors['text']};")
        self.progress_stage_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text']};")
        self._apply_progress_styles()
        self._refresh()
