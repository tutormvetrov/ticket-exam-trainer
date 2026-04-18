from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
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
from ui.components.common import CardFrame, IconBadge, file_badge_colors, tone_pair
from ui.theme import current_colors


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

GAP_KIND_LABELS = {
    "unsupported_claim": "Тезис без опоры",
    "contradiction": "Противоречие",
    "missing_bridge": "Нет перехода",
    "weak_evidence": "Слабая опора",
    "vague_result": "Размытый результат",
    "novelty_not_proven": "Новизна не доказана",
    "limitations_missing": "Нет ограничений",
    "methods_results_disconnect": "Методы не ведут к результатам",
}

GAP_STATUS_LABELS = {
    "open": "Открыто",
    "accepted": "В работе",
    "resolved": "Исправлено",
    "ignored": "Игнорируется",
}

REPAIR_STATUS_LABELS = {
    "todo": "Нужно сделать",
    "done": "Сделано",
    "dismissed": "Снято",
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
    evaluate_requested = Signal(str, str, str, int, str)
    gap_status_requested = Signal(str, str, str)
    repair_task_status_requested = Signal(str, str, str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.shadow_color = shadow_color
        self.snapshot: DefenseWorkspaceSnapshot | None = None
        self.current_project_id = ""
        self._processing = False
        self._processing_result: DefenseProcessingResult | None = None
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_timer)
        self._timer_profile_sec = 0
        self._timer_remaining_sec = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 28)
        layout.setSpacing(14)

        self.status_card = CardFrame(role="subtle-card", shadow_color=shadow_color, shadow=False)
        status_layout = QHBoxLayout(self.status_card)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(12)
        pm_bg, pm_fg = file_badge_colors("PM")
        status_layout.addWidget(IconBadge("PM", pm_bg, pm_fg, size=42, radius=13, font_size=11), 0, Qt.AlignmentFlag.AlignTop)

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

        self.license_pill = QLabel("Не активировано")
        self.license_pill.setProperty("role", "pill")
        status_layout.addWidget(self.license_pill, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.status_card)

        self.paywall_card = CardFrame(role="card", shadow_color=shadow_color)
        paywall_layout = QVBoxLayout(self.paywall_card)
        paywall_layout.setContentsMargins(20, 20, 20, 20)
        paywall_layout.setSpacing(10)

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
        self.paywall_amount.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {current_colors()['success']};")
        paywall_layout.addWidget(self.paywall_amount)

        self.paywall_status = QLabel("Оплата в приложении не встроена. Введите выданный ключ активации.")
        self.paywall_status.setProperty("role", "body")
        self.paywall_status.setWordWrap(True)
        paywall_layout.addWidget(self.paywall_status)

        self.activation_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.activation_row.setContentsMargins(0, 0, 0, 0)
        self.activation_row.setSpacing(10)
        self.activation_input = QLineEdit()
        self.activation_input.setObjectName("defense-code")
        self.activation_input.setPlaceholderText("Ключ активации модуля")
        self.activation_input.setProperty("role", "form-input")
        self.activation_row.addWidget(self.activation_input, 1)

        self.activate_button = QPushButton("Активировать модуль")
        self.activate_button.setObjectName("defense-activate")
        self.activate_button.setProperty("variant", "primary")
        self.activate_button.clicked.connect(self._emit_activate)
        self.activation_row.addWidget(self.activate_button)
        paywall_layout.addLayout(self.activation_row)
        layout.addWidget(self.paywall_card)

        self.workspace = QWidget()
        workspace_layout = QVBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)

        self.top_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.top_row.setContentsMargins(0, 0, 0, 0)
        self.top_row.setSpacing(16)

        self.projects_card = CardFrame(role="card", shadow_color=shadow_color)
        projects_layout = QVBoxLayout(self.projects_card)
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
        self.top_row.addWidget(self.projects_card, 2)

        self.create_card = CardFrame(role="card", shadow_color=shadow_color)
        create_layout = QVBoxLayout(self.create_card)
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
        self.project_title_input.setProperty("role", "form-input")
        form.addRow("Тема работы", self.project_title_input)

        self.student_input = QLineEdit()
        self.student_input.setProperty("role", "form-input")
        form.addRow("Студент", self.student_input)

        self.specialty_input = QLineEdit()
        self.specialty_input.setProperty("role", "form-input")
        form.addRow("Направление", self.specialty_input)

        self.supervisor_input = QLineEdit()
        self.supervisor_input.setProperty("role", "form-input")
        form.addRow("Научрук", self.supervisor_input)

        self.defense_date_input = QLineEdit()
        self.defense_date_input.setPlaceholderText("2026-06-01")
        self.defense_date_input.setProperty("role", "form-input")
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
        self.top_row.addWidget(self.create_card, 3)
        workspace_layout.addLayout(self.top_row)

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
        self.processing_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {current_colors()['text']};")
        self.processing_status.hide()
        project_layout.addWidget(self.processing_status)

        self.processing_progress = QProgressBar()
        self.processing_progress.setRange(0, 100)
        self.processing_progress.setTextVisible(False)
        self.processing_progress.setFixedHeight(12)
        self._apply_progress_styles(self.processing_progress)
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

        self.outline_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.outline_row.setContentsMargins(0, 0, 0, 0)
        self.outline_row.setSpacing(16)

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
        self.outline_row.addWidget(outline_card, 1)

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
        self.outline_row.addWidget(slides_card, 1)
        workspace_layout.addLayout(self.outline_row)

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

        evidence_card = CardFrame(role="card", shadow_color=shadow_color)
        evidence_layout = QVBoxLayout(evidence_card)
        evidence_layout.setContentsMargins(20, 20, 20, 20)
        evidence_layout.setSpacing(10)
        evidence_title = QLabel("Опора по ключевым блокам")
        evidence_title.setProperty("role", "section-title")
        evidence_layout.addWidget(evidence_title)
        self.evidence_label = QLabel("Статус доказательной опоры появится после обработки материалов.")
        self.evidence_label.setProperty("role", "body")
        self.evidence_label.setWordWrap(True)
        evidence_layout.addWidget(self.evidence_label)
        workspace_layout.addWidget(evidence_card)

        gap_card = CardFrame(role="card", shadow_color=shadow_color)
        gap_layout = QVBoxLayout(gap_card)
        gap_layout.setContentsMargins(20, 20, 20, 20)
        gap_layout.setSpacing(10)
        gap_head = QHBoxLayout()
        gap_head.setContentsMargins(0, 0, 0, 0)
        gap_head.setSpacing(10)
        gap_title = QLabel("Логические дыры")
        gap_title.setProperty("role", "section-title")
        gap_head.addWidget(gap_title)
        gap_head.addStretch(1)
        self.gap_filter_combo = QComboBox()
        self.gap_filter_combo.setObjectName("defense-gap-filter")
        self.gap_filter_combo.addItem("Все типы", "")
        for value, label in GAP_KIND_LABELS.items():
            self.gap_filter_combo.addItem(label, value)
        self.gap_filter_combo.currentIndexChanged.connect(self._refresh_gap_findings)
        gap_head.addWidget(self.gap_filter_combo)
        gap_layout.addLayout(gap_head)
        self.gap_summary_label = QLabel("Здесь появятся найденные логические дыры.")
        self.gap_summary_label.setProperty("role", "body")
        self.gap_summary_label.setWordWrap(True)
        gap_layout.addWidget(self.gap_summary_label)
        self.gap_pick_combo = QComboBox()
        self.gap_pick_combo.setObjectName("defense-gap-pick")
        self.gap_pick_combo.currentIndexChanged.connect(self._refresh_gap_findings)
        gap_layout.addWidget(self.gap_pick_combo)
        self.gap_action_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.gap_action_row.setContentsMargins(0, 0, 0, 0)
        self.gap_action_row.setSpacing(10)
        self.gap_accept_button = QPushButton("Принять в работу")
        self.gap_accept_button.setObjectName("defense-gap-accept")
        self.gap_accept_button.setProperty("variant", "secondary")
        self.gap_accept_button.clicked.connect(lambda: self._emit_gap_status("accepted"))
        self.gap_action_row.addWidget(self.gap_accept_button)
        self.gap_resolve_button = QPushButton("Пометить исправленным")
        self.gap_resolve_button.setObjectName("defense-gap-resolve")
        self.gap_resolve_button.setProperty("variant", "secondary")
        self.gap_resolve_button.clicked.connect(lambda: self._emit_gap_status("resolved"))
        self.gap_action_row.addWidget(self.gap_resolve_button)
        self.gap_ignore_button = QPushButton("Игнорировать")
        self.gap_ignore_button.setObjectName("defense-gap-ignore")
        self.gap_ignore_button.setProperty("variant", "outline")
        self.gap_ignore_button.clicked.connect(lambda: self._emit_gap_status("ignored"))
        self.gap_action_row.addWidget(self.gap_ignore_button)
        self.gap_action_row.addStretch(1)
        gap_layout.addLayout(self.gap_action_row)
        workspace_layout.addWidget(gap_card)

        mock_card = CardFrame(role="card", shadow_color=shadow_color)
        mock_layout = QVBoxLayout(mock_card)
        mock_layout.setContentsMargins(20, 20, 20, 20)
        mock_layout.setSpacing(10)

        self.mock_head = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.mock_head.setContentsMargins(0, 0, 0, 0)
        self.mock_head.setSpacing(10)
        mock_title = QLabel("Имитация защиты")
        mock_title.setProperty("role", "section-title")
        self.mock_head.addWidget(mock_title)
        self.mock_head.addStretch(1)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("defense-mode")
        for value, label in MODE_OPTIONS:
            self.mode_combo.addItem(label, value)
        self.mode_combo.currentIndexChanged.connect(self._sync_timer_controls)
        self.mock_head.addWidget(self.mode_combo)
        mock_layout.addLayout(self.mock_head)

        self.context_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.context_row.setContentsMargins(0, 0, 0, 0)
        self.context_row.setSpacing(10)
        self.persona_combo = QComboBox()
        self.persona_combo.setObjectName("defense-persona")
        for value, label in PERSONA_LABELS.items():
            self.persona_combo.addItem(label, value)
        self.context_row.addWidget(self.persona_combo)
        self.timer_combo = QComboBox()
        self.timer_combo.setObjectName("defense-timer-profile")
        self.timer_combo.addItem("Без таймера", 0)
        self.timer_combo.addItem("5 минут", 300)
        self.timer_combo.addItem("7 минут", 420)
        self.timer_combo.addItem("10 минут", 600)
        self.timer_combo.currentIndexChanged.connect(self._sync_timer_controls)
        self.context_row.addWidget(self.timer_combo)
        mock_layout.addLayout(self.context_row)

        self.timer_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.timer_row.setContentsMargins(0, 0, 0, 0)
        self.timer_row.setSpacing(10)
        self.timer_status_label = QLabel("Таймер не запущен.")
        self.timer_status_label.setProperty("role", "body")
        self.timer_row.addWidget(self.timer_status_label, 1)
        self.timer_start_button = QPushButton("Запустить таймер")
        self.timer_start_button.setObjectName("defense-timer-start")
        self.timer_start_button.setProperty("variant", "secondary")
        self.timer_start_button.clicked.connect(self._toggle_timer)
        self.timer_row.addWidget(self.timer_start_button)
        self.timer_reset_button = QPushButton("Сбросить")
        self.timer_reset_button.setObjectName("defense-timer-reset")
        self.timer_reset_button.setProperty("variant", "outline")
        self.timer_reset_button.clicked.connect(self._reset_timer)
        self.timer_row.addWidget(self.timer_reset_button)
        mock_layout.addLayout(self.timer_row)
        self.timer_progress = QProgressBar()
        self.timer_progress.setObjectName("defense-timer-progress")
        self.timer_progress.setRange(0, 100)
        self.timer_progress.setTextVisible(False)
        self.timer_progress.setFixedHeight(10)
        self._apply_progress_styles(self.timer_progress)
        mock_layout.addWidget(self.timer_progress)

        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Введите текст доклада или ответ на вопрос комиссии.")
        self.answer_input.setMinimumHeight(140)
        self.answer_input.setProperty("role", "editor")
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

        repair_card = CardFrame(role="card", shadow_color=shadow_color)
        repair_layout = QVBoxLayout(repair_card)
        repair_layout.setContentsMargins(20, 20, 20, 20)
        repair_layout.setSpacing(10)
        repair_title = QLabel("Что исправить перед защитой")
        repair_title.setProperty("role", "section-title")
        repair_layout.addWidget(repair_title)
        self.repair_label = QLabel("После анализа и репетиции здесь появится очередь доработок.")
        self.repair_label.setProperty("role", "body")
        self.repair_label.setWordWrap(True)
        repair_layout.addWidget(self.repair_label)
        self.repair_pick_combo = QComboBox()
        self.repair_pick_combo.setObjectName("defense-repair-pick")
        self.repair_pick_combo.currentIndexChanged.connect(self._refresh_repair_tasks)
        repair_layout.addWidget(self.repair_pick_combo)
        self.repair_actions = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.repair_actions.setContentsMargins(0, 0, 0, 0)
        self.repair_actions.setSpacing(10)
        self.repair_done_button = QPushButton("Сделано")
        self.repair_done_button.setObjectName("defense-repair-done")
        self.repair_done_button.setProperty("variant", "secondary")
        self.repair_done_button.clicked.connect(lambda: self._emit_repair_status("done"))
        self.repair_actions.addWidget(self.repair_done_button)
        self.repair_dismiss_button = QPushButton("Снять")
        self.repair_dismiss_button.setObjectName("defense-repair-dismiss")
        self.repair_dismiss_button.setProperty("variant", "outline")
        self.repair_dismiss_button.clicked.connect(lambda: self._emit_repair_status("dismissed"))
        self.repair_actions.addWidget(self.repair_dismiss_button)
        self.repair_actions.addStretch(1)
        repair_layout.addLayout(self.repair_actions)
        workspace_layout.addWidget(repair_card)

        layout.addWidget(self.workspace)
        self.workspace.hide()
        self._apply_responsive_layout()

    def _apply_progress_styles(self, progress: QProgressBar) -> None:
        colors = current_colors()
        progress.setStyleSheet(
            f"""
            QProgressBar {{
                background: {colors["card_muted"]};
                border: 1px solid {colors["border"]};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: {colors["primary"]};
                border-radius: 5px;
            }}
            """
        )

    def set_snapshot(self, snapshot: DefenseWorkspaceSnapshot) -> None:
        self.snapshot = snapshot
        self.current_project_id = snapshot.active_project.project.project_id if snapshot.active_project else ""
        self.paywall_amount.setText(f"Доступ: {snapshot.paywall_amount_label}")
        self.install_label.setText(f"Идентификатор установки: {snapshot.install_id}")
        self.recommendation_label.setText(snapshot.recommendation.label)
        self.recommendation_body.setText(snapshot.recommendation.rationale)

        activated = snapshot.license_state.activated
        self.license_pill.setText("Модуль активирован" if activated else "Модуль закрыт")
        if activated:
            self.paywall_status.setText("Лицензия активирована локально. Материалы проекта остаются на этом компьютере.")
        elif snapshot.license_state.status == "wrong_install":
            self.paywall_status.setText("Ключ выдан для другой установки. Скопируйте текущий install ID и запросите новый код.")
        elif snapshot.license_state.status == "invalid":
            self.paywall_status.setText("Ключ не подошёл. Проверьте код или запросите код именно для этого install ID.")
        else:
            self.paywall_status.setText("Оплата в приложении не встроена. Введите выданный ключ активации для этого install ID.")
        self.paywall_card.setVisible(not activated)
        self.workspace.setVisible(activated)
        self._render_projects(snapshot)
        self._render_active_project(snapshot)
        self._sync_timer_controls()

    def is_processing(self) -> bool:
        return self._processing

    def set_activation_pending(self, pending: bool) -> None:
        self.activate_button.setEnabled(not pending)
        self.activate_button.setText("Проверяем ключ..." if pending else "Активировать модуль")
        if pending:
            self.paywall_status.setText("Проверяем код активации для этой установки...")

    def set_processing_pending(self, project_title: str) -> None:
        self._processing = True
        _, fg = tone_pair("warning")
        self.processing_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {fg};")
        self.processing_status.setText(f"Идёт обработка материалов: {project_title}")
        self.processing_status.show()
        self.processing_progress.setValue(0)
        self.processing_progress.show()
        self.processing_meta.setText("Импорт и разбор идут в фоне.")
        self.processing_meta.show()
        self.processing_result.hide()
        self.import_button.setEnabled(False)

    def set_processing_progress(self, percent: int, stage: str, detail: str = "") -> None:
        _, fg = tone_pair("primary")
        self.processing_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {fg};")
        self.processing_status.setText(stage)
        self.processing_progress.setValue(max(0, min(100, percent)))
        self.processing_meta.setText(detail or "Идёт фоновая локальная обработка.")

    def show_processing_result(self, result: DefenseProcessingResult) -> None:
        self._processing = False
        self._set_import_busy(False)
        self._processing_result = result
        self.import_button.setEnabled(True)
        _, fg = tone_pair("success" if result.ok else "danger")
        self.processing_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {fg};")
        self.processing_status.setText("Обработка материалов завершена" if result.ok else "Обработка материалов завершилась с ошибкой")
        self.processing_status.show()
        self.processing_progress.setValue(100 if result.ok else self.processing_progress.value())
        self.processing_progress.show()
        details = [result.message] if result.message else []
        if result.ok:
            details.append(f"Логические дыры: {result.gap_findings_count}")
            details.append(f"Задачи на исправление: {result.repair_tasks_count}")
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
        if result.timer_verdict:
            lines.append("")
            lines.append(result.timer_verdict)
        if result.weak_points:
            lines.append("")
            lines.append("Слабые места:")
            lines.extend(f"• {item}" for item in result.weak_points)
        if result.suggested_repair_tasks:
            lines.append("")
            lines.append("Что добить дальше:")
            lines.extend(f"• {item}" for item in result.suggested_repair_tasks)
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
            self.evidence_label.setText("Статус доказательной опоры появится после обработки материалов.")
            self.gap_summary_label.setText("Здесь появятся найденные логические дыры.")
            self.gap_pick_combo.clear()
            self.weak_label.setText("После репетиции защиты здесь появятся рискованные зоны.")
            self.repair_label.setText("После анализа и репетиции здесь появится очередь доработок.")
            self.repair_pick_combo.clear()
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
            evidence_state = self._evidence_state_for_claim(claim)
            claim_lines.append(
                f"• {claim_label}: {claim.text[:180]} ({int(round(claim.confidence * 100))}% • {evidence_state}){suffix}"
            )
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

        self.evidence_label.setText(self._build_evidence_summary(project))
        self._refresh_gap_findings()

        if project.weak_areas:
            weak_lines = [f"• {item.title}: {item.evidence}" for item in project.weak_areas[:5]]
            self.weak_label.setText("\n".join(weak_lines))
        elif project.latest_score is not None:
            self.weak_label.setText(project.latest_score.summary_text)
        else:
            self.weak_label.setText("После репетиции защиты здесь появятся рискованные зоны.")
        self._refresh_repair_tasks()

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

    def _set_create_busy(self, busy: bool) -> None:
        self.create_button.setEnabled(not busy)
        self.create_button.setText("Создание..." if busy else "Создать проект защиты")

    def _set_import_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.import_button.setText("Импорт..." if busy else "Импортировать материалы")

    def _emit_create_project(self) -> None:
        self._set_create_busy(True)
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
            self._set_import_busy(True)
            self.import_requested.emit(self.current_project_id)

    def _emit_evaluate(self) -> None:
        if self.current_project_id:
            self.evaluate_requested.emit(
                self.current_project_id,
                str(self.mode_combo.currentData()),
                str(self.persona_combo.currentData()),
                int(self.timer_combo.currentData() or 0),
                self.answer_input.toPlainText(),
            )

    def _refresh_gap_findings(self) -> None:
        project = self.snapshot.active_project if self.snapshot else None
        if project is None:
            return
        filter_value = str(self.gap_filter_combo.currentData() or "")
        findings = [item for item in project.gap_findings if not filter_value or item.gap_kind.value == filter_value]
        current_id = str(self.gap_pick_combo.currentData() or "")
        self.gap_pick_combo.blockSignals(True)
        self.gap_pick_combo.clear()
        for finding in findings:
            self.gap_pick_combo.addItem(
                f"{int(round(finding.severity * 100))}% • {GAP_KIND_LABELS.get(finding.gap_kind.value, finding.gap_kind.value)} • {finding.title}",
                finding.finding_id,
            )
        if current_id:
            index = self.gap_pick_combo.findData(current_id)
            if index >= 0:
                self.gap_pick_combo.setCurrentIndex(index)
        self.gap_pick_combo.blockSignals(False)
        if not findings:
            self.gap_summary_label.setText("Явных логических дыр не найдено. После следующего импорта или репетиции список обновится.")
            self._set_gap_buttons_enabled(False)
            return
        finding_id = str(self.gap_pick_combo.currentData() or findings[0].finding_id)
        finding = next((item for item in findings if item.finding_id == finding_id), findings[0])
        lines = [
            f"{GAP_KIND_LABELS.get(finding.gap_kind.value, finding.gap_kind.value)} • статус: {GAP_STATUS_LABELS.get(finding.status.value, finding.status.value)}",
            finding.explanation,
        ]
        if finding.related_claim_kinds:
            lines.append("Связанные блоки: " + ", ".join(CLAIM_LABELS.get(kind, kind.value) for kind in finding.related_claim_kinds))
        if finding.evidence_links:
            lines.append("Опора: " + "; ".join(finding.evidence_links[:2]))
        if finding.suggested_fix:
            lines.append("Что сделать: " + finding.suggested_fix)
        self.gap_summary_label.setText("\n".join(lines))
        self._set_gap_buttons_enabled(True)

    def _refresh_repair_tasks(self) -> None:
        project = self.snapshot.active_project if self.snapshot else None
        if project is None:
            return
        current_id = str(self.repair_pick_combo.currentData() or "")
        self.repair_pick_combo.blockSignals(True)
        self.repair_pick_combo.clear()
        for task in project.repair_tasks:
            self.repair_pick_combo.addItem(
                f"{REPAIR_STATUS_LABELS.get(task.status.value, task.status.value)} • {task.title}",
                task.task_id,
            )
        if current_id:
            index = self.repair_pick_combo.findData(current_id)
            if index >= 0:
                self.repair_pick_combo.setCurrentIndex(index)
        self.repair_pick_combo.blockSignals(False)
        if not project.repair_tasks:
            self.repair_label.setText("После анализа и репетиции здесь появится очередь доработок.")
            self._set_repair_buttons_enabled(False)
            return
        task_id = str(self.repair_pick_combo.currentData() or project.repair_tasks[0].task_id)
        task = next((item for item in project.repair_tasks if item.task_id == task_id), project.repair_tasks[0])
        lines = [
            f"{REPAIR_STATUS_LABELS.get(task.status.value, task.status.value)} • {task.title}",
            task.reason,
        ]
        if task.related_gap_ids:
            lines.append("Связанные дыры: " + ", ".join(task.related_gap_ids[:3]))
        if task.suggested_action:
            lines.append("Действие: " + task.suggested_action)
        self.repair_label.setText("\n".join(lines))
        self._set_repair_buttons_enabled(True)

    def _emit_gap_status(self, status: str) -> None:
        finding_id = str(self.gap_pick_combo.currentData() or "")
        if self.current_project_id and finding_id:
            self._set_gap_buttons_enabled(False)
            self.gap_status_requested.emit(self.current_project_id, finding_id, status)

    def _emit_repair_status(self, status: str) -> None:
        task_id = str(self.repair_pick_combo.currentData() or "")
        if self.current_project_id and task_id:
            self._set_repair_buttons_enabled(False)
            self.repair_task_status_requested.emit(self.current_project_id, task_id, status)

    def _sync_timer_controls(self) -> None:
        mode = str(self.mode_combo.currentData() or "")
        if mode == "speech_5":
            self.timer_combo.setCurrentIndex(self.timer_combo.findData(300))
            self.timer_combo.setEnabled(False)
        elif mode == "speech_7":
            self.timer_combo.setCurrentIndex(self.timer_combo.findData(420))
            self.timer_combo.setEnabled(False)
        elif mode == "speech_10":
            self.timer_combo.setCurrentIndex(self.timer_combo.findData(600))
            self.timer_combo.setEnabled(False)
        else:
            self.timer_combo.setEnabled(True)
        self._timer_profile_sec = int(self.timer_combo.currentData() or 0)
        if self._timer_remaining_sec <= 0 or self._timer_remaining_sec > max(self._timer_profile_sec, 1):
            self._timer_remaining_sec = self._timer_profile_sec
        self._refresh_timer_widgets()

    def _toggle_timer(self) -> None:
        if self._timer_profile_sec <= 0:
            self.timer_status_label.setText("Для этого сценария таймер отключён.")
            return
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self.timer_start_button.setText("Продолжить таймер")
            return
        if self._timer_remaining_sec <= 0:
            self._timer_remaining_sec = self._timer_profile_sec
        self._countdown_timer.start()
        self.timer_start_button.setText("Пауза")
        self._refresh_timer_widgets()

    def _reset_timer(self) -> None:
        self._countdown_timer.stop()
        self._timer_remaining_sec = self._timer_profile_sec
        self.timer_start_button.setText("Запустить таймер")
        self._refresh_timer_widgets()

    def _tick_timer(self) -> None:
        if self._timer_remaining_sec > 0:
            self._timer_remaining_sec -= 1
        else:
            self._countdown_timer.stop()
        self._refresh_timer_widgets()

    def _refresh_timer_widgets(self) -> None:
        if self._timer_profile_sec <= 0:
            self.timer_status_label.setText("Таймер отключён.")
            self.timer_progress.setValue(0)
            self.timer_start_button.setEnabled(False)
            self.timer_reset_button.setEnabled(False)
            return
        self.timer_start_button.setEnabled(True)
        self.timer_reset_button.setEnabled(True)
        remaining = max(0, self._timer_remaining_sec)
        percent = int(round((remaining / max(1, self._timer_profile_sec)) * 100))
        self.timer_progress.setValue(percent)
        self.timer_status_label.setText(f"Осталось: {remaining // 60:02d}:{remaining % 60:02d}")
        if not self._countdown_timer.isActive():
            self.timer_start_button.setText("Запустить таймер" if remaining == self._timer_profile_sec else "Продолжить таймер")

    def _build_evidence_summary(self, project) -> str:
        lines = []
        for kind in ("novelty", "results", "limitations", "methods"):
            claim = next((item for item in project.claims if item.kind.value == kind), None)
            label = CLAIM_LABELS.get(kind, kind)
            lines.append(f"• {label}: {self._evidence_state_for_claim(claim)}")
        return "\n".join(lines)

    @staticmethod
    def _evidence_state_for_claim(claim) -> str:
        if claim is None:
            return "нет опоры"
        if len(claim.source_anchors) >= 2 and not claim.needs_review:
            return "есть опора"
        if claim.source_anchors:
            return "слабая опора"
        return "нет опоры"

    def _set_gap_buttons_enabled(self, enabled: bool) -> None:
        self.gap_accept_button.setEnabled(enabled)
        self.gap_resolve_button.setEnabled(enabled)
        self.gap_ignore_button.setEnabled(enabled)

    def _set_repair_buttons_enabled(self, enabled: bool) -> None:
        self.repair_done_button.setEnabled(enabled)
        self.repair_dismiss_button.setEnabled(enabled)

    def refresh_theme(self) -> None:
        self.paywall_amount.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {current_colors()['success']};")
        self.processing_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {current_colors()['text']};")
        self._apply_progress_styles(self.processing_progress)
        self._apply_progress_styles(self.timer_progress)
        if self.snapshot is not None:
            self.set_snapshot(self.snapshot)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        compact = self.width() < 1080
        narrow = self.width() < 1240
        self.activation_row.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.top_row.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        self.outline_row.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        self.mock_head.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.context_row.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.timer_row.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.gap_action_row.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.repair_actions.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.activate_button.setMaximumWidth(16777215 if compact else 280)
        self.projects_card.setMinimumWidth(0 if narrow else 320)
        self.create_card.setMinimumWidth(0 if narrow else 360)
