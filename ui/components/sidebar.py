from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.build_info import get_runtime_build_info
from ui.components.common import CardFrame, LogoMark
from ui.icons import apply_button_icon


NAV_ITEMS = [
    ("library", "Библиотека", "library"),
    ("subjects", "Предметы", "subjects"),
    ("sections", "Разделы", "sections"),
    ("tickets", "Билеты", "tickets"),
    ("import", "Импорт документов", "import"),
    ("training", "Тренировка", "training"),
    ("dialogue", "Диалог", "dialogue"),
    ("statistics", "Статистика", "statistics"),
    ("defense", "Подготовка к защите", "defense"),
    ("settings", "Настройки", "settings"),
]


class Sidebar(QWidget):
    section_selected = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.build_info = get_runtime_build_info()
        self.setMinimumWidth(232)
        self.setMaximumWidth(288)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setProperty("role", "sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.brand = QFrame()
        self.brand.setProperty("role", "sidebar-brand")
        self.brand.setMinimumHeight(50)
        brand_layout = QHBoxLayout(self.brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)
        brand_layout.addWidget(LogoMark(42), 0, Qt.AlignmentFlag.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title_box.addStretch(1)

        title = QLabel("Тезис")
        title.setProperty("role", "brand-title")
        title.setWordWrap(False)
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_box.addWidget(title)
        title_box.addStretch(1)

        brand_layout.addLayout(title_box, 1)
        layout.addWidget(self.brand)

        self.divider = QFrame()
        self.divider.setProperty("role", "chrome-divider")
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)

        nav_caption = QLabel("НАВИГАЦИЯ")
        nav_caption.setProperty("role", "nav-caption")
        layout.addWidget(nav_caption)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        self._current_key = "library"
        self._button_icons: dict[str, str] = {}
        for key, label, icon_name in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName(f"sidebar-{key}")
            button.setCheckable(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(38)
            button.setProperty("variant", "nav")
            button.setProperty("active-warm", "false")
            button.clicked.connect(lambda checked=False, value=key: self.section_selected.emit(value))
            self.button_group.addButton(button)

            self.buttons[key] = button
            self._button_icons[key] = icon_name
            layout.addWidget(button)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.status_card = CardFrame(role="chrome-card", shadow_color=shadow_color, shadow=False)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(6)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setProperty("role", "chrome-status-dot")
        self.status_dot.setProperty("tone", "warning")
        status_row.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.status_label = QLabel("Ollama: проверка нужна")
        self.status_label.setProperty("role", "chrome-status")
        self.status_label.setProperty("tone", "warning")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)

        self.readiness_label = QLabel("Готовность: —")
        self.readiness_label.setProperty("role", "chrome-readiness")
        self.readiness_label.setWordWrap(False)
        status_row.addWidget(self.readiness_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_layout.addLayout(status_row)

        self.model_label = QLabel("Модель: локальная Qwen")
        self.model_label.setProperty("role", "chrome-meta")
        self.model_label.setWordWrap(True)
        status_layout.addWidget(self.model_label)

        self.url_label = QLabel("http://localhost:11434")
        self.url_label.setProperty("role", "chrome-meta")
        self.url_label.setWordWrap(True)
        status_layout.addWidget(self.url_label)
        layout.addWidget(self.status_card)

        self.version_label = QLabel(self.build_info.release_label)
        self.version_label.setProperty("role", "chrome-version")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        self._current_status_tone = "warning"
        self.set_current("library")
        self.refresh_theme()

    def set_current(self, key: str) -> None:
        self._current_key = key
        for nav_key, button in self.buttons.items():
            is_active = nav_key == key
            button.setProperty("active-warm", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            icon_tone = "rust" if is_active else "ink_muted"
            apply_button_icon(
                button,
                self._button_icons[nav_key],
                size=18,
                tone=icon_tone,
                on_tone=icon_tone,
            )

    def set_ollama_status(self, available: bool, label_text: str, model_text: str, url_text: str, tone: str = "auto") -> None:
        if tone == "auto":
            tone = "success" if available else "danger"
        self._current_status_tone = tone
        self.status_dot.setProperty("tone", tone)
        self.status_label.setProperty("tone", tone)
        self._refresh_status_theme()
        self.status_label.setText(label_text)
        self.model_label.setText(model_text)
        self.url_label.setText(url_text)

    def set_readiness(self, percent: int) -> None:
        self.readiness_label.setText(f"Готовность: {percent}%")

    def refresh_theme(self) -> None:
        self.set_current(self._current_key)
        self.set_ollama_status(
            available=self._current_status_tone == "success",
            label_text=self.status_label.text(),
            model_text=self.model_label.text(),
            url_text=self.url_label.text(),
            tone=self._current_status_tone,
        )

    def _refresh_status_theme(self) -> None:
        for widget in (self.status_dot, self.status_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
