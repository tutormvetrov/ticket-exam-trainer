from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QSize
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import apply_shadow


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

        gradient = QLinearGradient(8, 8, self.width() - 8, self.height() - 8)
        gradient.setColorAt(0.0, QColor("#03C77E"))
        gradient.setColorAt(1.0, QColor("#6CF6B8"))

        def draw_slice(top: float, left: float, right: float, height: float, trim: float) -> None:
            path = QPainterPath()
            path.moveTo(left, top + height)
            path.quadTo(left + 12, top + height - 12, left + 24, top)
            path.lineTo(right - trim, top + height * 0.38)
            path.quadTo(right + 2, top + height * 0.54, right - 2, top + height)
            path.lineTo(left, top + height)
            path.closeSubpath()
            painter.drawPath(path)

        painter.setBrush(gradient)
        draw_slice(7, 8, 42, 26, 2)
        draw_slice(23, 15, 46, 19, 4)
        draw_slice(35, 22, 48, 13, 5)

        cut_pen = QPen(QColor("#FFFFFF"), 4.2)
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
        self.setFixedSize(size, size)
        self.setStyleSheet(
            f"QFrame {{ background: {bg_color}; border-radius: {radius}px; }}"
            f"QLabel {{ color: {fg_color}; font-size: {font_size}px; font-weight: 700; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


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
        self.text_label.setStyleSheet(
            f"font-size: {10 if compact else 11}px; color: #5F6B7A; font-weight: 600; line-height: 1.2;"
        )
        layout.addWidget(self.text_label)
        self.badge: IconBadge | None = None
        self.set_content(icon_text, value, label_text, tone)

    def set_content(self, icon_text: str, value: str, label_text: str, tone: str) -> None:
        tones = {
            "blue": ("#EEF5FF", "#2E78E6"),
            "orange": ("#FFF5EA", "#F59A23"),
            "slate": ("#F1F4F8", "#8FA0B4"),
            "green": ("#EAF9F1", "#18B06A"),
        }
        bg, fg = tones.get(tone, tones["blue"])
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


class ScoreBadge(QLabel):
    def __init__(self, value: int, tone: str) -> None:
        super().__init__(f"{value}%")
        styles = {
            "success": ("#DFF5E8", "#2A9D68"),
            "warning": ("#FFF1DF", "#E98B19"),
            "danger": ("#FFE4E8", "#D35469"),
        }
        bg, fg = styles.get(tone, styles["success"])
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

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        diameter = min(self.diameter, max(64, min(self.width() - 28, self.height() - 44)))
        left = (self.width() - diameter) / 2
        top = 12
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

        painter.setPen(QColor("#1F2A3B"))
        painter.setFont(QFont("Segoe UI", max(14, int(round(diameter * 0.19))), 800))
        painter.drawText(QRectF(left, top + diameter * 0.18, diameter, diameter * 0.28), Qt.AlignmentFlag.AlignCenter, f"{self.percent}%")

        painter.setPen(QColor("#7B8794"))
        painter.setFont(QFont("Segoe UI", max(8, int(round(diameter * 0.09)))))
        painter.drawText(
            QRectF(left, top + diameter * 0.45, diameter, diameter * 0.36),
            Qt.AlignmentFlag.AlignCenter,
            "Средний\nрезультат",
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
            value.setStyleSheet("font-size: 14px; font-weight: 600;")
            layout.addWidget(value, index, 1)
