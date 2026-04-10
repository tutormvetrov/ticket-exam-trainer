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
        self._selected = False
        self.setObjectName(f"training-mode-{mode.key}")
        self.setFixedHeight(92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        border = self.mode.border if not selected else "#2F6FEB"
        background = self.mode.tint if not selected else "#EEF5FF"
        self.setStyleSheet(
            f"QFrame#TrainingModeCard {{ background: {background}; border: 2px solid {border}; border-radius: 16px; }}"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_mode.emit(self.mode.key)
        super().mousePressEvent(event)


class TrainingModesPanel(CardFrame):
    mode_selected = Signal(str)

    def __init__(self, modes: list[TrainingModeData], shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        self.cards: dict[str, TrainingModeCard] = {}
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
            self.cards[mode.key] = card
        layout.addLayout(grid)

    def set_selected_mode(self, mode_key: str) -> None:
        for key, card in self.cards.items():
            card.set_selected(key == mode_key)
