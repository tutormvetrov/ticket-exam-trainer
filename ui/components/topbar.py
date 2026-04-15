from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QWidget

from ui.theme import current_colors


class TopBar(QWidget):
    search_changed = Signal(str)
    settings_clicked = Signal()
    ollama_clicked = Signal()
    theme_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._palette_name = "light"
        self.layout_root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.layout_root.setContentsMargins(28, 16, 28, 16)
        self.layout_root.setSpacing(12)

        self.search_shell = QFrame()
        self.search_shell.setProperty("role", "search-shell")
        self.search_shell.setMinimumWidth(250)
        self.search_shell.setMaximumWidth(360)
        self.search_shell.setFixedHeight(40)
        search_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.search_shell)
        search_layout.setContentsMargins(12, 0, 10, 0)
        search_layout.setSpacing(10)
        self.search_icon = QLabel("⌕")
        self.search_icon.setStyleSheet(f"font-size: 18px; color: {current_colors()['text_tertiary']};")
        search_layout.addWidget(self.search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по билетам...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.textChanged.connect(self.search_changed.emit)
        search_layout.addWidget(self.search_input, 1)
        self.layout_root.addWidget(self.search_shell, 1, Qt.AlignmentFlag.AlignLeft)

        self.layout_root.addStretch(1)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("topbar-settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(48, 40)
        self.settings_button.setProperty("variant", "toolbar-ghost")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        self.layout_root.addWidget(self.settings_button)

        self.ollama_button = QPushButton("⟳  Настройки Ollama")
        self.ollama_button.setObjectName("topbar-ollama")
        self.ollama_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ollama_button.setProperty("variant", "toolbar")
        self.ollama_button.clicked.connect(self.ollama_clicked.emit)
        self.layout_root.addWidget(self.ollama_button)

        self.theme_button = QPushButton("◔  Тёмная тема")
        self.theme_button.setObjectName("topbar-theme")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setProperty("variant", "toolbar")
        self.theme_button.clicked.connect(self.theme_clicked.emit)
        self.layout_root.addWidget(self.theme_button)
        self._apply_responsive_layout()

    def set_theme_label(self, palette_name: str) -> None:
        self._palette_name = palette_name
        self._apply_responsive_layout()

    def refresh_theme(self) -> None:
        self.search_icon.setStyleSheet(f"font-size: 18px; color: {current_colors()['text_tertiary']};")

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self) -> None:
        compact = self.width() < 980
        dense = self.width() < 1160
        self.layout_root.setContentsMargins(20 if dense else 28, 16, 20 if dense else 28, 16)
        self.layout_root.setSpacing(10 if dense else 12)
        self.search_shell.setMinimumWidth(180 if compact else 220 if dense else 250)
        self.search_shell.setMaximumWidth(250 if compact else 300 if dense else 360)
        self.ollama_button.setText("⟳  Ollama" if dense else "⟳  Настройки Ollama")
        if self._palette_name == "light":
            self.theme_button.setText("◔  Тема" if dense else "◔  Тёмная тема")
        else:
            self.theme_button.setText("☼  Тема" if dense else "☼  Светлая тема")
