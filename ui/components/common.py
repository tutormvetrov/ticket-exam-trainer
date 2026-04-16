from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QRectF, Signal, QSize, QEasingCurve, Property, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.icons import SvgIconLabel
from ui.theme import alpha_color, apply_shadow, current_colors, is_dark_palette


def tone_pair(tone: str) -> tuple[str, str]:
    colors = current_colors()
    mapping = {
        "primary": (colors["primary_soft"], colors["primary"]),
        "blue": (colors["primary_soft"], colors["primary"]),
        "success": (colors["success_soft"], colors["success"]),
        "green": (colors["success_soft"], colors["success"]),
        "warning": (colors["warning_soft"], colors["warning"]),
        "orange": (colors["warning_soft"], colors["warning"]),
        "danger": (colors["danger_soft"], colors["danger"]),
        "red": (colors["danger_soft"], colors["danger"]),
        "violet": (colors["violet_soft"], "#A78BFA" if is_dark_palette() else "#7C3AED"),
        "cyan": (colors["cyan_soft"], "#5CD6EE" if is_dark_palette() else "#0F766E"),
        "slate": (colors["card_muted"], colors["text_secondary"]),
    }
    return mapping.get(tone, mapping["primary"])


def file_badge_colors(file_type: str) -> tuple[str, str]:
    normalized = (file_type or "").strip().upper()
    if normalized == "DOCX":
        return tone_pair("primary")
    if normalized == "PDF":
        return tone_pair("danger")
    if normalized in {"AI", "TXT", "MD"}:
        return tone_pair("success")
    if normalized in {"PM", "DLC"}:
        return tone_pair("violet")
    if normalized == "PPTX":
        return tone_pair("warning")
    return tone_pair("slate")


class CardFrame(QFrame):
    def __init__(self, role: str = "card", shadow_color: QColor | None = None, shadow: bool = True) -> None:
        super().__init__()
        self.setProperty("role", role)
        if shadow and shadow_color is not None:
            apply_shadow(self, shadow_color)


class LogoMark(QWidget):
    def __init__(self, size: int = 52) -> None:
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        colors = current_colors()
        gradient = QLinearGradient(8, 8, self.width() - 8, self.height() - 8)
        if is_dark_palette():
            gradient.setColorAt(0.0, QColor("#0A8C65"))
            gradient.setColorAt(0.55, QColor("#23D18B"))
            gradient.setColorAt(1.0, QColor("#88F2C2"))
        else:
            gradient.setColorAt(0.0, QColor("#047857"))
            gradient.setColorAt(0.55, QColor("#10B981"))
            gradient.setColorAt(1.0, QColor("#6EE7B7"))

        def draw_slice(top: float, left: float, right: float, height: float, trim: float) -> None:
            path = QPainterPath()
            path.moveTo(left, top + height)
            path.quadTo(left + 12, top + height - 12, left + 24, top)
            path.lineTo(right - trim, top + height * 0.38)
            path.quadTo(right + 2, top + height * 0.54, right - 2, top + height)
            path.lineTo(left, top + height)
            path.closeSubpath()
            painter.drawPath(path)

        glow_pen = QPen(QColor("#23D18B" if is_dark_palette() else "#0F9F6E"), 1.8)
        glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow_pen)
        painter.setBrush(gradient)
        draw_slice(7, 8, 42, 26, 2)
        draw_slice(23, 15, 46, 19, 4)
        draw_slice(35, 22, 48, 13, 5)

        cut_pen = QPen(QColor(colors["card_bg"] if is_dark_palette() else "#ECFFF7"), 4.0)
        cut_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(cut_pen)
        painter.drawArc(QRectF(10, 11, 34, 24), 210 * 16, -70 * 16)
        painter.drawArc(QRectF(17, 25, 28, 18), 205 * 16, -72 * 16)


class IconBadge(QFrame):
    def __init__(
        self,
        text: str,
        bg_color: str,
        fg_color: str = "#1F2A3B",
        size: int = 44,
        radius: int = 14,
        font_size: int = 10,
    ) -> None:
        super().__init__()
        self._bg_color = bg_color
        self._fg_color = fg_color
        self._radius = radius
        self._font_size = font_size
        self.setFixedSize(size, size)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.refresh_theme()

    def set_colors(self, bg_color: str, fg_color: str) -> None:
        self._bg_color = bg_color
        self._fg_color = fg_color
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(
            f"QFrame {{ background: {self._bg_color}; border-radius: {self._radius}px; }}"
            f"QLabel {{ color: {self._fg_color}; font-size: {self._font_size}px; font-weight: 700; }}"
        )


class StatusDot(QFrame):
    def __init__(self, text: str, color: str = "#18B06A") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        label = QLabel(text)
        label.setProperty("role", "status-ok")
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)


class MetricTile(CardFrame):
    def __init__(
        self,
        icon_text: str,
        value: str,
        label_text: str,
        tone: str,
        shadow_color: QColor,
        compact: bool = False,
    ) -> None:
        super().__init__(role="subtle-card", shadow_color=shadow_color)
        self.compact = compact
        self.tone = tone
        self._icon_text = icon_text
        self._value = value
        self._label_text = label_text
        self.setMinimumHeight(54 if compact else 64)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10 if compact else 12, 8 if compact else 10, 10 if compact else 12, 8 if compact else 10)
        layout.setSpacing(4 if compact else 6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.badge_shell = QWidget()
        self.badge_shell.setFixedSize(20 if compact else 22, 20 if compact else 22)
        self.badge_holder = QHBoxLayout(self.badge_shell)
        self.badge_holder.setContentsMargins(0, 0, 0, 0)
        self.badge_holder.setSpacing(0)
        top_row.addWidget(self.badge_shell, 0, Qt.AlignmentFlag.AlignVCenter)

        self.value_label = QLabel()
        self.value_label.setStyleSheet(f"font-size: {16 if compact else 18}px; font-weight: 800;")
        top_row.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(f"font-size: {10 if compact else 11}px; font-weight: 600; line-height: 1.2;")
        layout.addWidget(self.text_label)
        self.badge: IconBadge | None = None
        self.set_content(icon_text, value, label_text, tone)

    def set_content(self, icon_text: str, value: str, label_text: str, tone: str) -> None:
        self._icon_text = icon_text
        self._value = value
        self._label_text = label_text
        colors = current_colors()
        self.tone = tone
        bg, fg = tone_pair(tone)
        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        badge_size = 20 if self.compact else 22
        self.badge = IconBadge(icon_text, bg, fg, size=badge_size, radius=7, font_size=8 if self.compact else 9)
        self.badge_holder.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.value_label.setText(value)
        self.text_label.setText(label_text)
        self.value_label.setStyleSheet(f"font-size: {16 if self.compact else 18}px; font-weight: 800; color: {colors['text']};")
        self.text_label.setStyleSheet(
            f"font-size: {10 if self.compact else 11}px; color: {colors['text_secondary']}; font-weight: 600; line-height: 1.2;"
        )

    def refresh_theme(self) -> None:
        self.set_content(self._icon_text, self._value, self._label_text, self.tone)


class ScoreBadge(QLabel):
    def __init__(self, value: int, tone: str) -> None:
        super().__init__(f"{value}%")
        bg, fg = tone_pair(tone)
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 12px; padding: 7px 10px; font-size: 13px; font-weight: 700;"
        )


class DonutChart(QWidget):
    def __init__(self, percent: int, accent: str = "#18B06A", track: str = "#E6EEF6", diameter: int = 96) -> None:
        super().__init__()
        self.percent = percent
        self.accent = QColor(accent)
        self.track = QColor(track)
        self.diameter = diameter
        self.setMinimumSize(diameter + 36, diameter + 54)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.diameter + 44, self.diameter + 56)

    def set_percent(self, percent: int) -> None:
        self.percent = max(0, min(100, int(percent)))
        self.update()

    def animate_to(self, percent: int) -> None:
        target = max(0, min(100, int(percent)))
        if not hasattr(self, "_animation"):
            self._animation = QPropertyAnimation(self, b"animatedPercent", self)
            self._animation.setDuration(800)
            self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.stop()
        self._animation.setStartValue(self.percent)
        self._animation.setEndValue(target)
        self._animation.start()

    def get_animated_percent(self) -> int:
        return self.percent

    def set_animated_percent(self, value: int) -> None:
        self.percent = max(0, min(100, int(value)))
        self._update_accent_for_percent()
        self.update()

    animatedPercent = Property(int, get_animated_percent, set_animated_percent)

    def _update_accent_for_percent(self) -> None:
        if self.percent <= 30:
            self.accent = QColor("#EF5350")
        elif self.percent <= 60:
            self.accent = QColor("#FFA726")
        elif self.percent <= 80:
            self.accent = QColor("#FFEE58")
        else:
            self.accent = QColor("#66BB6A")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = current_colors()

        diameter = min(self.diameter, max(64, min(self.width() - 28, self.height() - 54)))
        left = (self.width() - diameter) / 2
        top = 8
        rect = QRectF(left, top, diameter, diameter)

        stroke = max(8, int(round(diameter * 0.11)))
        pen = QPen(self.track, stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        accent_pen = QPen(self.accent, stroke)
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(accent_pen)
        span = int(-360 * 16 * (self.percent / 100))
        painter.drawArc(rect, 90 * 16, span)

        painter.setPen(QColor(colors["text"]))
        painter.setFont(QFont(QApplication.font().family(), max(15, int(round(diameter * 0.24))), 800))
        painter.drawText(
            QRectF(left, top + diameter * 0.26, diameter, diameter * 0.22),
            Qt.AlignmentFlag.AlignCenter,
            f"{self.percent}%",
        )

        painter.setPen(QColor(colors["text_secondary"]))
        painter.setFont(QFont(QApplication.font().family(), max(9, int(round(diameter * 0.11))), 600))
        painter.drawText(
            QRectF(0, top + diameter + 6, self.width(), 28),
            Qt.AlignmentFlag.AlignCenter,
            "Средний результат",
        )


class ClickableFrame(CardFrame):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class TwoColumnRows(QWidget):
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        for index, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text)
            label.setProperty("role", "body")
            layout.addWidget(label, index, 0)
            value = QLabel(value_text)
            value.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {current_colors()['text']};")
            layout.addWidget(value, index, 1)


class EmptyStatePanel(CardFrame):
    def __init__(
        self,
        icon_name: str,
        title_text: str,
        body_text: str,
        *,
        shadow_color: QColor | None = None,
        role: str = "subtle-card",
        primary_action: tuple[str, Callable[[], None], str, str | None] | None = None,
        secondary_action: tuple[str, Callable[[], None], str, str | None] | None = None,
    ) -> None:
        super().__init__(role=role, shadow_color=shadow_color, shadow=shadow_color is not None and role == "card")
        self._icon_name = icon_name
        self._primary_handler = lambda: None
        self._secondary_handler = lambda: None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.icon_shell = QFrame()
        self.icon_shell.setProperty("role", "empty-icon-shell")
        self.icon_shell.setFixedSize(64, 64)
        icon_layout = QVBoxLayout(self.icon_shell)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = SvgIconLabel(icon_name, size=28, tone="primary")
        icon_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_shell, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel(title_text)
        self.title_label.setProperty("role", "section-title")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body_label = QLabel(body_text)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

        self.actions_row = QHBoxLayout()
        self.actions_row.setContentsMargins(0, 0, 0, 0)
        self.actions_row.setSpacing(10)

        self.primary_button = QPushButton()
        self.primary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.primary_button.clicked.connect(self._trigger_primary)
        self.actions_row.addWidget(self.primary_button)

        self.secondary_button = QPushButton()
        self.secondary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.secondary_button.clicked.connect(self._trigger_secondary)
        self.actions_row.addWidget(self.secondary_button)
        self.actions_row.addStretch(1)
        layout.addLayout(self.actions_row)
        layout.addStretch(1)

        self.set_content(icon_name, title_text, body_text, primary_action=primary_action, secondary_action=secondary_action)

    def set_content(
        self,
        icon_name: str,
        title_text: str,
        body_text: str,
        *,
        primary_action: tuple[str, Callable[[], None], str, str | None] | None = None,
        secondary_action: tuple[str, Callable[[], None], str, str | None] | None = None,
    ) -> None:
        self._icon_name = icon_name
        self.icon_label.set_icon(icon_name, tone="primary")
        self.title_label.setText(title_text)
        self.body_label.setText(body_text)
        self._configure_button(self.primary_button, primary_action, "_primary_handler")
        self._configure_button(self.secondary_button, secondary_action, "_secondary_handler")

    def _configure_button(
        self,
        button: QPushButton,
        config: tuple[str, Callable[[], None], str, str | None] | None,
        handler_attr: str,
    ) -> None:
        from ui.icons import apply_button_icon

        if config is None:
            button.hide()
            button.setProperty("iconName", "")
            setattr(self, handler_attr, lambda: None)
            return
        text, action, variant, icon_name = config
        setattr(self, handler_attr, action)
        button.show()
        button.setText(text)
        button.setProperty("variant", variant)
        button.setProperty("iconName", icon_name or "")
        if icon_name:
            apply_button_icon(button, icon_name)
        else:
            button.setIcon(QIcon())
        button.style().unpolish(button)
        button.style().polish(button)

    def _trigger_primary(self) -> None:
        self._primary_handler()

    def _trigger_secondary(self) -> None:
        self._secondary_handler()

    def refresh_theme(self) -> None:
        self.icon_label.set_icon(self._icon_name, tone="primary")
        from ui.icons import apply_button_icon

        for button in (self.primary_button, self.secondary_button):
            if button.isHidden():
                continue
            icon_name = str(button.property("iconName") or "").strip()
            if icon_name:
                apply_button_icon(button, icon_name)
            button.style().unpolish(button)
            button.style().polish(button)
