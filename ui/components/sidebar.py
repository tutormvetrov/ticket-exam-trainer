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
from ui.theme import current_colors


NAV_ITEMS = [
    ("library", "Библиотека", "library"),
    ("subjects", "Предметы", "subjects"),
    ("sections", "Разделы", "sections"),
    ("tickets", "Билеты", "tickets"),
    ("import", "Импорт документов", "import"),
    ("training", "Тренировка", "training"),
    ("dialogue", "Диалог", "dialogue"),
    ("statistics", "Статистика", "statistics"),
    ("knowledge-map", "Карта знаний", "knowledge-map"),
    ("defense", "Подготовка к защите", "defense"),
    ("settings", "Настройки", "settings"),
]


class Sidebar(QWidget):
    section_selected = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.build_info = get_runtime_build_info()
        self.setMinimumWidth(248)
        self.setMaximumWidth(304)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setProperty("role", "sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.brand = QFrame()
        self.brand.setMinimumHeight(76)
        brand_layout = QHBoxLayout(self.brand)
        brand_layout.setContentsMargins(10, 10, 12, 10)
        brand_layout.setSpacing(12)
        brand_layout.addWidget(LogoMark(52), 0, Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)

        title = QLabel("Тезис")
        title.setProperty("role", "brand-title")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_box.addWidget(title)

        subtitle = QLabel("Local exam engine")
        subtitle.setProperty("role", "brand-subtitle")
        title_box.addWidget(subtitle)

        brand_layout.addLayout(title_box, 1)
        layout.addWidget(self.brand)

        self.divider = QFrame()
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)

        nav_caption = QLabel("НАВИГАЦИЯ")
        nav_caption.setProperty("role", "nav-caption")
        layout.addWidget(nav_caption)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        self._button_icons: dict[str, str] = {}
        for key, label, icon_name in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName(f"sidebar-{key}")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(42)
            button.setProperty("variant", "nav")
            button.clicked.connect(lambda checked=False, value=key: self.section_selected.emit(value))
            self.button_group.addButton(button)
            self.buttons[key] = button
            self._button_icons[key] = icon_name
            layout.addWidget(button)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        status_card = CardFrame(role="subtle-card", shadow_color=shadow_color)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        self.status_dot = QLabel("●")
        status_row.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.status_label = QLabel("Ollama: проверка нужна")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)

        self.status_tail = QLabel("•")
        status_row.addWidget(self.status_tail)
        status_layout.addLayout(status_row)

        self.model_label = QLabel("Модель: локальная Qwen")
        self.model_label.setProperty("role", "body")
        self.model_label.setWordWrap(True)
        status_layout.addWidget(self.model_label)

        self.url_label = QLabel("http://localhost:11434")
        self.url_label.setProperty("role", "body")
        self.url_label.setWordWrap(True)
        status_layout.addWidget(self.url_label)

        self.readiness_label = QLabel("Готовность: —")
        self.readiness_label.setProperty("role", "body")
        self.readiness_label.setWordWrap(True)
        status_layout.addWidget(self.readiness_label)
        layout.addWidget(status_card)

        self.version_label = QLabel(self.build_info.release_label)
        self.version_label.setProperty("role", "muted")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        self._current_status_tone = "warning"
        self.set_current("library")
        self.refresh_theme()

    def set_current(self, key: str) -> None:
        button = self.buttons.get(key)
        if button:
            button.setChecked(True)

    def set_ollama_status(self, available: bool, label_text: str, model_text: str, url_text: str, tone: str = "auto") -> None:
        if tone == "auto":
            tone = "success" if available else "danger"
        colors = current_colors()
        tone_colors = {
            "success": (colors["success"], colors["success"]),
            "warning": (colors["warning"], colors["warning"]),
            "danger": (colors["danger"], colors["danger"]),
        }
        color, text_color = tone_colors.get(tone, tone_colors["danger"])
        self._current_status_tone = tone
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_tail.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setStyleSheet(f"color: {text_color}; font-size: 14px; font-weight: 700;")
        self.status_label.setText(label_text)
        self.model_label.setText(model_text)
        self.url_label.setText(url_text)

    def set_readiness(self, percent: int) -> None:
        self.readiness_label.setText(f"Готовность: {percent}%")

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.brand.setStyleSheet(
            f"background: {colors['card_bg']}; border: 1px solid {colors['border_strong']}; border-radius: 18px;"
        )
        self.divider.setStyleSheet(f"background: {colors['border']};")
        for key, button in self.buttons.items():
            apply_button_icon(button, self._button_icons[key], size=18)
        self.status_dot.setStyleSheet(f"color: {colors['text_tertiary']}; font-size: 14px;")
        self.status_tail.setStyleSheet(f"color: {colors['text_tertiary']}; font-size: 14px;")
        self.status_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 14px; font-weight: 700;")
        self.set_ollama_status(
            available=self._current_status_tone == "success",
            label_text=self.status_label.text(),
            model_text=self.model_label.text(),
            url_text=self.url_label.text(),
            tone=self._current_status_tone,
        )
