from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from application.defense_ui_data import DefenseEvaluationResult, DefenseProcessingResult, DefenseWorkspaceSnapshot
from ui.components.common import CardFrame, IconBadge


PROFILE_OPTIONS = [
    ("research", "Исследовательская работа"),
    ("applied", "Прикладная работа"),
    ("legal_humanities", "Право и гуманитарный профиль"),
]

MODE_OPTIONS = [
    ("speech_5", "Доклад на 5 минут"),
    ("speech_7", "Доклад на 7 минут"),
    ("speech_10", "Доклад на 10 минут"),
    ("persona_qa", "Вопросы комиссии"),
    ("full_mock_defense", "Полная репетиция защиты"),
]

CLAIM_LABELS = {
    "problem": "Проблема",
    "relevance": "Актуальность",
    "object": "Объект",
    "subject": "Предмет",
    "goal": "Цель",
    "tasks": "Задачи",
    "methods": "Методы",
    "novelty": "Новизна",
    "practical_significance": "Практическая значимость",
    "results": "Результаты",
    "limitations": "Ограничения",
    "personal_contribution": "Личный вклад",
    "risk_topic": "Риск-тема",
}

PERSONA_LABELS = {
    "scientific_advisor": "Научрук",
    "opponent": "Оппонент",
    "commission": "Комиссия",
}

SOURCE_KIND_LABELS = {
    "thesis": "Диссертация",
    "notes": "Заметки",
    "slides": "Слайды",
}

PROJECT_STATUS_LABELS = {
    "draft": "Черновик",
    "ready_for_rehearsal": "Готов к репетиции",
}


class DefenseView(QWidget):
    activate_requested = Signal(str)
    create_project_requested = Signal(object)
    project_selected = Signal(str)
    import_requested = Signal(str)
    evaluate_requested = Signal(str, str, str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.snapshot: DefenseWorkspaceSnapshot | None = None
        self.current_project_id = ""
        self._processing = False
        self._processing_result: DefenseProcessingResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(14)

        header_box = QVBoxLayout()
        header_box.setContentsMargins(0, 0, 0, 0)
        header_box.setSpacing(4)
        title = QLabel("Подготовка к защите")
        title.setProperty("role", "hero")
        header_box.addWidget(title)

        subtitle = QLabel("Платный локальный модуль подготовки к защите магистерской")
        subtitle.setProperty("role", "body")
        subtitle.setWordWrap(True)
        header_box.addWidget(subtitle)
        header_row.addLayout(header_box, 1)

        self.license_pill = QLabel("Не активировано")
        self.license_pill.setProperty("role", "pill")
        header_row.addWidget(self.license_pill, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        self.status_card = CardFrame(role="subtle-card", shadow_color=shadow_color, shadow=False)
        status_layout = QHBoxLayout(self.status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(14)
        status_layout.addWidget(IconBadge("PM", "#EEF6FF", "#2E78E6", size=42, radius=13, font_size=11), 0, Qt.AlignmentFlag.AlignTop)

        status_text = QVBoxLayout()
        status_text.setContentsMargins(0, 0, 0, 0)
        status_text.setSpacing(4)
        self.recommendation_label = QLabel("Рекомендация по модели")
        self.recommendation_label.setProperty("role", "section-title")
        status_text.addWidget(self.recommendation_label)

        self.recommendation_body = QLabel("")
        self.recommendation_body.setProperty("role", "body")
        self.recommendation_body.setWordWrap(True)
        status_text.addWidget(self.recommendation_body)

        self.install_label = QLabel("")
        self.install_label.setProperty("role", "muted")
        self.install_label.setWordWrap(True)
        status_text.addWidget(self.install_label)
        status_layout.addLayout(status_text, 1)
        layout.addWidget(self.status_card)

        self.paywall_card = CardFrame(role="card", shadow_color=shadow_color)
        paywall_layout = QVBoxLayout(self.paywall_card)
        paywall_layout.setContentsMargins(22, 22, 22, 22)
        paywall_layout.setSpacing(12)

        paywall_title = QLabel("Доступ к модулю")
        paywall_title.setProperty("role", "section-title")
        paywall_layout.addWidget(paywall_title)

        paywall_body = QLabel(
            "Этот раздел закрыт платным доступом. Здесь доступна локальная подготовка к защите: разбор текста, "
            "карта защиты, текст доклада, вопросы комиссии и репетиция защиты."
        )
        paywall_body.setProperty("role", "body")
        paywall_body.setWordWrap(True)
        paywall_layout.addWidget(paywall_body)

        self.paywall_amount = QLabel("")
        self.paywall_amount.setStyleSheet("font-size: 18px; font-weight: 800; color: #035F46;")
        paywall_layout.addWidget(self.paywall_amount)

        self.paywall_status = QLabel("Оплата в приложении не встроена. Введите выданный ключ активации.")
        self.paywall_status.setProperty("role", "body")
        self.paywall_status.setWordWrap(True)
        paywall_layout.addWidget(self.paywall_status)

        activation_row = QHBoxLayout()
        activation_row.setContentsMargins(0, 0, 0, 0)
        activation_row.setSpacing(10)
        self.activation_input = QLineEdit()
        self.activation_input.setObjectName("defense-code")
        self.activation_input.setPlaceholderText("Ключ активации модуля")
        activation_row.addWidget(self.activation_input, 1)

        self.activate_button = QPushButton("Активировать модуль")
        self.activate_button.setObjectName("defense-activate")
        self.activate_button.setProperty("variant", "primary")
        self.activate_button.clicked.connect(self._emit_activate)
        activation_row.addWidget(self.activate_button)
        paywall_layout.addLayout(activation_row)
        layout.addWidget(self.paywall_card)

        self.workspace = QWidget()
        workspace_layout = QVBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        projects_card = CardFrame(role="card", shadow_color=shadow_color)
        projects_layout = QVBoxLayout(projects_card)
        projects_layout.setContentsMargins(18, 18, 18, 18)
        projects_layout.setSpacing(12)

        projects_title = QLabel("Проекты защиты")
        projects_title.setProperty("role", "section-title")
        projects_layout.addWidget(projects_title)

        self.projects_empty = QLabel("Пока нет ни одного проекта подготовки.")
        self.projects_empty.setProperty("role", "body")
        self.projects_empty.setWordWrap(True)
        projects_layout.addWidget(self.projects_empty)

        self.projects_group = QButtonGroup(self)
        self.projects_group.setExclusive(True)
        self.projects_layout = QVBoxLayout()
        self.projects_layout.setContentsMargins(0, 0, 0, 0)
        self.projects_layout.setSpacing(8)
        projects_layout.addLayout(self.projects_layout)
        top_row.addWidget(projects_card, 2)

        create_card = CardFrame(role="card", shadow_color=shadow_color)
        create_layout = QVBoxLayout(create_card)
        create_layout.setContentsMargins(18, 18, 18, 18)
        create_layout.setSpacing(12)

        create_title = QLabel("Создать проект")
        create_title.setProperty("role", "section-title")
        create_layout.addWidget(create_title)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.project_title_input = QLineEdit()
        self.project_title_input.setObjectName("defense-project-title")
        form.addRow("Тема работы", self.project_title_input)

        self.student_input = QLineEdit()
        form.addRow("Студент", self.student_input)

        self.specialty_input = QLineEdit()
        form.addRow("Направление", self.specialty_input)

        self.supervisor_input = QLineEdit()
        form.addRow("Научрук", self.supervisor_input)

        self.defense_date_input = QLineEdit()
        self.defense_date_input.setPlaceholderText("2026-06-01")
        form.addRow("Дата защиты", self.defense_date_input)

        self.profile_combo = QComboBox()
        for value, label in PROFILE_OPTIONS:
            self.profile_combo.addItem(label, value)
        form.addRow("Профиль", self.profile_combo)
        create_layout.addLayout(form)

        self.create_button = QPushButton("Создать проект защиты")
        self.create_button.setObjectName("defense-create")
        self.create_button.setProperty("variant", "primary")
        self.create_button.clicked.connect(self._emit_create_project)
        create_layout.addWidget(self.create_button, 0, Qt.AlignmentFlag.AlignLeft)
        top_row.addWidget(create_card, 3)
        workspace_layout.addLayout(top_row)

        self.project_card = CardFrame(role="card", shadow_color=shadow_color)
        project_layout = QVBoxLayout(self.project_card)
        project_layout.setContentsMargins(20, 20, 20, 20)
        project_layout.setSpacing(12)

        project_header = QHBoxLayout()
        project_header.setContentsMargins(0, 0, 0, 0)
        project_header.setSpacing(10)
        self.project_title = QLabel("Проект не выбран")
        self.project_title.setProperty("role", "section-title")
        project_header.addWidget(self.project_title)
        project_header.addStretch(1)

        self.import_button = QPushButton("Импортировать материалы")
        self.import_button.setObjectName("defense-import-materials")
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self._emit_import)
        project_header.addWidget(self.import_button)
        project_layout.addLayout(project_header)

        self.project_meta = QLabel("Создайте проект и загрузите диссертацию, заметки или PPTX.")
        self.project_meta.setProperty("role", "body")
        self.project_meta.setWordWrap(True)
        project_layout.addWidget(self.project_meta)

        self.sources_label = QLabel("Материалы пока не загружены.")
        self.sources_label.setProperty("role", "body")
        self.sources_label.setWordWrap(True)
        project_layout.addWidget(self.sources_label)

        self.processing_status = QLabel("")
        self.processing_status.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.processing_status.hide()
        project_layout.addWidget(self.processing_status)

        self.processing_progress = QProgressBar()
        self.processing_progress.setRange(0, 100)
        self.processing_progress.setTextVisible(False)
        self.processing_progress.setFixedHeight(12)
        self.processing_progress.hide()
        project_layout.addWidget(self.processing_progress)

        self.processing_meta = QLabel("")
        self.processing_meta.setProperty("role", "body")
        self.processing_meta.setWordWrap(True)
        self.processing_meta.hide()
        project_layout.addWidget(self.processing_meta)

        self.processing_result = QLabel("")
        self.processing_result.setProperty("role", "muted")
        self.processing_result.setWordWrap(True)
        self.processing_result.hide()
        project_layout.addWidget(self.processing_result)
        workspace_layout.addWidget(self.project_card)

        self.claims_card = CardFrame(role="card", shadow_color=shadow_color)
        claims_layout = QVBoxLayout(self.claims_card)
        claims_layout.setContentsMargins(20, 20, 20, 20)
        claims_layout.setSpacing(10)
        claims_title = QLabel("Карта защиты")
        claims_title.setProperty("role", "section-title")
        claims_layout.addWidget(claims_title)
        self.claims_label = QLabel("Сначала загрузите материалы проекта.")
        self.claims_label.setProperty("role", "body")
        self.claims_label.setWordWrap(True)
        claims_layout.addWidget(self.claims_label)
        workspace_layout.addWidget(self.claims_card)

        outline_row = QHBoxLayout()
        outline_row.setContentsMargins(0, 0, 0, 0)
        outline_row.setSpacing(16)

        outline_card = CardFrame(role="card", shadow_color=shadow_color)
        outline_layout = QVBoxLayout(outline_card)
        outline_layout.setContentsMargins(20, 20, 20, 20)
        outline_layout.setSpacing(10)
        outline_head = QHBoxLayout()
        outline_head.setContentsMargins(0, 0, 0, 0)
        outline_head.setSpacing(10)
        outline_title = QLabel("Текст доклада")
        outline_title.setProperty("role", "section-title")
        outline_head.addWidget(outline_title)
        outline_head.addStretch(1)
        self.duration_combo = QComboBox()
        self.duration_combo.setObjectName("defense-duration")
        self.duration_combo.addItem("5 минут", "5")
        self.duration_combo.addItem("7 минут", "7")
        self.duration_combo.addItem("10 минут", "10")
        self.duration_combo.currentIndexChanged.connect(self._refresh_outline)
        outline_head.addWidget(self.duration_combo)
        outline_layout.addLayout(outline_head)
        self.outline_label = QLabel("Контур доклада появится после обработки материалов.")
        self.outline_label.setProperty("role", "body")
        self.outline_label.setWordWrap(True)
        outline_layout.addWidget(self.outline_label)
        outline_row.addWidget(outline_card, 1)

        slides_card = CardFrame(role="card", shadow_color=shadow_color)
        slides_layout = QVBoxLayout(slides_card)
        slides_layout.setContentsMargins(20, 20, 20, 20)
        slides_layout.setSpacing(10)
        slides_title = QLabel("План слайдов")
        slides_title.setProperty("role", "section-title")
        slides_layout.addWidget(slides_title)
        self.slides_label = QLabel("План слайдов ещё не собран.")
        self.slides_label.setProperty("role", "body")
        self.slides_label.setWordWrap(True)
        slides_layout.addWidget(self.slides_label)
        outline_row.addWidget(slides_card, 1)
        workspace_layout.addLayout(outline_row)

        questions_card = CardFrame(role="card", shadow_color=shadow_color)
        questions_layout = QVBoxLayout(questions_card)
        questions_layout.setContentsMargins(20, 20, 20, 20)
        questions_layout.setSpacing(10)
        questions_title = QLabel("Вопросы комиссии")
        questions_title.setProperty("role", "section-title")
        questions_layout.addWidget(questions_title)
        self.questions_label = QLabel("Вопросы появятся после обработки материалов.")
        self.questions_label.setProperty("role", "body")
        self.questions_label.setWordWrap(True)
        questions_layout.addWidget(self.questions_label)
        workspace_layout.addWidget(questions_card)

        mock_card = CardFrame(role="card", shadow_color=shadow_color)
        mock_layout = QVBoxLayout(mock_card)
        mock_layout.setContentsMargins(20, 20, 20, 20)
        mock_layout.setSpacing(10)

        mock_head = QHBoxLayout()
        mock_head.setContentsMargins(0, 0, 0, 0)
        mock_head.setSpacing(10)
        mock_title = QLabel("Имитация защиты")
        mock_title.setProperty("role", "section-title")
        mock_head.addWidget(mock_title)
        mock_head.addStretch(1)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("defense-mode")
        for value, label in MODE_OPTIONS:
            self.mode_combo.addItem(label, value)
        mock_head.addWidget(self.mode_combo)
        mock_layout.addLayout(mock_head)

        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Введите текст доклада или ответ на вопрос комиссии.")
        self.answer_input.setMinimumHeight(140)
        mock_layout.addWidget(self.answer_input)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)
        self.evaluate_button = QPushButton("Оценить ответ")
        self.evaluate_button.setObjectName("defense-evaluate")
        self.evaluate_button.setProperty("variant", "primary")
        self.evaluate_button.clicked.connect(self._emit_evaluate)
        action_row.addWidget(self.evaluate_button)
        action_row.addStretch(1)
        mock_layout.addLayout(action_row)

        self.evaluation_label = QLabel("Здесь появится разбор репетиции защиты.")
        self.evaluation_label.setProperty("role", "body")
        self.evaluation_label.setWordWrap(True)
        mock_layout.addWidget(self.evaluation_label)
        workspace_layout.addWidget(mock_card)

        weak_card = CardFrame(role="card", shadow_color=shadow_color)
        weak_layout = QVBoxLayout(weak_card)
        weak_layout.setContentsMargins(20, 20, 20, 20)
        weak_layout.setSpacing(10)
        weak_title = QLabel("Слабые места")
        weak_title.setProperty("role", "section-title")
        weak_layout.addWidget(weak_title)
        self.weak_label = QLabel("После репетиции защиты здесь появятся рискованные зоны.")
        self.weak_label.setProperty("role", "body")
        self.weak_label.setWordWrap(True)
        weak_layout.addWidget(self.weak_label)
        workspace_layout.addWidget(weak_card)

        layout.addWidget(self.workspace)
        self.workspace.hide()

    def set_snapshot(self, snapshot: DefenseWorkspaceSnapshot) -> None:
        self.snapshot = snapshot
        self.current_project_id = snapshot.active_project.project.project_id if snapshot.active_project else ""
        self.paywall_amount.setText(f"Доступ: {snapshot.paywall_amount_label}")
        self.install_label.setText(f"Идентификатор установки: {snapshot.install_id}")
        self.recommendation_label.setText(snapshot.recommendation.label)
        self.recommendation_body.setText(snapshot.recommendation.rationale)

        activated = snapshot.license_state.activated
        self.license_pill.setText("Модуль активирован" if activated else "Модуль закрыт")
        self.paywall_status.setText(
            "Лицензия активирована локально. Материалы проекта остаются на этом компьютере."
            if activated
            else "Оплата в приложении не встроена. Введите выданный ключ активации."
        )
        self.paywall_card.setVisible(not activated)
        self.workspace.setVisible(activated)
        self._render_projects(snapshot)
        self._render_active_project(snapshot)

    def is_processing(self) -> bool:
        return self._processing

    def set_activation_pending(self, pending: bool) -> None:
        self.activate_button.setEnabled(not pending)
        self.activate_button.setText("Проверяем ключ..." if pending else "Активировать модуль")

    def set_processing_pending(self, project_title: str) -> None:
        self._processing = True
        self.processing_status.setText(f"Идёт обработка материалов: {project_title}")
        self.processing_status.show()
        self.processing_progress.setValue(0)
        self.processing_progress.show()
        self.processing_meta.setText("Импорт и разбор идут в фоне.")
        self.processing_meta.show()
        self.processing_result.hide()
        self.import_button.setEnabled(False)

    def set_processing_progress(self, percent: int, stage: str, detail: str = "") -> None:
        self.processing_status.setText(stage)
        self.processing_progress.setValue(max(0, min(100, percent)))
        self.processing_meta.setText(detail or "Идёт фоновая локальная обработка.")

    def show_processing_result(self, result: DefenseProcessingResult) -> None:
        self._processing = False
        self._processing_result = result
        self.import_button.setEnabled(True)
        self.processing_status.setText("Обработка материалов завершена" if result.ok else "Обработка материалов завершилась с ошибкой")
        self.processing_status.show()
        self.processing_progress.setValue(100 if result.ok else self.processing_progress.value())
        self.processing_progress.show()
        details = [result.message] if result.message else []
        if result.warnings:
            details.append("Предупреждения:")
            details.extend(f"• {warning}" for warning in result.warnings[:4])
        if result.error:
            details.append(f"Ошибка: {result.error}")
        self.processing_result.setText("\n".join(details))
        self.processing_result.show()

    def set_evaluation_pending(self, pending: bool) -> None:
        self.evaluate_button.setEnabled(not pending)
        self.evaluate_button.setText("Оцениваем..." if pending else "Оценить ответ")

    def show_evaluation_result(self, result: DefenseEvaluationResult) -> None:
        if not result.ok:
            self.evaluation_label.setText(result.error or "Не удалось оценить ответ.")
            return
        lines = [result.summary]
        if result.weak_points:
            lines.append("")
            lines.append("Слабые места:")
            lines.extend(f"• {item}" for item in result.weak_points)
        if result.followup_questions:
            lines.append("")
            lines.append("Следующие вопросы комиссии:")
            lines.extend(f"• {item}" for item in result.followup_questions)
        self.evaluation_label.setText("\n".join(lines))

    def _render_projects(self, snapshot: DefenseWorkspaceSnapshot) -> None:
        while self.projects_layout.count():
            item = self.projects_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for button in list(self.projects_group.buttons()):
            self.projects_group.removeButton(button)

        self.projects_empty.setVisible(not snapshot.projects)
        for project in snapshot.projects:
            button = QPushButton(project.title)
            button.setObjectName(f"defense-project-{project.project_id}")
            button.setCheckable(True)
            button.setChecked(project.project_id == self.current_project_id)
            button.setProperty("variant", "nav")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, value=project.project_id: self.project_selected.emit(value))
            self.projects_group.addButton(button)
            status_label = PROJECT_STATUS_LABELS.get(project.status, project.status)
            meta = QLabel(f"{status_label} • материалов: {project.source_count} • обновлён: {project.updated_label}")
            meta.setProperty("role", "muted")
            meta.setWordWrap(True)
            box = QVBoxLayout()
            box.setContentsMargins(0, 0, 0, 8)
            box.setSpacing(4)
            box.addWidget(button)
            box.addWidget(meta)
            host = QWidget()
            host.setLayout(box)
            self.projects_layout.addWidget(host)
        self.projects_layout.addStretch(1)

    def _render_active_project(self, snapshot: DefenseWorkspaceSnapshot) -> None:
        project = snapshot.active_project
        if project is None:
            self.project_title.setText("Проект не выбран")
            self.project_meta.setText("Создайте проект и затем импортируйте диссертацию, заметки или PPTX.")
            self.sources_label.setText("Материалы пока не загружены.")
            self.import_button.setEnabled(False)
            self.processing_status.hide()
            self.processing_progress.hide()
            self.processing_meta.hide()
            self.processing_result.hide()
            self.claims_label.setText("Сначала загрузите материалы проекта.")
            self.outline_label.setText("Контур доклада появится после обработки материалов.")
            self.slides_label.setText("План слайдов ещё не собран.")
            self.questions_label.setText("Вопросы появятся после обработки материалов.")
            self.weak_label.setText("После репетиции защиты здесь появятся рискованные зоны.")
            return

        self.import_button.setEnabled(not self._processing)
        self.project_title.setText(project.project.title)
        self.project_meta.setText(
            f"{project.project.student_name or 'Студент не указан'} • "
            f"{project.project.specialty or 'Направление не указано'} • "
            f"статус: {PROJECT_STATUS_LABELS.get(project.project.status, project.project.status)}"
        )
        if project.sources:
            source_lines = [
                f"• {SOURCE_KIND_LABELS.get(source.kind.value, source.kind.value)}: {source.title} ({source.file_type}, версия {source.version})"
                for source in project.sources[:6]
            ]
            self.sources_label.setText("Материалы проекта:\n" + "\n".join(source_lines))
        else:
            self.sources_label.setText("Материалы ещё не загружены.")

        claim_lines = []
        for claim in [item for item in project.claims if item.kind.value != "risk_topic"][:8]:
            suffix = " • нужна проверка" if claim.needs_review else ""
            claim_label = CLAIM_LABELS.get(claim.kind.value, claim.kind.value)
            claim_lines.append(f"• {claim_label}: {claim.text[:180]} ({int(round(claim.confidence * 100))}%){suffix}")
        self.claims_label.setText("\n".join(claim_lines) if claim_lines else "Карта защиты пока пуста.")
        self._refresh_outline()

        if project.slides:
            slide_lines = [f"• {slide.slide_index}. {slide.title}: {slide.purpose}" for slide in project.slides[:5]]
            self.slides_label.setText("\n".join(slide_lines))
        else:
            self.slides_label.setText("План слайдов ещё не собран.")

        if project.questions:
            question_lines = [
                f"• {PERSONA_LABELS.get(question.persona.value, question.persona.value)}: {question.question_text}"
                for question in project.questions[:6]
            ]
            self.questions_label.setText("\n".join(question_lines))
        else:
            self.questions_label.setText("Вопросы комиссии ещё не собраны.")

        if project.weak_areas:
            weak_lines = [f"• {item.title}: {item.evidence}" for item in project.weak_areas[:5]]
            self.weak_label.setText("\n".join(weak_lines))
        elif project.latest_score is not None:
            self.weak_label.setText(project.latest_score.summary_text)
        else:
            self.weak_label.setText("После репетиции защиты здесь появятся рискованные зоны.")

    def _refresh_outline(self) -> None:
        if self.snapshot is None or self.snapshot.active_project is None:
            return
        duration = self.duration_combo.currentData()
        segments = self.snapshot.active_project.outlines.get(str(duration), [])
        if not segments:
            self.outline_label.setText("Контур доклада пока не собран.")
            return
        lines = [f"• {title} ({seconds} с): {text}" for title, text, seconds in segments[:8]]
        self.outline_label.setText("\n".join(lines))

    def _emit_activate(self) -> None:
        code = self.activation_input.text().strip()
        if code:
            self.activate_requested.emit(code)

    def _emit_create_project(self) -> None:
        payload = {
            "title": self.project_title_input.text().strip(),
            "degree": "магистр",
            "specialty": self.specialty_input.text().strip(),
            "student_name": self.student_input.text().strip(),
            "supervisor_name": self.supervisor_input.text().strip(),
            "defense_date": self.defense_date_input.text().strip(),
            "discipline_profile": str(self.profile_combo.currentData()),
        }
        self.create_project_requested.emit(payload)

    def _emit_import(self) -> None:
        if self.current_project_id:
            self.import_requested.emit(self.current_project_id)

    def _emit_evaluate(self) -> None:
        if self.current_project_id:
            self.evaluate_requested.emit(
                self.current_project_id,
                str(self.mode_combo.currentData()),
                self.answer_input.toPlainText(),
            )
