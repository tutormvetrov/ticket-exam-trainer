from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.common import CardFrame, ClickableFrame, IconBadge
from ui.theme import alpha_color, current_colors, is_dark_palette


class SettingsNavItem(ClickableFrame):
    selected = False
    clicked_key = Signal(str)

    def __init__(self, key: str, title: str, subtitle: str, icon_text: str, icon_bg: str) -> None:
        super().__init__(role="subtle-card", shadow=False)
        self.key = key
        self.icon_bg = icon_bg
        self.setObjectName(f"settings-nav-{key}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        self.badge = IconBadge(icon_text, icon_bg, current_colors()["text_secondary"], size=32, radius=10, font_size=14)
        layout.addWidget(self.badge)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setWordWrap(True)
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.subtitle_label)
        layout.addLayout(text_box, 1)
        self.set_selected(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_key.emit(self.key)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        colors = current_colors()
        border = colors["primary"] if selected else colors["border"]
        background = colors["primary_soft"] if selected else colors["card_bg"]
        self.setStyleSheet(
            f"QFrame#SettingsNavItem {{ background: {background}; border: 1px solid {border}; border-radius: 18px; }}"
        )
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        self.subtitle_label.setStyleSheet(f"font-size: 12px; color: {colors['text_secondary']};")
        self.badge.set_colors(self.icon_bg, colors["text_secondary"])

    def refresh_theme(self) -> None:
        self.set_selected(self.selected)


class SettingsNavPanel(CardFrame):
    section_changed = Signal(str)

    def __init__(self, sections: list[tuple[str, str, str, str, str]], shadow_color) -> None:
        super().__init__(role="card", shadow_color=shadow_color)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.items: dict[str, SettingsNavItem] = {}

        for key, title, subtitle, icon_text, icon_bg in sections:
            item = SettingsNavItem(key, title, subtitle, icon_text, icon_bg)
            item.clicked_key.connect(self._emit_change)
            self.items[key] = item
            layout.addWidget(item)

        self.set_current("ollama")

    def _emit_change(self, key: str) -> None:
        self.set_current(key)
        self.section_changed.emit(key)

    def set_current(self, key: str) -> None:
        for item_key, item in self.items.items():
            item.set_selected(item_key == key)

    def refresh_theme(self) -> None:
        for item in self.items.values():
            item.refresh_theme()


class ToggleSwitch(QPushButton):
    toggled_value = Signal(bool)

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setObjectName("settings-toggle-switch")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 26)
        self.clicked.connect(lambda checked=False: self.toggled_value.emit(bool(checked)))
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = current_colors()
        bg = QColor(colors["primary"] if self.isChecked() else colors["border_strong"])
        knob_x = 24 if self.isChecked() else 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect(), 13, 13)
        painter.setBrush(QColor(colors["card_bg"]))
        painter.drawEllipse(knob_x, 4, 18, 18)

    def refresh_theme(self) -> None:
        self.update()


class SettingsToggleCard(CardFrame):
    def __init__(self, title: str, description: str, icon_text: str, accent: str, checked: bool, shadow_color) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color, shadow=False)
        self.accent = accent
        self.setMinimumHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        self.badge = IconBadge(icon_text, alpha_color(accent, 0.14), accent, size=40, radius=12, font_size=16)
        layout.addWidget(self.badge)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        self.title_label = QLabel(title)
        self.description_label = QLabel(description)
        self.description_label.setProperty("role", "body")
        self.description_label.setWordWrap(True)
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.description_label)
        layout.addLayout(text_box, 1)

        self.toggle = ToggleSwitch(checked)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        self.toggle.setObjectName(f"settings-toggle-{title.lower().replace(' ', '-').replace('/', '-')}")
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.badge.set_colors(alpha_color(self.accent, 0.22 if is_dark_palette() else 0.14), self.accent)
        self.title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {colors['text']};")
        self.toggle.refresh_theme()


class DiagnosticTile(CardFrame):
    def __init__(self, title: str, value: str, description: str, tone: str, shadow_color) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color, shadow=False)
        self.setObjectName("DiagnosticTile")
        self._title = title
        self._value = value
        self._description = description
        self._tone = tone
        self.setMinimumHeight(122)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.badge_shell = QWidget()
        self.badge_shell.setFixedHeight(28)
        self.badge_holder = QHBoxLayout(self.badge_shell)
        self.badge_holder.setContentsMargins(0, 0, 0, 0)
        self.badge_holder.setSpacing(0)
        layout.addWidget(self.badge_shell)

        self.title_label = QLabel()
        self.title_label.setProperty("skipTextAdmin", True)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.value_label = QLabel()
        self.value_label.setProperty("skipTextAdmin", True)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

        self.body_label = QLabel()
        self.body_label.setProperty("skipTextAdmin", True)
        self.body_label.setWordWrap(True)
        self.body_label.setMaximumHeight(42)
        layout.addWidget(self.body_label)
        self.set_content(title, value, description, tone)

    def set_content(self, title: str, value: str, description: str, tone: str) -> None:
        self._title = title
        self._value = value
        self._description = description
        self._tone = tone
        palette = current_colors()
        colors = {
            "success": (palette["success_soft"], palette["success"]),
            "info": (palette["primary_soft"], palette["primary"]),
            "warning": (palette["warning_soft"], palette["warning"]),
            "neutral": (palette["card_muted"], palette["text_tertiary"]),
            "danger": (palette["danger_soft"], palette["danger"]),
        }
        icons = {
            "success": "OK",
            "info": "i",
            "warning": "!",
            "neutral": "...",
            "danger": "ER",
        }
        bg, fg = colors[tone]
        border = {
            "success": palette["success"],
            "info": palette["primary"],
            "warning": palette["warning"],
            "neutral": palette["border_strong"],
            "danger": palette["danger"],
        }[tone]
        self.setStyleSheet(f"QFrame#DiagnosticTile {{ background: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.badge_holder.addWidget(IconBadge(icons[tone], bg, fg, size=28, radius=10, font_size=10), 0, Qt.AlignmentFlag.AlignLeft)
        self.title_label.setText(title)
        self.value_label.setText(value)
        self.body_label.setText(description)
        self.title_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {palette['text_secondary']};")
        self.value_label.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {palette['text']};")
        self.body_label.setStyleSheet(f"font-size: 12px; color: {palette['text_secondary']};")

    def refresh_theme(self) -> None:
        self.set_content(self._title, self._value, self._description, self._tone)


class NumberStepper(QFrame):
    value_changed = Signal(int)

    def __init__(
        self,
        value: int = 60,
        *,
        minimum: int = 5,
        maximum: int = 300,
        step: int = 5,
        label_width: int = 74,
    ) -> None:
        super().__init__()
        self._value = value
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self.setProperty("role", "subtle-card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        minus = QPushButton("\u2212")
        minus.setObjectName("number-stepper-minus")
        minus.setProperty("variant", "toolbar-ghost")
        minus.setFixedWidth(42)
        minus.clicked.connect(lambda: self._set_value(self._value - self._step))
        layout.addWidget(minus)

        self.label = QLabel(str(self._value))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedWidth(label_width)
        layout.addWidget(self.label)

        plus = QPushButton("+")
        plus.setObjectName("number-stepper-plus")
        plus.setProperty("variant", "toolbar-ghost")
        plus.setFixedWidth(42)
        plus.clicked.connect(lambda: self._set_value(self._value + self._step))
        layout.addWidget(plus)
        self.refresh_theme()

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._set_value(value)

    def _set_value(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, value))
        self.label.setText(str(self._value))
        self.value_changed.emit(self._value)

    def refresh_theme(self) -> None:
        self.label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
