from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components.common import OrnamentalDivider
from ui.icons import apply_button_icon


class TopBar(QWidget):
    settings_clicked = Signal()

    _PAGE_META = {
        "library": ("Библиотека", "Документы, статусы и быстрый вход в режимы."),
        "subjects": ("Предметы", "Сводка по предметам и прогресс освоения."),
        "sections": ("Разделы", "Структура и состав импортированных материалов."),
        "tickets": ("Билеты", "Карты ответа, профили и слабые зоны."),
        "import": ("Импорт", "Последний прогон, следующие шаги и контроль статуса."),
        "training": ("Тренировка", "Очередь вопросов, режимы и оценка ответов."),
        "dialogue": ("Диалог", "Устная репетиция по билетам и активным сессиям."),
        "statistics": ("Статистика", "Результаты, динамика и зоны риска."),
        "defense": ("Подготовка к защите", "Контур доклада, слайды и репетиция защиты."),
        "settings": ("Настройки", "Тема, Ollama, хранение и сервисные действия."),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "titlebar")
        self.layout_root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.layout_root.setContentsMargins(24, 12, 24, 12)
        self.layout_root.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)

        self.page_title = QLabel()
        self.page_title.setProperty("role", "page-title-serif")
        self.page_title.setProperty("skipTextAdmin", True)
        title_box.addWidget(self.page_title)

        self.page_subtitle = QLabel()
        self.page_subtitle.setProperty("role", "subtitle-italic")
        self.page_subtitle.setProperty("skipTextAdmin", True)
        title_box.addWidget(self.page_subtitle)

        self.layout_root.addLayout(title_box)

        self.divider = OrnamentalDivider()
        self.divider.setProperty("line-tone", "border")
        self.divider.setProperty("dot-tone", "border_strong")
        self.layout_root.addWidget(self.divider, 1, Qt.AlignmentFlag.AlignVCenter)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setObjectName("topbar-settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setProperty("variant", "ghost")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        self.layout_root.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_current_section("library")
        self.refresh_theme()

    def set_page(self, title: str, subtitle: str = "") -> None:
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        self.page_subtitle.setVisible(bool(subtitle))

    def set_current_section(self, key: str) -> None:
        title, subtitle = self._PAGE_META.get(key, ("Тезис", "Локальный тренажёр билетов и ответов."))
        self.set_page(title, subtitle)

    def refresh_theme(self) -> None:
        apply_button_icon(self.settings_button, "settings", tone="ink_muted")
        self.settings_button.style().unpolish(self.settings_button)
        self.settings_button.style().polish(self.settings_button)
        self.divider.update()
