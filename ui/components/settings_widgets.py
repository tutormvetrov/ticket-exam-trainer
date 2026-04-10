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


class SettingsNavItem(ClickableFrame):
    selected = False
    clicked_key = Signal(str)

    def __init__(self, key: str, title: str, subtitle: str, icon_text: str, icon_bg: str) -> None:
        super().__init__(role="subtle-card", shadow=False)
        self.key = key
        self.setObjectName(f"settings-nav-{key}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        layout.addWidget(IconBadge(icon_text, icon_bg, "#4B5B72", size=32, radius=10, font_size=14))

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        title_label.setWordWrap(True)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("font-size: 12px; color: #6B7787;")
        subtitle_label.setWordWrap(True)
        text_box.addWidget(title_label)
        text_box.addWidget(subtitle_label)
        layout.addLayout(text_box, 1)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_key.emit(self.key)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        border = "#2E78E6" if selected else "#E4EAF2"
        background = "#EEF5FF" if selected else "#FFFFFF"
        self.setStyleSheet(
            f"QFrame#SettingsNavItem {{ background: {background}; border: 1px solid {border}; border-radius: 18px; }}"
        )


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
        bg = QColor("#1F6FEB") if self.isChecked() else QColor("#D7E1EE")
        knob_x = 24 if self.isChecked() else 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect(), 13, 13)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(knob_x, 4, 18, 18)


class SettingsToggleCard(CardFrame):
    def __init__(self, title: str, description: str, icon_text: str, accent: str, checked: bool, shadow_color) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color, shadow=False)
        self.setMinimumHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(IconBadge(icon_text, f"{accent}22", accent, size=40, radius=12, font_size=16))

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        description_label = QLabel(description)
        description_label.setProperty("role", "body")
        description_label.setWordWrap(True)
        text_box.addWidget(title_label)
        text_box.addWidget(description_label)
        layout.addLayout(text_box, 1)

        self.toggle = ToggleSwitch(checked)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        self.toggle.setObjectName(f"settings-toggle-{title.lower().replace(' ', '-').replace('/', '-')}")


class DiagnosticTile(CardFrame):
    def __init__(self, title: str, value: str, description: str, tone: str, shadow_color) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color, shadow=False)
        self.setObjectName("DiagnosticTile")
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
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #2B415C;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.value_label = QLabel()
        self.value_label.setProperty("skipTextAdmin", True)
        self.value_label.setStyleSheet("font-size: 16px; font-weight: 800; color: #1F2A3B;")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

        self.body_label = QLabel()
        self.body_label.setProperty("skipTextAdmin", True)
        self.body_label.setStyleSheet("font-size: 12px; color: #6B7787;")
        self.body_label.setWordWrap(True)
        self.body_label.setMaximumHeight(42)
        layout.addWidget(self.body_label)
        self.set_content(title, value, description, tone)

    def set_content(self, title: str, value: str, description: str, tone: str) -> None:
        colors = {
            "success": ("#EAF9F1", "#18B06A"),
            "info": ("#EEF5FF", "#2E78E6"),
            "warning": ("#FFF4E7", "#F59A23"),
            "neutral": ("#F4F7FB", "#7A8899"),
            "danger": ("#FFF0F2", "#D35469"),
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
            "success": "#BFEBCF",
            "info": "#CFE1FF",
            "warning": "#F7D39C",
            "neutral": "#DDE6F0",
            "danger": "#F2B9C5",
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
        self.label.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.label.setFixedWidth(label_width)
        layout.addWidget(self.label)

        plus = QPushButton("+")
        plus.setObjectName("number-stepper-plus")
        plus.setProperty("variant", "toolbar-ghost")
        plus.setFixedWidth(42)
        plus.clicked.connect(lambda: self._set_value(self._value + self._step))
        layout.addWidget(plus)

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._set_value(value)

    def _set_value(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, value))
        self.label.setText(str(self._value))
        self.value_changed.emit(self._value)
