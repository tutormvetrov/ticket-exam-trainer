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
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui.components.common import CardFrame, LogoMark


NAV_ITEMS = [
    ("library", "Библиотека", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ("subjects", "Предметы", QStyle.StandardPixmap.SP_DirHomeIcon),
    ("sections", "Разделы", QStyle.StandardPixmap.SP_DirIcon),
    ("tickets", "Билеты", QStyle.StandardPixmap.SP_FileIcon),
    ("import", "Импорт документов", QStyle.StandardPixmap.SP_ArrowUp),
    ("training", "Тренировка", QStyle.StandardPixmap.SP_MediaPlay),
    ("statistics", "Статистика", QStyle.StandardPixmap.SP_FileDialogInfoView),
    ("settings", "Настройки", QStyle.StandardPixmap.SP_FileDialogContentsView),
]


class Sidebar(QWidget):
    section_selected = Signal(str)

    def __init__(self, shadow_color) -> None:
        super().__init__()
        self.setMinimumWidth(228)
        self.setMaximumWidth(282)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setProperty("role", "sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        brand = QWidget()
        brand.setMinimumHeight(72)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(6, 6, 6, 6)
        brand_layout.setSpacing(10)
        brand_layout.addWidget(LogoMark(52), 0, Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title = QLabel("Тренажёр билетов к вузовским экзаменам")
        title.setProperty("role", "window-title")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_box.addWidget(title)
        brand_layout.addLayout(title_box, 1)
        layout.addWidget(brand)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #E3EAF2;")
        layout.addWidget(divider)

        nav_caption = QLabel("НАВИГАЦИЯ")
        nav_caption.setProperty("role", "nav-caption")
        layout.addWidget(nav_caption)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        for key, label, icon_kind in NAV_ITEMS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(42)
            button.setProperty("variant", "nav")
            button.setIcon(self.style().standardIcon(icon_kind))
            button.clicked.connect(lambda checked=False, value=key: self.section_selected.emit(value))
            self.button_group.addButton(button)
            self.buttons[key] = button
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
        self.status_dot.setStyleSheet("color: #94A3B8; font-size: 14px;")
        status_row.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.status_label = QLabel("Ollama: проверка нужна")
        self.status_label.setStyleSheet("color: #64748B; font-size: 14px; font-weight: 700;")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)

        self.status_tail = QLabel("•")
        self.status_tail.setStyleSheet("color: #94A3B8; font-size: 14px;")
        status_row.addWidget(self.status_tail)
        status_layout.addLayout(status_row)

        self.model_label = QLabel("Модель: mistral:instruct")
        self.model_label.setProperty("role", "body")
        self.model_label.setWordWrap(True)
        status_layout.addWidget(self.model_label)

        self.url_label = QLabel("http://localhost:11434")
        self.url_label.setProperty("role", "body")
        self.url_label.setWordWrap(True)
        status_layout.addWidget(self.url_label)
        layout.addWidget(status_card)

        version = QLabel("v1.0.0 • Локальный режим")
        version.setProperty("role", "muted")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        self.set_current("library")

    def set_current(self, key: str) -> None:
        button = self.buttons.get(key)
        if button:
            button.setChecked(True)

    def set_ollama_status(self, available: bool, label_text: str, model_text: str, url_text: str, tone: str = "auto") -> None:
        if tone == "auto":
            tone = "success" if available else "danger"
        colors = {
            "success": ("#18B06A", "#189D63"),
            "warning": ("#F59A23", "#D97706"),
            "danger": ("#D35469", "#D35469"),
        }
        color, text_color = colors.get(tone, colors["danger"])
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_tail.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setStyleSheet(f"color: {text_color}; font-size: 14px; font-weight: 700;")
        self.status_label.setText(label_text)
        self.model_label.setText(model_text)
        self.url_label.setText(url_text)
