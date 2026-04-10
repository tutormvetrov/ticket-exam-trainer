from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class TopBar(QWidget):
    search_changed = Signal(str)
    settings_clicked = Signal()
    ollama_clicked = Signal()
    theme_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(12)

        search_shell = QFrame()
        search_shell.setProperty("role", "search-shell")
        search_shell.setMinimumWidth(250)
        search_shell.setMaximumWidth(360)
        search_shell.setFixedHeight(40)
        search_layout = QHBoxLayout(search_shell)
        search_layout.setContentsMargins(12, 0, 10, 0)
        search_layout.setSpacing(10)
        icon = QLabel("⌕")
        icon.setStyleSheet("font-size: 18px; color: #8C97A5;")
        search_layout.addWidget(icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по билетам...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.textChanged.connect(self.search_changed.emit)
        search_layout.addWidget(self.search_input, 1)
        layout.addWidget(search_shell, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("topbar-settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(48, 40)
        self.settings_button.setProperty("variant", "toolbar-ghost")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_button)

        self.ollama_button = QPushButton("⟳  Настройки Ollama")
        self.ollama_button.setObjectName("topbar-ollama")
        self.ollama_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ollama_button.setProperty("variant", "toolbar")
        self.ollama_button.clicked.connect(self.ollama_clicked.emit)
        layout.addWidget(self.ollama_button)

        self.theme_button = QPushButton("◔  Тёмная тема")
        self.theme_button.setObjectName("topbar-theme")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setProperty("variant", "toolbar")
        self.theme_button.clicked.connect(self.theme_clicked.emit)
        layout.addWidget(self.theme_button)

    def set_theme_label(self, palette_name: str) -> None:
        self.theme_button.setText("◔  Тёмная тема" if palette_name == "light" else "☼  Светлая тема")
