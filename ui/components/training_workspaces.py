from __future__ import annotations

from dataclasses import dataclass
import hashlib
from random import Random
import re

from application.answer_profile_registry import STATE_EXAM_PUBLIC_ADMIN_PROFILE, get_answer_profile
from domain.answer_profile import AnswerBlockCode, AnswerProfileCode
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from application.ui_data import TrainingEvaluationResult
from domain.knowledge import KnowledgeAtom, TicketKnowledgeMap
from ui.training_mode_registry import TRAINING_MODE_SPECS, TrainingModeSpec
from ui.theme import current_colors


WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+")


def _compact(text: str, limit: int = 140) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _fallback_keywords(text: str) -> list[str]:
    return [token for token in WORD_PATTERN.findall(text) if len(token) > 3][:5]


def _pick_keyword(atom: KnowledgeAtom) -> str:
    candidates = [keyword for keyword in atom.keywords if len(keyword) > 2] or _fallback_keywords(atom.text)
    return max(candidates, key=len, default="")


def _pick_keyword_from_text(text: str) -> str:
    candidates = [keyword for keyword in _fallback_keywords(text) if len(keyword) > 2]
    return max(candidates, key=len, default="")


def _seed_for(ticket_id: str, mode_key: str) -> int:
    digest = hashlib.sha256(f"{ticket_id}:{mode_key}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _reference_answer(ticket: TicketKnowledgeMap, limit: int | None = None) -> str:
    if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
        blocks = ticket.answer_blocks if limit is None else ticket.answer_blocks[:limit]
        return "\n".join(f"{block.title}: {block.expected_content}" for block in blocks)
    if ticket.canonical_answer_summary.strip():
        return ticket.canonical_answer_summary.strip()
    atoms = [atom.text.strip() for atom in ticket.atoms if atom.text.strip()]
    if limit is not None:
        atoms = atoms[:limit]
    return "\n".join(atoms)


def _state_exam_blocks(ticket: TicketKnowledgeMap):
    return ticket.answer_blocks if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN else []


def _block_display_name(code: str) -> str:
    for block in STATE_EXAM_PUBLIC_ADMIN_PROFILE.blocks:
        if block.code.value == code:
            return block.title
    return code


def _criterion_display_name(code: str) -> str:
    for criterion in STATE_EXAM_PUBLIC_ADMIN_PROFILE.criteria:
        if criterion.code.value == code:
            return criterion.title
    return code


@dataclass(slots=True)
class ClozePrompt:
    original_text: str
    masked_text: str
    answer: str


class TrainingWorkspaceBase(QWidget):
    evaluate_requested = Signal(str)
    advance_requested = Signal()
    random_requested = Signal()

    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__()
        self.spec = spec
        self.current_ticket: TicketKnowledgeMap | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        colors = current_colors()
        self.header_label = QLabel(spec.workspace_title)
        self.header_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {colors['text']};")
        self.header_label.setWordWrap(True)
        self.header_label.hide()
        root.addWidget(self.header_label)

        self.hint_label = QLabel(spec.workspace_hint)
        self.hint_label.setProperty("role", "body")
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()
        root.addWidget(self.hint_label)

        self.empty_box = QFrame()
        self.empty_box.setObjectName("ModeEmptyBox")
        self.empty_box.setStyleSheet(
            f"QFrame#ModeEmptyBox {{ background: {colors['card_soft']}; border: 1px dashed {colors['border_strong']}; border-radius: 16px; }}"
        )
        empty_layout = QVBoxLayout(self.empty_box)
        empty_layout.setContentsMargins(18, 18, 18, 18)
        empty_layout.setSpacing(8)
        self.empty_title = QLabel(spec.empty_title)
        self.empty_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.empty_body = QLabel(spec.empty_body)
        self.empty_body.setProperty("role", "body")
        self.empty_body.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_body)
        root.addWidget(self.empty_box)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(14)
        root.addWidget(self.content)

        self.result_box = QFrame()
        self.result_box.setObjectName("ModeResultBox")
        self.result_box.setStyleSheet(
            f"QFrame#ModeResultBox {{ background: {colors['card_muted']}; border: 1px solid {colors['border']}; border-radius: 16px; }}"
        )
        result_layout = QVBoxLayout(self.result_box)
        result_layout.setContentsMargins(16, 14, 16, 14)
        result_layout.setSpacing(6)
        self.result_title = QLabel("Результат режима")
        self.result_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {colors['text']};")
        self.result_body = QLabel("Действие ещё не выполнялось.")
        self.result_body.setObjectName("training-mode-result")
        self.result_body.setProperty("role", "body")
        self.result_body.setWordWrap(True)
        result_layout.addWidget(self.result_title)
        result_layout.addWidget(self.result_body)
        self.content_layout.addWidget(self.result_box)

    def deactivate(self) -> None:
        return

    def set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self.current_ticket = ticket
        self.result_body.setText("Действие ещё не выполнялось.")
        self._set_ticket(ticket)

    def show_evaluation(self, result: TrainingEvaluationResult) -> None:
        if not result.ok:
            self.result_body.setText(result.error or "Проверка завершилась ошибкой.")
            return
        lines = [f"Оценка: {result.score_percent}%"]
        if result.feedback:
            lines.append(result.feedback)
        if result.weak_points:
            lines.append("Слабые места: " + ", ".join(result.weak_points[:4]))
        if result.block_scores:
            lines.append("Блоки госответа:")
            lines.extend(f"• {_block_display_name(code)}: {score}%" for code, score in result.block_scores.items())
        if result.criterion_scores:
            lines.append("Критерии оценки:")
            lines.extend(f"• {_criterion_display_name(code)}: {score}%" for code, score in result.criterion_scores.items())
        if result.followup_questions:
            lines.append("Уточняющие вопросы:")
            lines.extend(f"• {question}" for question in result.followup_questions[:3])
        self.result_body.setText("\n".join(lines))

    def _show_empty(self, title: str | None = None, body: str | None = None) -> None:
        self.empty_title.setText(title or self.spec.empty_title)
        self.empty_body.setText(body or self.spec.empty_body)
        self.empty_box.show()
        self.content.hide()
        self.hint_label.hide()

    def _show_content(self) -> None:
        self.empty_box.hide()
        self.content.show()

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        raise NotImplementedError

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.header_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {colors['text']};")
        self.empty_box.setStyleSheet(
            f"QFrame#ModeEmptyBox {{ background: {colors['card_soft']}; border: 1px dashed {colors['border_strong']}; border-radius: 16px; }}"
        )
        self.empty_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {colors['text']};")
        self.result_box.setStyleSheet(
            f"QFrame#ModeResultBox {{ background: {colors['card_muted']}; border: 1px solid {colors['border']}; border-radius: 16px; }}"
        )
        self.result_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {colors['text']};")


class ReadingWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)

        self.key_points = QLabel()
        self.key_points.setWordWrap(True)
        self.key_points.setProperty("role", "body")
        self.content_layout.insertWidget(0, self.key_points)

        self.reveal_button = QPushButton("Раскрыть эталонный ответ")
        self.reveal_button.setProperty("variant", "secondary")
        self.reveal_button.clicked.connect(self._toggle_answer)
        self.content_layout.insertWidget(1, self.reveal_button)

        self.answer_box = QFrame()
        self.answer_box.setObjectName("ReadingAnswerBox")
        self.answer_box.setStyleSheet(
            f"QFrame#ReadingAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )
        answer_layout = QVBoxLayout(self.answer_box)
        answer_layout.setContentsMargins(16, 14, 16, 14)
        answer_layout.setSpacing(8)
        answer_title = QLabel("Эталон ответа")
        answer_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['text']};")
        self.answer_body = QLabel()
        self.answer_body.setWordWrap(True)
        self.answer_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        answer_layout.addWidget(answer_title)
        answer_layout.addWidget(self.answer_body)
        self.content_layout.insertWidget(2, self.answer_box)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        self.understood_button = QPushButton("Понял")
        self.understood_button.setObjectName("training-reading-understood")
        self.understood_button.setProperty("variant", "primary")
        self.understood_button.clicked.connect(self._submit_understood)
        self.repeat_later_button = QPushButton("Повторить позже")
        self.repeat_later_button.setObjectName("training-reading-repeat")
        self.repeat_later_button.setProperty("variant", "secondary")
        self.repeat_later_button.clicked.connect(self._submit_repeat_later)
        self.next_button = QPushButton("Следующий билет")
        self.next_button.setObjectName("training-reading-next")
        self.next_button.setProperty("variant", "ghost")
        self.next_button.clicked.connect(self.advance_requested.emit)
        actions.addWidget(self.understood_button)
        actions.addWidget(self.repeat_later_button)
        actions.addStretch(1)
        actions.addWidget(self.next_button)
        self.content_layout.insertLayout(3, actions)
        self._show_empty()

    def _toggle_answer(self) -> None:
        visible = not self.answer_box.isVisible()
        self.answer_box.setVisible(visible)
        self.reveal_button.setText("Скрыть эталонный ответ" if visible else "Раскрыть эталонный ответ")

    def _submit_understood(self) -> None:
        if self.current_ticket is None:
            self.result_body.setText("Нет выбранного билета.")
            return
        self.evaluate_requested.emit(_reference_answer(self.current_ticket))

    def _submit_repeat_later(self) -> None:
        self.evaluate_requested.emit("Не смог воспроизвести ключевые смысловые блоки, нужен повтор.")

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        if ticket is None:
            self.answer_box.hide()
            self._show_empty()
            return
        self._show_content()
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            self.key_points.setText(
                "Структура госответа: "
                + ", ".join(block.title for block in ticket.answer_blocks)
            )
        else:
            self.key_points.setText(
                "Ключевые блоки билета: "
                + ", ".join(atom.label for atom in ticket.atoms[:5])
                if ticket.atoms
                else "Ключевые блоки пока не выделены."
            )
        self.answer_body.setText(_reference_answer(ticket) or "Эталонный ответ пока пуст.")
        self.answer_box.hide()
        self.reveal_button.setText("Раскрыть эталонный ответ")

    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.answer_box.setStyleSheet(
            f"QFrame#ReadingAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )


class ActiveRecallWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)

        self.prompt_box = QLabel()
        self.prompt_box.setWordWrap(True)
        self.prompt_box.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
        self.content_layout.insertWidget(0, self.prompt_box)

        self.recall_input = QTextEdit()
        self.recall_input.setObjectName("training-active-recall-input")
        self.recall_input.setProperty("role", "editor")
        self.recall_input.setPlaceholderText("Кратко воспроизведите ответ по памяти, не открывая эталон.")
        self.recall_input.setMinimumHeight(120)
        self.content_layout.insertWidget(1, self.recall_input)

        assessment_row = QHBoxLayout()
        assessment_row.setContentsMargins(0, 0, 0, 0)
        assessment_row.setSpacing(10)
        assessment_label = QLabel("Самооценка:")
        assessment_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {current_colors()['text_secondary']};")
        self.assessment_combo = QComboBox()
        self.assessment_combo.addItem("Выберите самооценку", "")
        self.assessment_combo.addItem("Вспомнил полностью", "full")
        self.assessment_combo.addItem("Вспомнил частично", "partial")
        self.assessment_combo.addItem("Не вспомнил", "miss")
        assessment_row.addWidget(assessment_label)
        assessment_row.addWidget(self.assessment_combo, 1)
        self.content_layout.insertLayout(2, assessment_row)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        self.reveal_button = QPushButton("Показать ответ")
        self.reveal_button.setObjectName("training-active-recall-reveal")
        self.reveal_button.setProperty("variant", "secondary")
        self.reveal_button.clicked.connect(self._toggle_answer)
        self.submit_button = QPushButton("Оценить воспоминание")
        self.submit_button.setObjectName("training-active-recall-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        buttons.addWidget(self.reveal_button)
        buttons.addStretch(1)
        buttons.addWidget(self.submit_button)
        self.content_layout.insertLayout(3, buttons)

        self.answer_box = QFrame()
        self.answer_box.setObjectName("RecallAnswerBox")
        self.answer_box.setStyleSheet(
            f"QFrame#RecallAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )
        answer_layout = QVBoxLayout(self.answer_box)
        answer_layout.setContentsMargins(16, 14, 16, 14)
        answer_layout.setSpacing(8)
        answer_title = QLabel("Эталон после попытки")
        answer_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['text']};")
        self.answer_body = QLabel()
        self.answer_body.setWordWrap(True)
        self.answer_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        answer_layout.addWidget(answer_title)
        answer_layout.addWidget(self.answer_body)
        self.content_layout.insertWidget(4, self.answer_box)
        self._show_empty()

    def _toggle_answer(self) -> None:
        visible = not self.answer_box.isVisible()
        self.answer_box.setVisible(visible)
        self.reveal_button.setText("Скрыть ответ" if visible else "Показать ответ")

    def _submit(self) -> None:
        rating = self.assessment_combo.currentData()
        if not rating:
            self.result_body.setText("Сначала выберите самооценку воспоминания.")
            return
        answer_text = self.recall_input.toPlainText().strip()
        if not answer_text and rating != "miss":
            self.result_body.setText("Сначала попробуйте вспомнить ответ своими словами.")
            return
        if not answer_text and rating == "miss":
            answer_text = "Не вспомнил ответ по билету."
        answer_text = f"{answer_text}\nСамооценка: {self.assessment_combo.currentText()}".strip()
        self.evaluate_requested.emit(answer_text)

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        if ticket is None:
            self.answer_box.hide()
            self._show_empty()
            return
        self._show_content()
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            target_blocks = ticket.answer_blocks[:2]
            self.prompt_box.setText(
                "Вспомните сначала вводную и теоретическую часть ответа: "
                + ", ".join(block.title.lower() for block in target_blocks)
            )
        else:
            self.prompt_box.setText(f"Вопрос: {ticket.title}")
        self.answer_body.setText(_reference_answer(ticket) or "Эталонный ответ пока пуст.")
        self.recall_input.clear()
        self.assessment_combo.setCurrentIndex(0)
        self.answer_box.hide()
        self.reveal_button.setText("Показать ответ")

    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.prompt_box.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
        self.answer_box.setStyleSheet(
            f"QFrame#RecallAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )


class ClozeWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)
        self.prompts: list[ClozePrompt] = []
        self.inputs: list[QLineEdit] = []

        self.cloze_grid = QGridLayout()
        self.cloze_grid.setContentsMargins(0, 0, 0, 0)
        self.cloze_grid.setHorizontalSpacing(10)
        self.cloze_grid.setVerticalSpacing(10)
        self.content_layout.insertLayout(0, self.cloze_grid)

        self.submit_button = QPushButton("Проверить пропуски")
        self.submit_button.setObjectName("training-cloze-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        self.content_layout.insertWidget(1, self.submit_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._show_empty()

    def _build_prompts(self, ticket: TicketKnowledgeMap) -> list[ClozePrompt]:
        prompts: list[ClozePrompt] = []
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            for block in ticket.answer_blocks[:3]:
                if block.is_missing:
                    continue
                answer = _pick_keyword_from_text(block.expected_content)
                if not answer:
                    continue
                masked_text = re.sub(re.escape(answer), "____", block.expected_content, count=1, flags=re.IGNORECASE)
                if masked_text == block.expected_content:
                    continue
                prompts.append(ClozePrompt(block.expected_content, f"{block.title}: {masked_text}", answer))
            return prompts
        for atom in ticket.atoms[:3]:
            answer = _pick_keyword(atom)
            if not answer:
                continue
            masked_text = re.sub(re.escape(answer), "____", atom.text, count=1, flags=re.IGNORECASE)
            if masked_text == atom.text:
                continue
            prompts.append(ClozePrompt(atom.text, masked_text, answer))
        return prompts

    def _clear_grid(self) -> None:
        while self.cloze_grid.count():
            item = self.cloze_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _submit(self) -> None:
        if not self.prompts:
            self.result_body.setText("Для этого билета не удалось построить пропуски.")
            return
        values = [field.text().strip() for field in self.inputs]
        if any(not value for value in values):
            self.result_body.setText("Заполните все пропуски перед проверкой.")
            return
        reconstructed = []
        exact = 0
        for prompt, value in zip(self.prompts, values):
            reconstructed.append(prompt.original_text.replace(prompt.answer, value, 1))
            if value.lower() == prompt.answer.lower():
                exact += 1
        self.result_body.setText("Проверяем ответ...")
        self.evaluate_requested.emit("\n".join(reconstructed))

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self._clear_grid()
        self.inputs = []
        self.prompts = []
        if ticket is None:
            self._show_empty()
            return
        self.prompts = self._build_prompts(ticket)
        if not self.prompts:
            self._show_empty(body="Для этого режима нужен билет с текстами, где можно честно построить смысловые пропуски.")
            return
        self._show_content()
        for index, prompt in enumerate(self.prompts):
            label = QLabel(prompt.masked_text)
            label.setWordWrap(True)
            label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {current_colors()['text']};")
            field = QLineEdit()
            field.setProperty("role", "form-input")
            field.setPlaceholderText("Заполните пропуск")
            self.cloze_grid.addWidget(label, index, 0)
            self.cloze_grid.addWidget(field, index, 1)
            self.inputs.append(field)


class MatchingWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        self.content_layout.insertLayout(0, self.rows_layout)
        self.controls: list[tuple[str, str, QComboBox]] = []

        self.submit_button = QPushButton("Проверить пары")
        self.submit_button.setObjectName("training-matching-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        self.content_layout.insertWidget(1, self.submit_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._show_empty()

    def _clear_rows(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif layout is not None:
                while layout.count():
                    child = layout.takeAt(0)
                    child_widget = child.widget()
                    if child_widget is not None:
                        child_widget.deleteLater()

    def _submit(self) -> None:
        if not self.controls:
            self.result_body.setText("Для выбранного билета нет пар для сопоставления.")
            return
        lines: list[str] = []
        correct = 0
        for term, expected, combo in self.controls:
            selected = combo.currentData()
            if not selected:
                self.result_body.setText("Соотнесите все термины перед проверкой.")
                return
            lines.append(f"{term}: {selected}")
            if selected == expected:
                correct += 1
        self.result_body.setText("Проверяем ответ...")
        self.evaluate_requested.emit("\n".join(lines))

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self._clear_rows()
        self.controls = []
        if ticket is None:
            self._show_empty()
            return
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            pairs = [(block.title, _compact(block.expected_content, 110)) for block in ticket.answer_blocks if not block.is_missing][:4]
        else:
            atoms = ticket.atoms[:4]
            pairs = [(atom.label, _compact(atom.text, 110)) for atom in atoms]
        if len(pairs) < 2:
            self._show_empty(body="Для сопоставления нужен билет минимум с двумя содержательными атомами знания.")
            return
        self._show_content()
        definitions = [definition for _, definition in pairs]
        shuffled = definitions[:]
        Random(_seed_for(ticket.ticket_id, "matching")).shuffle(shuffled)
        for term_text, expected in pairs:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            term = QLabel(term_text)
            term.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {current_colors()['text']};")
            term.setMinimumWidth(180)
            combo = QComboBox()
            combo.addItem("Выберите определение", "")
            for definition in shuffled:
                combo.addItem(definition, definition)
            row.addWidget(term)
            row.addWidget(combo, 1)
            self.rows_layout.addLayout(row)
            self.controls.append((term_text, expected, combo))


class PlanWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)
        self.blocks: list[str] = []
        self.correct_order: list[str] = []

        self.blocks_layout = QVBoxLayout()
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(10)
        self.content_layout.insertLayout(0, self.blocks_layout)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)
        self.reset_button = QPushButton("Сбросить порядок")
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.clicked.connect(self._reset_order)
        self.submit_button = QPushButton("Проверить порядок")
        self.submit_button.setObjectName("training-plan-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        controls.addWidget(self.submit_button)
        self.content_layout.insertLayout(1, controls)
        self._show_empty()

    def _render_blocks(self) -> None:
        while self.blocks_layout.count():
            item = self.blocks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, block in enumerate(self.blocks):
            card = QFrame()
            card.setObjectName("PlanBlockCard")
            card.setStyleSheet(
                f"QFrame#PlanBlockCard {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 14px; }}"
            )
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)
            row.setSpacing(10)
            position = QLabel(str(index + 1))
            position.setFixedWidth(22)
            position.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['primary']};")
            body = QLabel(block)
            body.setWordWrap(True)
            body.setStyleSheet(f"font-size: 14px; color: {current_colors()['text']};")
            up = QPushButton("↑")
            down = QPushButton("↓")
            up.setEnabled(index > 0)
            down.setEnabled(index < len(self.blocks) - 1)
            up.clicked.connect(lambda _, i=index: self._move_block(i, -1))
            down.clicked.connect(lambda _, i=index: self._move_block(i, 1))
            row.addWidget(position)
            row.addWidget(body, 1)
            row.addWidget(up)
            row.addWidget(down)
            self.blocks_layout.addWidget(card)

    def _move_block(self, index: int, delta: int) -> None:
        target = index + delta
        if target < 0 or target >= len(self.blocks):
            return
        self.blocks[index], self.blocks[target] = self.blocks[target], self.blocks[index]
        self._render_blocks()

    def _reset_order(self) -> None:
        if not self.correct_order:
            return
        self.blocks = self.correct_order[:]
        Random(_seed_for(self.current_ticket.ticket_id if self.current_ticket else "empty", "plan")).shuffle(self.blocks)
        self._render_blocks()

    def _submit(self) -> None:
        if not self.blocks:
            self.result_body.setText("Нет тезисов для проверки порядка.")
            return
        exact = sum(1 for current, expected in zip(self.blocks, self.correct_order) if current == expected)
        self.result_body.setText("Проверяем ответ...")
        self.evaluate_requested.emit("\n".join(self.blocks))

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self.blocks = []
        self.correct_order = []
        if ticket is None:
            self._show_empty()
            return
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            blocks = [block.title for block in ticket.answer_blocks]
        else:
            blocks = [_compact(atom.text, 120) for atom in ticket.atoms[:5] if atom.text.strip()]
        if len(blocks) < 2:
            self._show_empty(body="Для сборки плана нужен билет минимум с двумя тезисами или шагами ответа.")
            return
        self._show_content()
        self.correct_order = blocks
        self.blocks = blocks[:]
        Random(_seed_for(ticket.ticket_id, "plan")).shuffle(self.blocks)
        self._render_blocks()

    def refresh_theme(self) -> None:
        super().refresh_theme()
        if self.blocks:
            self._render_blocks()


class MiniExamWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)
        self.seconds_left = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)
        self.timer_badge = QLabel("Таймер: --:--")
        self.timer_badge.setObjectName("training-mini-exam-timer")
        self.timer_badge.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['danger']};")
        self.ticket_badge = QLabel("Экзаменационный билет не выбран")
        self.ticket_badge.setObjectName("training-mini-exam-ticket")
        self.ticket_badge.setProperty("role", "body")
        status_row.addWidget(self.timer_badge)
        status_row.addWidget(self.ticket_badge, 1)
        self.content_layout.insertLayout(0, status_row)

        self.answer_input = QTextEdit()
        self.answer_input.setObjectName("training-mini-exam-input")
        self.answer_input.setProperty("role", "editor")
        self.answer_input.setPlaceholderText("Дайте полный ответ по билету в экзаменационном режиме.")
        self.answer_input.setMinimumHeight(240)
        self.content_layout.insertWidget(1, self.answer_input)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        self.random_button = QPushButton("Случайный билет")
        self.random_button.setObjectName("training-mini-exam-random")
        self.random_button.setProperty("variant", "secondary")
        self.random_button.clicked.connect(self.random_requested.emit)
        self.reset_button = QPushButton("Сбросить таймер")
        self.reset_button.setObjectName("training-mini-exam-reset")
        self.reset_button.setProperty("variant", "ghost")
        self.reset_button.clicked.connect(self._restart_timer)
        self.submit_button = QPushButton("Завершить мини-экзамен")
        self.submit_button.setObjectName("training-mini-exam-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        buttons.addWidget(self.random_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.submit_button)
        self.content_layout.insertLayout(2, buttons)
        self._show_empty()

    def deactivate(self) -> None:
        self.timer.stop()

    def _format_time(self) -> str:
        minutes, seconds = divmod(max(self.seconds_left, 0), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _tick(self) -> None:
        self.seconds_left -= 1
        self.timer_badge.setText(f"Таймер: {self._format_time()}")
        if self.seconds_left <= 0:
            self.timer.stop()
            self.result_body.setText("Время вышло. Можно завершить ответ и посмотреть разбор.")

    def _restart_timer(self) -> None:
        if self.current_ticket is None:
            return
        self.seconds_left = max(120, min(600, int(self.current_ticket.estimated_oral_time_sec or 180)))
        self.timer_badge.setText(f"Таймер: {self._format_time()}")
        self.timer.start(1000)

    def _submit(self) -> None:
        answer_text = self.answer_input.toPlainText().strip()
        if not answer_text:
            self.result_body.setText("Мини-экзамен требует полного ответа в текстовом поле.")
            return
        self.timer.stop()
        self.evaluate_requested.emit(answer_text)

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self.answer_input.clear()
        if ticket is None:
            self.timer.stop()
            self._show_empty()
            return
        self._show_content()
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN:
            self.ticket_badge.setText(f"Госэкзамен: {ticket.title}")
            self.answer_input.setPlaceholderText("Дайте полный ответ так, чтобы закрыть введение, теорию, практику, навыки, вывод и дополнительные элементы.")
        else:
            self.ticket_badge.setText(f"Случайный билет: {ticket.title}")
            self.answer_input.setPlaceholderText("Дайте полный ответ по билету в экзаменационном режиме.")
        self._restart_timer()

    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.timer_badge.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['danger']};")


class StateExamFullWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)
        self.block_inputs: dict[AnswerBlockCode, QTextEdit] = {}
        self.block_rows: dict[AnswerBlockCode, QLabel] = {}

        self.blocks_layout = QVBoxLayout()
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(12)
        self.content_layout.insertLayout(0, self.blocks_layout)

        self.submit_button = QPushButton("Проверить полный госответ")
        self.submit_button.setObjectName("training-state-exam-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        self.content_layout.insertWidget(1, self.submit_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._show_empty()

    def show_evaluation(self, result: TrainingEvaluationResult) -> None:
        super().show_evaluation(result)
        if not result.ok:
            return
        for code, label in self.block_rows.items():
            score = result.block_scores.get(code.value)
            if score is None:
                continue
            label.setText(f"{label.property('baseTitle')} • {score}%")

    def _clear_blocks(self) -> None:
        while self.blocks_layout.count():
            item = self.blocks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.block_inputs.clear()
        self.block_rows.clear()

    def _submit(self) -> None:
        if self.current_ticket is None or not self.current_ticket.answer_blocks:
            self.result_body.setText("Для этого режима нужен билет с профилем госэкзамена.")
            return
        parts: list[str] = []
        for block in self.current_ticket.answer_blocks:
            field = self.block_inputs.get(block.block_code)
            text = field.toPlainText().strip() if field is not None else ""
            if text:
                parts.append(f"{block.title}: {text}")
        if not parts:
            self.result_body.setText("Заполните хотя бы один блок ответа перед проверкой.")
            return
        self.evaluate_requested.emit("\n\n".join(parts))

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self._clear_blocks()
        self.hint_label.setText(self.spec.workspace_hint)
        self.hint_label.show()
        if ticket is None:
            self._show_empty()
            return
        if ticket.answer_profile_code != AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN or not ticket.answer_blocks:
            self._show_empty(body="Для полного госответа нужен билет, импортированный с профилем «Госэкзамен».")
            return
        self._show_content()
        profile = get_answer_profile(ticket.answer_profile_code)
        self.hint_label.setText(profile.mode_hints.get("state-exam-full", self.spec.workspace_hint))
        for block in ticket.answer_blocks:
            card = QFrame()
            card.setObjectName("StateExamBlockCard")
            card.setStyleSheet(
                f"QFrame#StateExamBlockCard {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(8)
            title = QLabel(block.title)
            title.setProperty("baseTitle", block.title)
            title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['text']};")
            hint = QLabel(
                "Пробел в источнике. Подготовьте этот блок отдельно."
                if block.is_missing
                else _compact(block.expected_content, 140)
            )
            hint.setProperty("role", "body")
            hint.setWordWrap(True)
            field = QTextEdit()
            field.setProperty("role", "editor")
            field.setPlaceholderText(f"Введите свою часть ответа для блока «{block.title.lower()}».")
            field.setMinimumHeight(96)
            card_layout.addWidget(title)
            card_layout.addWidget(hint)
            card_layout.addWidget(field)
            self.blocks_layout.addWidget(card)
            self.block_inputs[block.block_code] = field
            self.block_rows[block.block_code] = title

    def refresh_theme(self) -> None:
        super().refresh_theme()
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)


def create_training_workspaces() -> dict[str, TrainingWorkspaceBase]:
    return {
        "reading": ReadingWorkspace(TRAINING_MODE_SPECS["reading"]),
        "active-recall": ActiveRecallWorkspace(TRAINING_MODE_SPECS["active-recall"]),
        "cloze": ClozeWorkspace(TRAINING_MODE_SPECS["cloze"]),
        "matching": MatchingWorkspace(TRAINING_MODE_SPECS["matching"]),
        "plan": PlanWorkspace(TRAINING_MODE_SPECS["plan"]),
        "mini-exam": MiniExamWorkspace(TRAINING_MODE_SPECS["mini-exam"]),
        "state-exam-full": StateExamFullWorkspace(TRAINING_MODE_SPECS["state-exam-full"]),
    }
