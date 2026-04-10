from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from app.platform import is_macos
from ui.components.common import LogoMark


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
        icon.setToolTip("Тренажёр билетов к вузовским экзаменам")
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
        button.setStyleSheet(
            "QPushButton { border: none; border-radius: 8px; background: transparent; font-size: 16px; }"
            "QPushButton:hover { background: #EEF3F8; }"
        )
        return button

    def _toggle_maximize(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()
