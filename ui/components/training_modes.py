from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from domain.models import TrainingModeData
from ui.components.common import CardFrame, ClickableFrame, IconBadge
from ui.theme import alpha_color, current_colors, is_dark_palette


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
        self.badge = IconBadge(mode.icon_text, alpha_color(mode.border, 0.18 if is_dark_palette() else 0.14), "#FFFFFF", size=40, radius=12, font_size=15)
        layout.addWidget(self.badge)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        self.title_label = QLabel(mode.title)
        self.description_label = QLabel(mode.description)
        self.description_label.setWordWrap(True)
        self.description_label.setProperty("role", "body")
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.description_label)
        layout.addLayout(text_box, 1)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        colors = current_colors()
        border = self.mode.border if not selected else colors["primary"]
        background = alpha_color(self.mode.border, 0.12 if is_dark_palette() else 0.08) if not selected else colors["primary_soft"]
        self.setStyleSheet(
            f"QFrame#TrainingModeCard {{ background: {background}; border: 2px solid {border}; border-radius: 16px; }}"
        )
        self.title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {colors['text']};")
        self.badge.set_colors(alpha_color(self.mode.border, 0.18 if is_dark_palette() else 0.14), "#FFFFFF")

    def refresh_theme(self) -> None:
        self.set_selected(self._selected)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_mode.emit(self.mode.key)
        super().mousePressEvent(event)


class TrainingModesPanel(CardFrame):
    mode_selected = Signal(str)

    def __init__(self, modes: list[TrainingModeData], shadow_color, *, show_header: bool = True) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        self.modes = modes[:]
        self.shadow_color = shadow_color
        self.cards: dict[str, TrainingModeCard] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        if show_header:
            title = QLabel("Режим тренировки")
            title.setProperty("role", "section-title")
            subtitle = QLabel("Выберите способ изучения материала")
            subtitle.setProperty("role", "body")
            layout.addWidget(title)
            layout.addWidget(subtitle)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        for mode in modes:
            card = TrainingModeCard(mode, shadow_color)
            card.clicked_mode.connect(self.mode_selected.emit)
            self.cards[mode.key] = card
        layout.addLayout(self.grid)
        self._reflow_cards()

    def set_selected_mode(self, mode_key: str) -> None:
        for key, card in self.cards.items():
            card.set_selected(key == mode_key)

    def refresh_theme(self) -> None:
        for card in self.cards.values():
            card.refresh_theme()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._reflow_cards()
        super().resizeEvent(event)

    def _reflow_cards(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self.grid.removeWidget(widget)
        width = max(1, self.width())
        columns = 1 if width < 760 else 2 if width < 1080 else 3
        for index, mode in enumerate(self.modes):
            card = self.cards[mode.key]
            self.grid.addWidget(card, index // columns, index % columns)
