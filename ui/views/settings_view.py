from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from application.admin_access import AdminAccessState
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.update_service import UpdateInfo
from app import platform as platform_helpers
from app.build_info import get_runtime_build_info
from app.meta import APP_VERSION
from app.paths import get_app_root, get_check_script_path, get_docs_path, get_readme_path, get_setup_script_path, get_workspace_root
from infrastructure.ollama.service import OllamaDiagnostics, OllamaService
from ui.background import FunctionThread
from ui.components.common import CardFrame, IconBadge
from ui.components.settings_widgets import DiagnosticTile, NumberStepper, SettingsNavPanel, SettingsToggleCard
from ui.training_catalog import DEFAULT_TRAINING_MODES
from ui.theme import FONT_PRESETS, app_font, current_colors, resolve_font_family


SETTINGS_SECTIONS = [
    ("general", "Общие", "Интерфейс и запуск", "UI", "#EEF3FF"),
    ("documents", "Документы", "Импорт и обработка", "DOC", "#F4F7FB"),
    ("training", "Тренировка", "Очередь и режимы", "TR", "#F4F7FB"),
    ("ollama", "Ollama", "Локальная LLM", "AI", "#EEF5FF"),
    ("data", "Данные", "База и резервные копии", "DB", "#F4F7FB"),
    ("advanced", "Продвинутые", "Диагностика и сервис", "ADV", "#F4F7FB"),
]


class SettingsView(QWidget):
    diagnostics_changed = Signal(object)
    settings_saved = Signal(object)
    admin_setup_requested = Signal()
    admin_login_requested = Signal(str)
    admin_logout_requested = Signal()
    admin_editor_requested = Signal()
    admin_debug_toggled = Signal(bool)
    update_check_requested = Signal()
    open_release_requested = Signal()

    def __init__(
        self,
        shadow_color,
        initial_settings: OllamaSettings | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.self_scrolling = True
        self.shadow_color = shadow_color
        self.bundle_root = get_app_root()
        self.workspace_root = workspace_root or get_workspace_root()
        self.build_info = get_runtime_build_info(self.bundle_root)
        self.backups_dir = self.workspace_root / "backups"
        self.database_path = self.workspace_root / "exam_trainer.db"
        self.settings_path = self.workspace_root / "app_data" / "settings.json"
        self.settings = initial_settings or OllamaSettings(
            base_url=DEFAULT_OLLAMA_SETTINGS.base_url,
            model=DEFAULT_OLLAMA_SETTINGS.model,
            models_path=DEFAULT_OLLAMA_SETTINGS.models_path,
            timeout_seconds=DEFAULT_OLLAMA_SETTINGS.timeout_seconds,
            rewrite_questions=DEFAULT_OLLAMA_SETTINGS.rewrite_questions,
            examiner_followups=DEFAULT_OLLAMA_SETTINGS.examiner_followups,
            rule_based_fallback=DEFAULT_OLLAMA_SETTINGS.rule_based_fallback,
            theme_name=DEFAULT_OLLAMA_SETTINGS.theme_name,
            startup_view=DEFAULT_OLLAMA_SETTINGS.startup_view,
            auto_check_ollama_on_start=DEFAULT_OLLAMA_SETTINGS.auto_check_ollama_on_start,
            show_dlc_teaser=DEFAULT_OLLAMA_SETTINGS.show_dlc_teaser,
            default_import_dir=DEFAULT_OLLAMA_SETTINGS.default_import_dir,
            preferred_import_format=DEFAULT_OLLAMA_SETTINGS.preferred_import_format,
            import_llm_assist=DEFAULT_OLLAMA_SETTINGS.import_llm_assist,
            default_training_mode=DEFAULT_OLLAMA_SETTINGS.default_training_mode,
            review_mode=DEFAULT_OLLAMA_SETTINGS.review_mode,
            training_queue_size=DEFAULT_OLLAMA_SETTINGS.training_queue_size,
            font_preset=DEFAULT_OLLAMA_SETTINGS.font_preset,
            font_size=DEFAULT_OLLAMA_SETTINGS.font_size,
            auto_check_updates_on_start=DEFAULT_OLLAMA_SETTINGS.auto_check_updates_on_start,
        )
        self._diagnostics_thread: FunctionThread | None = None
        self._refresh_models_after_check = False
        self._last_diagnostics: OllamaDiagnostics | None = None
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(18)

        self.header_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header_row.setContentsMargins(0, 0, 0, 0)
        self.header_row.setSpacing(16)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(4)
        page_title = QLabel("Настройки")
        page_title.setProperty("role", "hero")
        page_subtitle = QLabel("Настройте запуск, импорт, тренировку и локальный AI без ложных статусов.")
        page_subtitle.setProperty("role", "page-subtitle")
        page_subtitle.setWordWrap(True)
        titles.addWidget(page_title)
        titles.addWidget(page_subtitle)
        self.header_row.addLayout(titles, 1)
        self.header_row.addStretch(1)

        self.reset_button = QPushButton("Сбросить")
        self.reset_button.setObjectName("settings-reset")
        self.reset_button.setProperty("variant", "outline")
        self.reset_button.clicked.connect(self.reset_form)
        self.header_row.addWidget(self.reset_button)

        self.save_button = QPushButton("Сохранить изменения")
        self.save_button.setObjectName("settings-save")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save_settings)
        self.header_row.addWidget(self.save_button)
        layout.addLayout(self.header_row)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {current_colors()['border']};")
        layout.addWidget(divider)

        self.main_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.main_row.setContentsMargins(0, 0, 0, 0)
        self.main_row.setSpacing(16)

        self.nav_panel = SettingsNavPanel(SETTINGS_SECTIONS, shadow_color)
        self.nav_panel.setMinimumWidth(254)
        self.nav_panel.setMaximumWidth(304)
        self.nav_panel.section_changed.connect(self.switch_section)
        self.main_row.addWidget(self.nav_panel, 3)

        self.settings_stack = QStackedWidget()
        self.main_row.addWidget(self.settings_stack, 7)
        layout.addLayout(self.main_row, 1)

        self.settings_stack.addWidget(self._build_general_page())
        self.settings_stack.addWidget(self._build_documents_page())
        self.settings_stack.addWidget(self._build_training_page())
        self.settings_stack.addWidget(self._build_ollama_page())
        self.settings_stack.addWidget(self._build_data_page())
        self.settings_stack.addWidget(self._build_advanced_page())

        self.switch_section("ollama")
        self.reset_form()
        self._connect_dirty_tracking()
        self._apply_responsive_layout()

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)

        title = QLabel("Общие параметры")
        title.setProperty("role", "section-title")
        card_layout.addWidget(title)

        body = QLabel(
            "Эти параметры управляют первым запуском, темой интерфейса, стартовым экраном и типографикой. "
            "Предпросмотр ниже обновляется сразу, а на всё приложение изменения применяются после сохранения."
        )
        body.setProperty("role", "body")
        body.setWordWrap(True)
        card_layout.addWidget(body)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        theme_block = self._labeled_block("Тема приложения")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Тёмная", "dark")
        self.theme_combo.setMinimumHeight(46)
        theme_block.layout().addWidget(self.theme_combo)
        row.addWidget(theme_block, 1)

        startup_block = self._labeled_block("Экран при запуске")
        self.startup_view_combo = QComboBox()
        startup_views = [
            ("Библиотека", "library"),
            ("Предметы", "subjects"),
            ("Разделы", "sections"),
            ("Билеты", "tickets"),
            ("Импорт документов", "import"),
            ("Тренировка", "training"),
            ("Статистика", "statistics"),
            ("Настройки", "settings"),
        ]
        for label, value in startup_views:
            self.startup_view_combo.addItem(label, value)
        self.startup_view_combo.setMinimumHeight(46)
        startup_block.layout().addWidget(self.startup_view_combo)
        row.addWidget(startup_block, 1)
        card_layout.addLayout(row)

        typography_row = QHBoxLayout()
        typography_row.setContentsMargins(0, 0, 0, 0)
        typography_row.setSpacing(16)

        font_block = self._labeled_block("Шрифт интерфейса")
        self.font_preset_combo = QComboBox()
        for preset_key in ("segoe", "bahnschrift", "trebuchet", "verdana", "arial"):
            self.font_preset_combo.addItem(FONT_PRESETS[preset_key]["label"], preset_key)
        self.font_preset_combo.setMinimumHeight(46)
        font_block.layout().addWidget(self.font_preset_combo)
        typography_row.addWidget(font_block, 1)

        font_size_block = self._labeled_block("Размер текста")
        self.font_size_stepper = NumberStepper(self.settings.font_size, minimum=9, maximum=18, step=1, label_width=56)
        self.font_size_stepper.setMinimumHeight(46)
        font_size_block.layout().addWidget(self.font_size_stepper)
        typography_row.addWidget(font_size_block, 1)
        card_layout.addLayout(typography_row)

        self.font_preset_combo.currentIndexChanged.connect(self._refresh_typography_preview)
        self.font_size_stepper.value_changed.connect(lambda _value: self._refresh_typography_preview())

        preview_card = CardFrame(role="subtle-card", shadow_color=self.shadow_color, shadow=False)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 16, 18, 16)
        preview_layout.setSpacing(10)

        preview_title = QLabel("Предпросмотр типографики")
        preview_title.setProperty("role", "card-title")
        preview_layout.addWidget(preview_title)

        self.typography_preview_meta = QLabel("")
        self.typography_preview_meta.setProperty("role", "muted")
        self.typography_preview_meta.setWordWrap(True)
        preview_layout.addWidget(self.typography_preview_meta)

        self.typography_preview_title = QLabel("Тезис: библиотека, тренировка, статистика и защита")
        self.typography_preview_title.setWordWrap(True)
        preview_layout.addWidget(self.typography_preview_title)

        self.typography_preview_body = QLabel(
            "Текст интерфейса должен легко читаться на длинной сессии: в очереди, в разборе результата и в настройках."
        )
        self.typography_preview_body.setWordWrap(True)
        preview_layout.addWidget(self.typography_preview_body)

        preview_chip_row = QHBoxLayout()
        preview_chip_row.setContentsMargins(0, 0, 0, 0)
        preview_chip_row.setSpacing(10)

        self.typography_preview_chip = QLabel("Режим: активное вспоминание")
        self.typography_preview_chip.setProperty("role", "pill")
        preview_chip_row.addWidget(self.typography_preview_chip, 0, Qt.AlignmentFlag.AlignLeft)

        self.typography_preview_button = QPushButton("Пример кнопки")
        self.typography_preview_button.setProperty("variant", "secondary")
        self.typography_preview_button.setEnabled(False)
        preview_chip_row.addWidget(self.typography_preview_button, 0, Qt.AlignmentFlag.AlignLeft)
        preview_chip_row.addStretch(1)
        preview_layout.addLayout(preview_chip_row)

        card_layout.addWidget(preview_card)
        self._refresh_typography_preview()

        self.auto_check_card = SettingsToggleCard(
            "Автопроверка Ollama при старте",
            "Если включено, приложение само проверяет адрес сервера и модель при запуске.",
            "AI",
            "#2E78E6",
            self.settings.auto_check_ollama_on_start,
            self.shadow_color,
        )
        card_layout.addWidget(self.auto_check_card)

        self.update_check_card = SettingsToggleCard(
            "Автопроверка обновлений",
            "При запуске приложение проверяет свежий релиз на GitHub и честно предлагает обновиться.",
            "UP",
            "#0F766E",
            self.settings.auto_check_updates_on_start,
            self.shadow_color,
        )
        card_layout.addWidget(self.update_check_card)

        self.dlc_card = SettingsToggleCard(
            "Показывать карточку платного модуля",
            "Оставлять на главном экране карточку модуля подготовки к защите магистерской.",
            "PM",
            "#7C3AED",
            self.settings.show_dlc_teaser,
            self.shadow_color,
        )
        card_layout.addWidget(self.dlc_card)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_documents_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)

        title = QLabel("Параметры импорта")
        title.setProperty("role", "section-title")
        card_layout.addWidget(title)

        body = QLabel(
            "Главный боевой сценарий релиза это один большой DOCX. "
            "PDF тоже поддерживается, но стартовый фильтр и папку удобнее закрепить здесь."
        )
        body.setProperty("role", "body")
        body.setWordWrap(True)
        card_layout.addWidget(body)

        folder_block = self._labeled_block("Папка импорта по умолчанию")
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(10)
        self.default_import_dir_input = QLineEdit(str(self.settings.default_import_dir))
        self.default_import_dir_input.setProperty("role", "form-input")
        self.default_import_dir_input.setMinimumHeight(46)
        folder_row.addWidget(self.default_import_dir_input, 1)
        folder_button = QPushButton("Выбрать")
        folder_button.setObjectName("settings-select-import-dir")
        folder_button.setProperty("variant", "secondary")
        folder_button.setMinimumHeight(46)
        folder_button.clicked.connect(self.select_import_dir)
        folder_row.addWidget(folder_button)
        folder_block.layout().addLayout(folder_row)
        card_layout.addWidget(folder_block)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        format_block = self._labeled_block("Предпочитаемый формат")
        self.import_format_combo = QComboBox()
        self.import_format_combo.addItem("DOCX", "docx")
        self.import_format_combo.addItem("PDF", "pdf")
        self.import_format_combo.setMinimumHeight(46)
        format_block.layout().addWidget(self.import_format_combo)
        row.addWidget(format_block, 1)

        helper_block = self._labeled_block("Поведение импорта")
        helper_label = QLabel("Формат влияет на порядок в диалоге выбора файла.")
        helper_label.setProperty("role", "body")
        helper_label.setWordWrap(True)
        helper_block.layout().addWidget(helper_label)
        row.addWidget(helper_block, 1)
        card_layout.addLayout(row)

        self.import_llm_card = SettingsToggleCard(
            "LLM-помощь при структурировании",
            "Разрешить локальной модели уточнять структуру билетов, если исходный документ размечен неидеально.",
            "AI",
            "#18B06A",
            self.settings.import_llm_assist,
            self.shadow_color,
        )
        card_layout.addWidget(self.import_llm_card)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_training_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)

        title = QLabel("Параметры тренировки")
        title.setProperty("role", "section-title")
        card_layout.addWidget(title)

        body = QLabel(
            "Здесь задаются стартовый режим, профиль повторения и длина адаптивной очереди. "
            "Изменения влияют на библиотеку, тренировку и статистику."
        )
        body.setProperty("role", "body")
        body.setWordWrap(True)
        card_layout.addWidget(body)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        mode_block = self._labeled_block("Режим по умолчанию")
        self.training_mode_combo = QComboBox()
        for item in DEFAULT_TRAINING_MODES:
            self.training_mode_combo.addItem(item.title, item.key)
        self.training_mode_combo.setMinimumHeight(46)
        mode_block.layout().addWidget(self.training_mode_combo)
        grid.addWidget(mode_block, 0, 0)

        review_block = self._labeled_block("Профиль повторения")
        self.review_mode_combo = QComboBox()
        self.review_mode_combo.addItem("Стандартное адаптивное", "standard_adaptive")
        self.review_mode_combo.addItem("Экспресс перед экзаменом", "exam_crunch")
        self.review_mode_combo.setMinimumHeight(46)
        review_block.layout().addWidget(self.review_mode_combo)
        grid.addWidget(review_block, 0, 1)

        queue_block = self._labeled_block("Размер очереди")
        self.queue_size_combo = QComboBox()
        for size in (6, 8, 10, 12, 16):
            self.queue_size_combo.addItem(str(size), size)
        self.queue_size_combo.setMinimumHeight(46)
        queue_block.layout().addWidget(self.queue_size_combo)
        grid.addWidget(queue_block, 1, 0)

        note_block = self._labeled_block("Что это меняет")
        note_label = QLabel(
            "Чем больше очередь, тем больше карточек видно сразу. "
            "Экстренный режим сильнее поджимает слабые билеты и устные навыки."
        )
        note_label.setProperty("role", "body")
        note_label.setWordWrap(True)
        note_block.layout().addWidget(note_label)
        grid.addWidget(note_block, 1, 1)
        card_layout.addLayout(grid)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_ollama_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 18)
        card_layout.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.addWidget(IconBadge("AI", current_colors()["primary_soft"], current_colors()["primary"], size=50, radius=15, font_size=16))

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(3)
        title = QLabel("Ollama")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {current_colors()['text']};")
        subtitle = QLabel("Реальный центр управления локальной LLM через Ollama. По умолчанию используется qwen3:8b.")
        subtitle.setProperty("role", "body")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.status_pill = QLabel("Проверка...")
        self.status_pill.setProperty("skipTextAdmin", True)
        self.status_pill.setStyleSheet(
            f"background: {current_colors()['card_muted']}; color: {current_colors()['text_secondary']}; border-radius: 999px; padding: 10px 16px; "
            "font-size: 14px; font-weight: 700;"
        )
        header.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(header)

        section_label = QLabel("Основные параметры")
        section_label.setProperty("role", "section-title")
        card_layout.addWidget(section_label)

        form_rows = QVBoxLayout()
        form_rows.setContentsMargins(0, 0, 0, 0)
        form_rows.setSpacing(16)

        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(16)

        url_block = self._labeled_block("Адрес API")
        self.url_input = QLineEdit(self.settings.base_url)
        self.url_input.setPlaceholderText("http://localhost:11434")
        self.url_input.setProperty("role", "form-input")
        self.url_input.setMinimumHeight(46)
        url_block.layout().addWidget(self.url_input)
        first_row.addWidget(url_block, 3)

        model_block = self._labeled_block("Модель")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItem(self.settings.model)
        self.model_combo.setCurrentText(self.settings.model)
        self.model_combo.setMinimumHeight(46)
        model_block.layout().addWidget(self.model_combo)
        first_row.addWidget(model_block, 2)
        form_rows.addLayout(first_row)

        second_row = QHBoxLayout()
        second_row.setContentsMargins(0, 0, 0, 0)
        second_row.setSpacing(16)

        folder_block = self._labeled_block("Папка с моделями")
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(10)
        self.models_path_input = QLineEdit(str(self.settings.models_path))
        self.models_path_input.setPlaceholderText(str(platform_helpers.default_models_path()))
        self.models_path_input.setProperty("role", "form-input")
        self.models_path_input.setMinimumHeight(46)
        folder_row.addWidget(self.models_path_input, 1)
        models_button = QPushButton("Открыть")
        models_button.setObjectName("settings-open-models-folder-inline")
        models_button.setProperty("variant", "secondary")
        models_button.setMinimumHeight(46)
        models_button.clicked.connect(self.open_models_folder)
        folder_row.addWidget(models_button)
        folder_block.layout().addLayout(folder_row)
        second_row.addWidget(folder_block, 3)

        timeout_block = self._labeled_block("Таймаут запроса, сек.")
        self.timeout_stepper = NumberStepper(self.settings.timeout_seconds)
        self.timeout_stepper.setMinimumHeight(46)
        timeout_block.layout().addWidget(self.timeout_stepper)
        second_row.addWidget(timeout_block, 2)
        form_rows.addLayout(second_row)
        card_layout.addLayout(form_rows)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {current_colors()['border']};")
        card_layout.addWidget(line)

        usage_title = QLabel("Использование LLM в приложении")
        usage_title.setProperty("role", "section-title")
        card_layout.addWidget(usage_title)

        self.rewrite_card = SettingsToggleCard(
            "Улучшать формулировки вопросов",
            "Локальная модель помогает делать учебные вопросы яснее и плотнее.",
            "Q",
            "#7C3AED",
            self.settings.rewrite_questions,
            self.shadow_color,
        )
        card_layout.addWidget(self.rewrite_card)

        self.followups_card = SettingsToggleCard(
            "Генерировать уточняющие вопросы экзаменатора",
            "После ответа система может задавать уточняющие вопросы по слабым местам.",
            "F",
            "#F97316",
            self.settings.examiner_followups,
            self.shadow_color,
        )
        card_layout.addWidget(self.followups_card)

        self.fallback_card = SettingsToggleCard(
            "Автоматический переход на локальные правила",
            "Если Ollama недоступен, приложение честно переключается на локальные правила без ложного сообщения об успехе.",
            "RB",
            "#64748B",
            self.settings.rule_based_fallback,
            self.shadow_color,
        )
        card_layout.addWidget(self.fallback_card)
        layout.addWidget(card)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)
        lower_row.addWidget(self._build_diagnostics_card(), 1)
        lower_row.addWidget(self._build_actions_card())
        layout.addLayout(lower_row)
        layout.addStretch(1)
        return page

    def _build_data_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        storage_card = CardFrame(role="card", shadow_color=self.shadow_color)
        storage_layout = QVBoxLayout(storage_card)
        storage_layout.setContentsMargins(24, 22, 24, 22)
        storage_layout.setSpacing(14)

        title = QLabel("Хранилище приложения")
        title.setProperty("role", "section-title")
        storage_layout.addWidget(title)

        body = QLabel("Здесь видны реальные пути к папке данных, базе, настройкам и резервным копиям.")
        body.setProperty("role", "body")
        body.setWordWrap(True)
        storage_layout.addWidget(body)

        self.workspace_path_label = QLabel()
        self.workspace_path_label.setProperty("skipTextAdmin", True)
        self.workspace_path_label.setProperty("role", "body")
        self.workspace_path_label.setWordWrap(True)
        storage_layout.addWidget(self.workspace_path_label)

        self.bundle_path_label = QLabel()
        self.bundle_path_label.setProperty("skipTextAdmin", True)
        self.bundle_path_label.setProperty("role", "body")
        self.bundle_path_label.setWordWrap(True)
        storage_layout.addWidget(self.bundle_path_label)

        self.database_path_label = QLabel()
        self.database_path_label.setProperty("skipTextAdmin", True)
        self.database_path_label.setProperty("role", "body")
        self.database_path_label.setWordWrap(True)
        storage_layout.addWidget(self.database_path_label)

        self.settings_path_label = QLabel()
        self.settings_path_label.setProperty("skipTextAdmin", True)
        self.settings_path_label.setProperty("role", "body")
        self.settings_path_label.setWordWrap(True)
        storage_layout.addWidget(self.settings_path_label)

        self.backups_path_label = QLabel()
        self.backups_path_label.setProperty("skipTextAdmin", True)
        self.backups_path_label.setProperty("role", "body")
        self.backups_path_label.setWordWrap(True)
        storage_layout.addWidget(self.backups_path_label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        open_app_button = QPushButton("Открыть папку приложения")
        open_app_button.setObjectName("settings-open-app-folder")
        open_app_button.setProperty("variant", "secondary")
        open_app_button.clicked.connect(lambda: self._open_path(self.bundle_root))
        buttons.addWidget(open_app_button)
        open_data_button = QPushButton("Открыть папку данных")
        open_data_button.setObjectName("settings-open-workspace-folder")
        open_data_button.setProperty("variant", "secondary")
        open_data_button.clicked.connect(lambda: self._open_path(self.workspace_root))
        buttons.addWidget(open_data_button)
        open_db_button = QPushButton("Открыть папку базы")
        open_db_button.setObjectName("settings-open-db-folder")
        open_db_button.setProperty("variant", "secondary")
        open_db_button.clicked.connect(lambda: self._open_path(self.database_path.parent))
        buttons.addWidget(open_db_button)
        buttons.addStretch(1)
        storage_layout.addLayout(buttons)
        layout.addWidget(storage_card)

        backup_card = CardFrame(role="card", shadow_color=self.shadow_color)
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(24, 22, 24, 22)
        backup_layout.setSpacing(14)

        backup_title = QLabel("Резервные копии")
        backup_title.setProperty("role", "section-title")
        backup_layout.addWidget(backup_title)

        backup_body = QLabel(
            "Копия создаётся из текущей SQLite базы в отдельную папку backups. "
            "Это обычная файловая копия SQLite, а не декоративная кнопка."
        )
        backup_body.setProperty("role", "body")
        backup_body.setWordWrap(True)
        backup_layout.addWidget(backup_body)

        self.backup_status_label = QLabel("Резервная копия ещё не создавалась в этой сессии.")
        self.backup_status_label.setProperty("skipTextAdmin", True)
        self.backup_status_label.setProperty("role", "body")
        self.backup_status_label.setWordWrap(True)
        backup_layout.addWidget(self.backup_status_label)

        backup_buttons = QHBoxLayout()
        backup_buttons.setContentsMargins(0, 0, 0, 0)
        backup_buttons.setSpacing(10)
        create_backup_button = QPushButton("Создать резервную копию")
        create_backup_button.setObjectName("settings-create-backup")
        create_backup_button.setProperty("variant", "primary")
        create_backup_button.clicked.connect(self.create_backup)
        backup_buttons.addWidget(create_backup_button)
        open_backups_button = QPushButton("Открыть папку копий")
        open_backups_button.setObjectName("settings-open-backups")
        open_backups_button.setProperty("variant", "secondary")
        open_backups_button.clicked.connect(lambda: self._open_path(self.backups_dir))
        backup_buttons.addWidget(open_backups_button)
        backup_buttons.addStretch(1)
        backup_layout.addLayout(backup_buttons)
        layout.addWidget(backup_card)

        layout.addStretch(1)
        self._refresh_storage_labels()
        return page

    def _build_advanced_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        paths_card = CardFrame(role="card", shadow_color=self.shadow_color)
        paths_layout = QVBoxLayout(paths_card)
        paths_layout.setContentsMargins(24, 22, 24, 22)
        paths_layout.setSpacing(14)

        title = QLabel("Сервисные пути")
        title.setProperty("role", "section-title")
        paths_layout.addWidget(title)

        docs_label = QLabel(f"Папка документации: {get_docs_path()}")
        docs_label.setProperty("role", "body")
        docs_label.setWordWrap(True)
        paths_layout.addWidget(docs_label)

        audit_label = QLabel(f"Папка аудита: {self.bundle_root / 'audit'}")
        audit_label.setProperty("role", "body")
        audit_label.setWordWrap(True)
        paths_layout.addWidget(audit_label)

        check_label = QLabel(f"Скрипт проверки Ollama: {get_check_script_path()}")
        check_label.setProperty("role", "body")
        check_label.setWordWrap(True)
        paths_layout.addWidget(check_label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        audit_button = QPushButton("Открыть аудит")
        audit_button.setObjectName("settings-open-audit")
        audit_button.setProperty("variant", "secondary")
        audit_button.clicked.connect(lambda: self._open_path(self.bundle_root / "audit"))
        buttons.addWidget(audit_button)
        docs_button = QPushButton("Открыть документацию")
        docs_button.setObjectName("settings-open-docs")
        docs_button.setProperty("variant", "secondary")
        docs_button.clicked.connect(lambda: self._open_path(get_docs_path()))
        buttons.addWidget(docs_button)
        buttons.addStretch(1)
        paths_layout.addLayout(buttons)
        top_row.addWidget(paths_card, 3)

        update_card = CardFrame(role="card", shadow_color=self.shadow_color)
        update_layout = QVBoxLayout(update_card)
        update_layout.setContentsMargins(24, 22, 24, 22)
        update_layout.setSpacing(14)

        update_title = QLabel("Обновления")
        update_title.setProperty("role", "section-title")
        update_layout.addWidget(update_title)

        self.update_status_label = QLabel("Проверка обновлений ещё не выполнялась.")
        self.update_status_label.setProperty("skipTextAdmin", True)
        self.update_status_label.setProperty("role", "body")
        self.update_status_label.setWordWrap(True)
        update_layout.addWidget(self.update_status_label)

        self.update_meta_label = QLabel(f"Текущая версия: {APP_VERSION}")
        self.update_meta_label.setProperty("skipTextAdmin", True)
        self.update_meta_label.setProperty("role", "muted")
        self.update_meta_label.setWordWrap(True)
        update_layout.addWidget(self.update_meta_label)

        self.build_meta_label = QLabel(
            f"Текущая сборка: {self.build_info.release_label} • Собрано: {self.build_info.built_at_label}"
        )
        self.build_meta_label.setProperty("skipTextAdmin", True)
        self.build_meta_label.setProperty("role", "muted")
        self.build_meta_label.setWordWrap(True)
        update_layout.addWidget(self.build_meta_label)

        update_buttons = QVBoxLayout()
        update_buttons.setContentsMargins(0, 0, 0, 0)
        update_buttons.setSpacing(10)
        self.update_check_button = QPushButton("Проверить обновления")
        self.update_check_button.setObjectName("settings-check-updates")
        self.update_check_button.setProperty("variant", "primary")
        self.update_check_button.clicked.connect(self.update_check_requested.emit)
        update_buttons.addWidget(self.update_check_button)

        self.open_release_button = QPushButton("Открыть страницу релиза")
        self.open_release_button.setObjectName("settings-open-release")
        self.open_release_button.setProperty("variant", "secondary")
        self.open_release_button.clicked.connect(self.open_release_requested.emit)
        self.open_release_button.setEnabled(False)
        update_buttons.addWidget(self.open_release_button)
        update_layout.addLayout(update_buttons)
        top_row.addWidget(update_card, 2)
        layout.addLayout(top_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(16)

        actions_card = CardFrame(role="card", shadow_color=self.shadow_color)
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(24, 22, 24, 22)
        actions_layout.setSpacing(14)

        actions_title = QLabel("Сервисные действия")
        actions_title.setProperty("role", "section-title")
        actions_layout.addWidget(actions_title)

        actions_body = QLabel(
            "Эти действия не меняют данные молча. Они либо открывают реальные каталоги, "
            "либо запускают честные диагностические скрипты."
        )
        actions_body.setProperty("role", "body")
        actions_body.setWordWrap(True)
        actions_layout.addWidget(actions_body)

        run_check_button = QPushButton("Запустить check_ollama.ps1")
        run_check_button.setObjectName("settings-run-check-script")
        run_check_button.setText(self._run_check_button_text())
        run_check_button.setProperty("variant", "primary")
        run_check_button.clicked.connect(self.run_check_script)
        actions_layout.addWidget(run_check_button)

        open_readme_button = QPushButton("Открыть инструкцию")
        open_readme_button.setObjectName("settings-open-readme")
        open_readme_button.setProperty("variant", "secondary")
        open_readme_button.clicked.connect(self.open_readme)
        actions_layout.addWidget(open_readme_button)
        lower_row.addWidget(actions_card, 3)

        admin_card = CardFrame(role="card", shadow_color=self.shadow_color)
        admin_layout = QVBoxLayout(admin_card)
        admin_layout.setContentsMargins(24, 22, 24, 22)
        admin_layout.setSpacing(14)

        admin_title = QLabel("Админ-доступ")
        admin_title.setProperty("role", "section-title")
        admin_layout.addWidget(admin_title)

        self.admin_status_label = QLabel("Пароль администратора не задан.")
        self.admin_status_label.setProperty("skipTextAdmin", True)
        self.admin_status_label.setProperty("role", "body")
        self.admin_status_label.setWordWrap(True)
        admin_layout.addWidget(self.admin_status_label)

        self.admin_hint_label = QLabel("Пароль задаётся и сбрасывается отдельной локальной утилитой.")
        self.admin_hint_label.setProperty("skipTextAdmin", True)
        self.admin_hint_label.setProperty("role", "muted")
        self.admin_hint_label.setWordWrap(True)
        admin_layout.addWidget(self.admin_hint_label)

        self.admin_setup_button = QPushButton("Настроить пароль")
        self.admin_setup_button.setObjectName("settings-admin-setup")
        self.admin_setup_button.setProperty("variant", "secondary")
        self.admin_setup_button.clicked.connect(self.admin_setup_requested.emit)
        admin_layout.addWidget(self.admin_setup_button)

        self.admin_password_input = QLineEdit()
        self.admin_password_input.setObjectName("settings-admin-password")
        self.admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password_input.setPlaceholderText("Введите админ-пароль")
        self.admin_password_input.setProperty("role", "form-input")
        self.admin_password_input.returnPressed.connect(self._emit_admin_login)
        admin_layout.addWidget(self.admin_password_input)

        admin_buttons = QHBoxLayout()
        admin_buttons.setContentsMargins(0, 0, 0, 0)
        admin_buttons.setSpacing(10)

        self.admin_login_button = QPushButton("Войти")
        self.admin_login_button.setObjectName("settings-admin-login")
        self.admin_login_button.setProperty("variant", "primary")
        self.admin_login_button.clicked.connect(self._emit_admin_login)
        admin_buttons.addWidget(self.admin_login_button)

        self.admin_logout_button = QPushButton("Выйти")
        self.admin_logout_button.setObjectName("settings-admin-logout")
        self.admin_logout_button.setProperty("variant", "secondary")
        self.admin_logout_button.clicked.connect(self.admin_logout_requested.emit)
        self.admin_logout_button.setEnabled(False)
        admin_buttons.addWidget(self.admin_logout_button)
        admin_layout.addLayout(admin_buttons)

        self.admin_debug_button = QPushButton("Включить режим отладки")
        self.admin_debug_button.setObjectName("settings-admin-debug")
        self.admin_debug_button.setProperty("variant", "secondary")
        self.admin_debug_button.setCheckable(True)
        self.admin_debug_button.setEnabled(False)
        self.admin_debug_button.clicked.connect(self._emit_admin_debug)
        admin_layout.addWidget(self.admin_debug_button)

        self.admin_text_button = QPushButton("Открыть редактор подписей")
        self.admin_text_button.setObjectName("settings-admin-text-editor")
        self.admin_text_button.setProperty("variant", "secondary")
        self.admin_text_button.setEnabled(False)
        self.admin_text_button.clicked.connect(self.admin_editor_requested.emit)
        admin_layout.addWidget(self.admin_text_button)
        admin_layout.addStretch(1)
        lower_row.addWidget(admin_card, 2, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(lower_row)

        layout.addStretch(1)
        return page

    def _build_diagnostics_card(self) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Диагностика")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.endpoint_tile = DiagnosticTile("Сервер", "Проверка...", "Ожидание ответа сервера", "neutral", self.shadow_color)
        self.model_tile = DiagnosticTile("Модель", "Проверка...", "Ожидание списка моделей", "neutral", self.shadow_color)
        self.last_check_tile = DiagnosticTile("Последняя проверка", "Нет данных", "Проверка ещё не выполнялась", "info", self.shadow_color)
        row.addWidget(self.endpoint_tile, 1)
        row.addWidget(self.model_tile, 1)
        row.addWidget(self.last_check_tile, 1)
        layout.addLayout(row)

        self.latency_card = CardFrame(role="subtle-card", shadow_color=self.shadow_color, shadow=False)
        latency_layout = QHBoxLayout(self.latency_card)
        latency_layout.setContentsMargins(16, 14, 16, 14)
        latency_layout.setSpacing(12)
        latency_layout.addWidget(IconBadge("MS", current_colors()["primary_soft"], current_colors()["primary"], size=28, radius=10, font_size=9))
        self.latency_label = QLabel("Время отклика: Нет данных")
        self.latency_label.setProperty("skipTextAdmin", True)
        self.latency_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {current_colors()['text']};")
        latency_layout.addWidget(self.latency_label)
        latency_layout.addStretch(1)
        layout.addWidget(self.latency_card)

        info_card = CardFrame(role="subtle-card", shadow_color=self.shadow_color, shadow=False)
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(14)
        info_layout.addWidget(IconBadge("i", current_colors()["primary_soft"], current_colors()["primary"], size=34, radius=12, font_size=16))

        info_text = QVBoxLayout()
        info_text.setContentsMargins(0, 0, 0, 0)
        info_text.setSpacing(4)
        info_title = QLabel("О локальной LLM")
        info_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
        info_body = QLabel(
            "Ollama и локальная модель работают полностью локально. Этот экран показывает только реально проверенные статусы."
        )
        info_body.setProperty("role", "body")
        info_body.setWordWrap(True)
        info_text.addWidget(info_title)
        info_text.addWidget(info_body)
        info_layout.addLayout(info_text, 1)

        readme_button = QPushButton("Подробнее в инструкции")
        readme_button.setObjectName("settings-readme-link")
        readme_button.setProperty("variant", "toolbar")
        readme_button.clicked.connect(self.open_readme)
        info_layout.addWidget(readme_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(info_card)

        self.error_label = QLabel("")
        self.error_label.setProperty("skipTextAdmin", True)
        self.error_label.setStyleSheet(f"color: {current_colors()['danger']}; font-size: 13px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        return card

    def _build_actions_card(self) -> QWidget:
        card = CardFrame(role="card", shadow_color=self.shadow_color)
        card.setMinimumWidth(252)
        card.setMaximumWidth(292)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Действия")
        title.setProperty("role", "section-title")
        layout.addWidget(title)

        refresh_button = QPushButton("Обновить список моделей")
        refresh_button.setObjectName("settings-refresh-models")
        refresh_button.setProperty("variant", "secondary")
        refresh_button.clicked.connect(self.refresh_models)
        layout.addWidget(refresh_button)

        start_button = QPushButton("Запустить Ollama")
        start_button.setObjectName("settings-start-ollama")
        start_button.setProperty("variant", "secondary")
        start_button.clicked.connect(self.start_ollama_server)
        layout.addWidget(start_button)

        check_button = QPushButton("Проверить соединение")
        check_button.setObjectName("settings-check-connection")
        check_button.setProperty("variant", "secondary")
        check_button.clicked.connect(self.check_connection)
        layout.addWidget(check_button)

        install_button = QPushButton("Автонастройка Ollama")
        install_button.setObjectName("settings-run-setup")
        install_button.setProperty("variant", "secondary")
        install_button.clicked.connect(self.run_setup_script)
        layout.addWidget(install_button)

        folder_button = QPushButton("Открыть папку моделей")
        folder_button.setObjectName("settings-open-models-folder")
        folder_button.setProperty("variant", "secondary")
        folder_button.clicked.connect(self.open_models_folder)
        layout.addWidget(folder_button)

        help_button = QPushButton("Инструкция по установке")
        help_button.setObjectName("settings-open-install-help")
        help_button.setProperty("variant", "secondary")
        help_button.clicked.connect(self.open_readme)
        layout.addWidget(help_button)

        helper = QLabel("Все действия относятся к локальной среде. Облачные API не используются.")
        helper.setWordWrap(True)
        helper.setProperty("role", "body")
        layout.addWidget(helper)
        layout.addStretch(1)
        return card

    def _labeled_block(self, title: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {current_colors()['text']};")
        layout.addWidget(label)
        return wrapper

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def _connect_dirty_tracking(self) -> None:
        self.theme_combo.currentIndexChanged.connect(self._mark_dirty)
        self.startup_view_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_preset_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_size_stepper.value_changed.connect(self._mark_dirty)
        self.auto_check_card.toggle.toggled.connect(self._mark_dirty)
        self.update_check_card.toggle.toggled.connect(self._mark_dirty)
        self.dlc_card.toggle.toggled.connect(self._mark_dirty)
        self.default_import_dir_input.textChanged.connect(self._mark_dirty)
        self.import_format_combo.currentIndexChanged.connect(self._mark_dirty)
        self.import_llm_card.toggle.toggled.connect(self._mark_dirty)
        self.training_mode_combo.currentIndexChanged.connect(self._mark_dirty)
        self.review_mode_combo.currentIndexChanged.connect(self._mark_dirty)
        self.queue_size_combo.currentIndexChanged.connect(self._mark_dirty)
        self.url_input.textChanged.connect(self._mark_dirty)
        self.model_combo.currentTextChanged.connect(self._mark_dirty)
        self.models_path_input.textChanged.connect(self._mark_dirty)
        self.timeout_stepper.value_changed.connect(self._mark_dirty)
        self.rewrite_card.toggle.toggled.connect(self._mark_dirty)
        self.followups_card.toggle.toggled.connect(self._mark_dirty)
        self.fallback_card.toggle.toggled.connect(self._mark_dirty)

    def switch_section(self, section: str) -> None:
        self.nav_panel.set_current(section)
        mapping = {
            "general": 0,
            "documents": 1,
            "training": 2,
            "ollama": 3,
            "data": 4,
            "advanced": 5,
        }
        self.settings_stack.setCurrentIndex(mapping[section])

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        compact = self.width() < 1080
        header_direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        if self.header_row.direction() != header_direction:
            self.header_row.setDirection(header_direction)

        main_direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        if self.main_row.direction() != main_direction:
            self.main_row.setDirection(main_direction)

        if compact:
            self.nav_panel.setMinimumWidth(0)
            self.nav_panel.setMaximumWidth(16777215)
            self.reset_button.setMinimumWidth(0)
            self.save_button.setMinimumWidth(0)
        else:
            self.nav_panel.setMinimumWidth(254)
            self.nav_panel.setMaximumWidth(304)

    def save_settings(self) -> None:
        self.settings = OllamaSettings(
            base_url=self.url_input.text().strip() or DEFAULT_OLLAMA_SETTINGS.base_url,
            model=self.model_combo.currentText().strip() or DEFAULT_OLLAMA_SETTINGS.model,
            models_path=Path(self.models_path_input.text().strip() or str(DEFAULT_OLLAMA_SETTINGS.models_path)),
            timeout_seconds=self.timeout_stepper.value(),
            rewrite_questions=self.rewrite_card.toggle.isChecked(),
            examiner_followups=self.followups_card.toggle.isChecked(),
            rule_based_fallback=self.fallback_card.toggle.isChecked(),
            theme_name=self._combo_value(self.theme_combo, DEFAULT_OLLAMA_SETTINGS.theme_name),
            startup_view=self._combo_value(self.startup_view_combo, DEFAULT_OLLAMA_SETTINGS.startup_view),
            auto_check_ollama_on_start=self.auto_check_card.toggle.isChecked(),
            show_dlc_teaser=self.dlc_card.toggle.isChecked(),
            default_import_dir=Path(self.default_import_dir_input.text().strip() or str(DEFAULT_OLLAMA_SETTINGS.default_import_dir)),
            preferred_import_format=self._combo_value(self.import_format_combo, DEFAULT_OLLAMA_SETTINGS.preferred_import_format),
            import_llm_assist=self.import_llm_card.toggle.isChecked(),
            default_training_mode=self._combo_value(self.training_mode_combo, DEFAULT_OLLAMA_SETTINGS.default_training_mode),
            review_mode=self._combo_value(self.review_mode_combo, DEFAULT_OLLAMA_SETTINGS.review_mode),
            training_queue_size=int(self.queue_size_combo.currentData() or DEFAULT_OLLAMA_SETTINGS.training_queue_size),
            font_preset=self._combo_value(self.font_preset_combo, DEFAULT_OLLAMA_SETTINGS.font_preset),
            font_size=self.font_size_stepper.value(),
            auto_check_updates_on_start=self.update_check_card.toggle.isChecked(),
        )
        self.check_connection()
        self.settings_saved.emit(self.settings)
        QMessageBox.information(self, "Настройки", "Параметры сохранены и применены.")
        self._dirty = False

    def reset_form(self) -> None:
        self.url_input.setText(self.settings.base_url)
        self.model_combo.setCurrentText(self.settings.model)
        self.models_path_input.setText(str(self.settings.models_path))
        self.timeout_stepper.set_value(self.settings.timeout_seconds)
        self.rewrite_card.toggle.setChecked(self.settings.rewrite_questions)
        self.followups_card.toggle.setChecked(self.settings.examiner_followups)
        self.fallback_card.toggle.setChecked(self.settings.rule_based_fallback)
        self._set_combo_value(self.theme_combo, self.settings.theme_name)
        self._set_combo_value(self.startup_view_combo, self.settings.startup_view)
        self._set_combo_value(self.font_preset_combo, self.settings.font_preset)
        self.font_size_stepper.set_value(self.settings.font_size)
        self._refresh_typography_preview()
        self.auto_check_card.toggle.setChecked(self.settings.auto_check_ollama_on_start)
        self.update_check_card.toggle.setChecked(self.settings.auto_check_updates_on_start)
        self.dlc_card.toggle.setChecked(self.settings.show_dlc_teaser)
        self.default_import_dir_input.setText(str(self.settings.default_import_dir))
        self._set_combo_value(self.import_format_combo, self.settings.preferred_import_format)
        self.import_llm_card.toggle.setChecked(self.settings.import_llm_assist)
        self._set_combo_value(self.training_mode_combo, self.settings.default_training_mode)
        self._set_combo_value(self.review_mode_combo, self.settings.review_mode)
        self._set_combo_value(self.queue_size_combo, self.settings.training_queue_size)
        self._refresh_storage_labels()
        if self.settings.auto_check_ollama_on_start:
            self.check_connection()
        else:
            self.set_diagnostics_pending("Статус ещё не проверен. Нажмите «Проверить соединение».")
        self._dirty = False

    def select_import_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Папка импорта",
            str(Path(self.default_import_dir_input.text().strip() or self.settings.default_import_dir)),
        )
        if path:
            self.default_import_dir_input.setText(path)

    def open_models_folder(self) -> None:
        path = Path(self.models_path_input.text().strip() or str(DEFAULT_OLLAMA_SETTINGS.models_path))
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def open_readme(self) -> None:
        self._open_path(get_readme_path())

    def create_backup(self) -> None:
        if not self.database_path.exists():
            QMessageBox.warning(self, "Резервная копия", f"Файл базы не найден:\n{self.database_path}")
            return
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.backups_dir / f"exam_trainer-{timestamp}.db"
        try:
            shutil.copy2(self.database_path, target)
        except OSError as exc:
            QMessageBox.critical(self, "Резервная копия", f"Не удалось создать резервную копию:\n{exc}")
            return
        self.backup_status_label.setText(f"Последняя копия: {target.name}")
        self._refresh_storage_labels()
        QMessageBox.information(self, "Резервная копия", f"Резервная копия создана:\n{target}")

    def _apply_diagnostics(self, diagnostics: OllamaDiagnostics) -> None:
        self._last_diagnostics = diagnostics
        if diagnostics.endpoint_ok and diagnostics.model_ok:
            self.status_pill.setStyleSheet(
                f"background: {current_colors()['success_soft']}; color: {current_colors()['success']}; border-radius: 999px; padding: 10px 18px; "
                "font-size: 14px; font-weight: 700;"
            )
            self.status_pill.setText("Подключено")
        elif diagnostics.endpoint_ok:
            self.status_pill.setStyleSheet(
                f"background: {current_colors()['warning_soft']}; color: {current_colors()['warning']}; border-radius: 999px; padding: 10px 18px; "
                "font-size: 14px; font-weight: 700;"
            )
            self.status_pill.setText("Сервер отвечает")
        else:
            self.status_pill.setStyleSheet(
                f"background: {current_colors()['danger_soft']}; color: {current_colors()['danger']}; border-radius: 999px; padding: 10px 18px; "
                "font-size: 14px; font-weight: 700;"
            )
            self.status_pill.setText("Недоступно")

        configured_models_path = self.models_path_input.text().strip()
        runtime_path_note = ""
        if diagnostics.resolved_models_path:
            runtime_path_note = f"Каталог моделей: {diagnostics.resolved_models_path}"
            if configured_models_path and Path(configured_models_path) != Path(diagnostics.resolved_models_path):
                runtime_path_note += "\nНастроенный путь не совпадает с фактически используемым. Проверьте миграцию моделей."
        endpoint_body = diagnostics.endpoint_message if diagnostics.endpoint_ok else (diagnostics.error_text or diagnostics.endpoint_message)
        if runtime_path_note:
            endpoint_body = f"{endpoint_body}\n{runtime_path_note}"
        self.endpoint_tile.set_content(
            "Сервер: OK" if diagnostics.endpoint_ok else "Сервер: ошибка",
            "Сервер отвечает" if diagnostics.endpoint_ok else "Нет ответа",
            endpoint_body,
            "success" if diagnostics.endpoint_ok else "danger",
        )
        self.model_tile.set_content(
            "Модель загружена" if diagnostics.model_ok else "Статус модели",
            diagnostics.model_name or (self.model_combo.currentText().strip() or DEFAULT_OLLAMA_SETTINGS.model),
            diagnostics.model_size_label or diagnostics.model_message,
            "success" if diagnostics.model_ok else "warning",
        )
        self.last_check_tile.set_content(
            "Последняя проверка",
            diagnostics.last_checked_label,
            "Диагностика сервера и модели",
            "info",
        )
        self.latency_label.setText(f"Время отклика: {diagnostics.latency_label}")
        self.error_label.setText("" if diagnostics.endpoint_ok else f"Ошибка: {diagnostics.error_text or diagnostics.endpoint_message}")

    def _refresh_storage_labels(self) -> None:
        self.workspace_path_label.setText(f"Папка данных: {self.workspace_root}")
        self.bundle_path_label.setText(f"Папка приложения: {self.bundle_root}")
        self.database_path_label.setText(f"База данных: {self.database_path}")
        self.settings_path_label.setText(f"Файл настроек: {self.settings_path}")
        self.backups_path_label.setText(f"Папка резервных копий: {self.backups_dir}")

    def set_admin_state(self, state: AdminAccessState, unlocked: bool) -> None:
        if state.configured:
            status = "Админ-пароль задан." if not unlocked else "Админ-доступ открыт."
        else:
            status = "Админ-пароль не задан."
        self.admin_status_label.setText(status)
        self.admin_hint_label.setText(
            "Пароль можно задать, изменить или сбросить через кнопку «Настроить пароль»."
            if not state.password_hint
            else f"Подсказка: {state.password_hint}"
        )
        self.admin_setup_button.setText("Изменить или сбросить пароль" if state.configured else "Создать пароль")
        self.admin_login_button.setEnabled(state.configured and not unlocked)
        self.admin_password_input.setEnabled(state.configured and not unlocked)
        self.admin_logout_button.setEnabled(unlocked)
        self.admin_debug_button.setEnabled(unlocked)
        self.admin_text_button.setEnabled(unlocked)
        self.admin_debug_button.setChecked(state.debug_mode if unlocked else False)
        self.admin_debug_button.setText("Выключить режим отладки" if state.debug_mode and unlocked else "Включить режим отладки")
        if not unlocked:
            self.admin_password_input.clear()

    def set_update_info(self, update_info: UpdateInfo, pending: bool = False) -> None:
        build_line = f"Текущая сборка: {self.build_info.release_label}"
        if pending:
            self.update_status_label.setText("Проверяем наличие новой версии на GitHub.")
            self.update_meta_label.setText(f"{build_line}. Канал обновлений: GitHub Releases.")
            self.open_release_button.setEnabled(False)
            return
        if update_info.error_text:
            self.update_status_label.setText(update_info.error_text)
            self.update_meta_label.setText(f"{build_line}. Последняя попытка: {update_info.checked_label}")
            self.open_release_button.setEnabled(True)
            return
        if update_info.update_available:
            self.update_status_label.setText(
                f"Доступна новая версия {update_info.latest_version}. Можно открыть релиз и обновиться вручную."
            )
            self.update_meta_label.setText(
                f"{build_line}. Сейчас установлена версия {update_info.current_version}. Проверено: {update_info.checked_label}"
            )
            self.open_release_button.setEnabled(True)
            return
        self.update_status_label.setText("Установлена актуальная версия приложения.")
        self.update_meta_label.setText(f"{build_line}. Проверено: {update_info.checked_label}")
        self.open_release_button.setEnabled(True)

    def _open_path(self, path: Path) -> None:
        target = path
        if path.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _check_script_display_name(self) -> str:
        return platform_helpers.check_script_name() or "diagnostic script"

    def _run_check_button_text(self) -> str:
        return "Запустить проверку Ollama"

    def _setup_launch_message(self) -> str:
        host = platform_helpers.script_host_label()
        return (
            "Запущен скрипт автоподготовки Ollama. "
            f"Он открыт в {host}. После завершения вернитесь сюда и нажмите "
            "«Проверить соединение»."
        )

    def _check_launch_message(self) -> str:
        host = platform_helpers.script_host_label()
        script_name = platform_helpers.check_script_name() or "diagnostic script"
        return f"Запущен диагностический скрипт {script_name} в {host}."

    def _unsupported_platform_message(self) -> str:
        return (
            "Для этой платформы автоскрипт не подготовлен. "
            "Откройте инструкцию и выполните настройку локального Ollama вручную."
        )

    def run_setup_script(self) -> None:
        self._launch_script(get_setup_script_path(), "Ollama", self._setup_launch_message())

    def run_check_script(self) -> None:
        self._launch_script(get_check_script_path(), "Ollama", self._check_launch_message())

    def _launch_script(self, script_path: Path | None, title: str, success_message: str) -> None:
        if script_path is None:
            QMessageBox.warning(self, title, self._unsupported_platform_message())
            return
        if not script_path.exists():
            QMessageBox.warning(self, title, f"Скрипт не найден:\n{script_path}")
            return
        try:
            platform_helpers.launch_support_script(script_path)
        except OSError as exc:
            QMessageBox.critical(self, title, f"Не удалось запустить скрипт:\n{exc}")
            return
        QMessageBox.information(self, title, success_message)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
            return
        text_index = combo.findText(str(value))
        if text_index >= 0:
            combo.setCurrentIndex(text_index)

    @staticmethod
    def _combo_value(combo: QComboBox, default):
        return combo.currentData() if combo.currentData() is not None else default

    def _emit_admin_login(self) -> None:
        password = self.admin_password_input.text().strip()
        if password:
            self.admin_login_requested.emit(password)

    def _emit_admin_debug(self) -> None:
        self.admin_debug_toggled.emit(self.admin_debug_button.isChecked())

    def _refresh_typography_preview(self) -> None:
        preset_key = self._combo_value(self.font_preset_combo, DEFAULT_OLLAMA_SETTINGS.font_preset)
        font_size = self.font_size_stepper.value()
        preset = FONT_PRESETS.get(preset_key, FONT_PRESETS[DEFAULT_OLLAMA_SETTINGS.font_preset])
        resolved_family = resolve_font_family(preset_key)

        title_font = app_font(preset_key, min(font_size + 3, 18))
        body_font = app_font(preset_key, font_size)
        meta_font = app_font(preset_key, max(9, font_size - 1))
        button_font = app_font(preset_key, font_size)

        self.typography_preview_title.setFont(title_font)
        self.typography_preview_body.setFont(body_font)
        self.typography_preview_chip.setFont(meta_font)
        self.typography_preview_button.setFont(button_font)
        self.typography_preview_meta.setText(
            f"{preset['label']} • {preset['description']} • активное семейство: {resolved_family} • размер: {font_size} pt"
        )

    def set_diagnostics_pending(self, message: str = "Проверка...") -> None:
        self.status_pill.setStyleSheet(
            f"background: {current_colors()['warning_soft']}; color: {current_colors()['warning']}; border-radius: 999px; padding: 10px 18px; "
            "font-size: 14px; font-weight: 700;"
        )
        self.status_pill.setText("Автопроверка отключена" if message == "Автопроверка отключена" else "Проверка...")
        self.endpoint_tile.set_content("Сервер: проверка", "Ожидание ответа", message, "warning")
        self.model_tile.set_content(
            "Статус модели",
            self.model_combo.currentText().strip() or DEFAULT_OLLAMA_SETTINGS.model,
            "Диагностика ещё не завершена",
            "neutral",
        )
        self.last_check_tile.set_content("Последняя проверка", "Ожидание", "Результат появится после ответа сервера", "info")
        self.latency_label.setText("Время отклика: Нет данных")
        self.error_label.setText("")

    def set_diagnostics(self, diagnostics: OllamaDiagnostics) -> None:
        self._apply_diagnostics(diagnostics)

    def _build_diagnostics_service(self) -> OllamaService:
        timeout_seconds = min(float(self.timeout_stepper.value()), 3.0)
        models_path = Path(self.models_path_input.text().strip() or str(DEFAULT_OLLAMA_SETTINGS.models_path))
        return OllamaService(self.url_input.text().strip(), timeout_seconds, models_path)

    def check_connection(self) -> None:
        self._run_diagnostics(refresh_models=False, pending_message="Проверяем адрес сервера и модель")

    def refresh_models(self) -> None:
        self._run_diagnostics(refresh_models=True, pending_message="Проверяем сервер, при необходимости запускаем Ollama и обновляем модели")

    def start_ollama_server(self) -> None:
        self._run_diagnostics(refresh_models=True, pending_message="Пробуем запустить Ollama и дождаться готовности сервера")

    def _run_diagnostics(self, refresh_models: bool, pending_message: str) -> None:
        if self._diagnostics_thread is not None and self._diagnostics_thread.isRunning():
            return
        self._refresh_models_after_check = refresh_models
        self.set_diagnostics_pending(pending_message)
        model_name = self.model_combo.currentText().strip() or self.settings.model
        self._diagnostics_thread = FunctionThread(lambda: self._build_diagnostics_service().inspect(model_name))
        self._diagnostics_thread.succeeded.connect(self._finish_diagnostics)
        self._diagnostics_thread.failed.connect(self._fail_diagnostics)
        self._diagnostics_thread.finished.connect(self._clear_diagnostics_thread)
        self._diagnostics_thread.start()

    def _finish_diagnostics(self, diagnostics: OllamaDiagnostics) -> None:
        if self._refresh_models_after_check:
            current = self.model_combo.currentText().strip() or self.settings.model
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            models = diagnostics.available_models or [current]
            self.model_combo.addItems(models)
            self.model_combo.setCurrentText(current if current in models else models[0])
            self.model_combo.blockSignals(False)
        self._apply_diagnostics(diagnostics)
        self.diagnostics_changed.emit(diagnostics)

    def _fail_diagnostics(self, error_text: str) -> None:
        diagnostics = OllamaDiagnostics(
            endpoint_ok=False,
            model_ok=False,
            endpoint_message="Сервер недоступен",
            model_message="Модель не проверена",
            model_name=self.model_combo.currentText().strip() or DEFAULT_OLLAMA_SETTINGS.model,
            error_text=error_text,
        )
        self._apply_diagnostics(diagnostics)
        self.diagnostics_changed.emit(diagnostics)

    def refresh_theme(self) -> None:
        self._refresh_typography_preview()
        self.nav_panel.refresh_theme()
        self.endpoint_tile.refresh_theme()
        self.model_tile.refresh_theme()
        self.last_check_tile.refresh_theme()
        self.timeout_stepper.refresh_theme()
        self.font_size_stepper.refresh_theme()
        if self._last_diagnostics is not None:
            self._apply_diagnostics(self._last_diagnostics)
        else:
            self.set_diagnostics_pending("Автопроверка отключена" if not self.settings.auto_check_ollama_on_start else "Проверка...")

    def _clear_diagnostics_thread(self) -> None:
        if self._diagnostics_thread is not None:
            self._diagnostics_thread.deleteLater()
        self._diagnostics_thread = None
        self._refresh_models_after_check = False

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._diagnostics_thread is not None:
            try:
                self._diagnostics_thread.succeeded.disconnect()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._diagnostics_thread.failed.disconnect()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._diagnostics_thread.finished.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._diagnostics_thread.wait(3500)
        super().closeEvent(event)
