from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QPushButton, QWidget

from ui.icons import apply_button_icon


class TopBar(QWidget):
    settings_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.layout_root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.layout_root.setContentsMargins(28, 16, 28, 16)
        self.layout_root.setSpacing(12)

        self.layout_root.addStretch(1)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setObjectName("topbar-settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setProperty("variant", "toolbar")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        self.layout_root.addWidget(self.settings_button)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        apply_button_icon(self.settings_button, "settings")
