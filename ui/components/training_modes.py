from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from domain.models import TrainingModeData
from ui.components.common import CardFrame, ClickableFrame, IconBadge


class TrainingModeCard(ClickableFrame):
    clicked_mode = Signal(str)

    def __init__(self, mode: TrainingModeData, shadow_color) -> None:
        super().__init__(role="mode-card", shadow_color=shadow_color)
        self.mode = mode
        self.setObjectName(f"training-mode-{mode.key}")
        self.setFixedHeight(92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#TrainingModeCard {{ background: {mode.tint}; border: 1px solid {mode.border}; border-radius: 16px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(IconBadge(mode.icon_text, mode.border, "#FFFFFF", size=40, radius=12, font_size=15))

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        title = QLabel(mode.title)
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        description = QLabel(mode.description)
        description.setWordWrap(True)
        description.setProperty("role", "body")
        text_box.addWidget(title)
        text_box.addWidget(description)
        layout.addLayout(text_box, 1)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_mode.emit(self.mode.key)
        super().mousePressEvent(event)


class TrainingModesPanel(CardFrame):
    mode_selected = Signal(str)

    def __init__(self, modes: list[TrainingModeData], shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("Режим тренировки")
        title.setProperty("role", "section-title")
        subtitle = QLabel("Выберите способ изучения материала")
        subtitle.setProperty("role", "body")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, mode in enumerate(modes):
            card = TrainingModeCard(mode, shadow_color)
            card.clicked_mode.connect(self.mode_selected.emit)
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
