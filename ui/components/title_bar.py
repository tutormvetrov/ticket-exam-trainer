from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from app.platform import is_macos
from ui.components.common import LogoMark
from ui.theme import alpha_color, current_colors


class AppTitleBar(QFrame):
    def __init__(self, window: QWidget) -> None:
        super().__init__()
        self.window = window
        self.setProperty("role", "titlebar")
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 12, 6)
        layout.setSpacing(8)

        icon = LogoMark(24)
        icon.setToolTip("Тезис")
        layout.addWidget(icon)
        layout.addStretch(1)

        if not is_macos():
            self.min_button = self._window_button("−")
            self.min_button.clicked.connect(self.window.showMinimized)
            layout.addWidget(self.min_button)

            self.max_button = self._window_button("□")
            self.max_button.clicked.connect(self._toggle_maximize)
            layout.addWidget(self.max_button)

            self.close_button = self._window_button("×")
            self.close_button.clicked.connect(self.window.close)
            layout.addWidget(self.close_button)

    def _window_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setFixedSize(34, 26)
        self._apply_window_button_theme(button)
        return button

    def _apply_window_button_theme(self, button: QPushButton) -> None:
        colors = current_colors()
        button.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 8px; background: transparent; font-size: 16px; color: {colors['text_secondary']}; }}"
            f"QPushButton:hover {{ background: {alpha_color(colors['text'], 0.08)}; color: {colors['text']}; }}"
        )

    def _toggle_maximize(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def refresh_theme(self) -> None:
        if not is_macos():
            for button in (self.min_button, self.max_button, self.close_button):
                self._apply_window_button_theme(button)
