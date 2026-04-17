from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from ui.theme.spacing import ELEVATION, shadow_color
from ui.theme.palette import DARK


def apply_shadow(widget: QWidget, level: str, palette: dict) -> None:
    """Навесить тень одного из 3 уровней (sm/md/lg).

    palette — LIGHT или DARK словарь. Определяется по нему светлая/тёмная
    редакция shadow (warm brown vs pure black).
    """
    spec = ELEVATION[level]  # KeyError если уровень некорректный
    is_dark = palette["app_bg"] == DARK["app_bg"]
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(spec["blur"])
    effect.setOffset(QPointF(0, spec["dy"]))
    effect.setColor(shadow_color(is_dark, level))
    widget.setGraphicsEffect(effect)


def paint_folio(painter: QPainter, rect: QRectF, palette: dict,
                outer_radius: float = 10, inner_radius: float = 6,
                outer_pad: float = 8, accent: str = "rust") -> None:
    """Нарисовать folio-карточку: латунная outer-рамка + parchment inner
    + закладка 4×44 сверху цвета accent.

    Вызывать из CardFrame(role='folio').paintEvent(). ВАЖНО: painter
    должен быть создан на самом виджете (QPainter(self)); никаких
    QGraphicsEffect внутри этого метода — это регрессия QPainter warnings.
    """
    # Внешний слой (латунная рамка)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outer_fill = QColor(palette["border_strong"])
    painter.setBrush(QBrush(outer_fill))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, outer_radius, outer_radius)
    # Внутренняя бумага
    inner = rect.adjusted(outer_pad, outer_pad, -outer_pad, -outer_pad)
    painter.setBrush(QBrush(QColor(palette["parchment"])))
    painter.drawRoundedRect(inner, inner_radius, inner_radius)
    # Закладка сверху
    accent_color = QColor(palette.get(accent, palette["rust"]))
    strip_w, strip_h = 44.0, 4.0
    strip_x = rect.center().x() - strip_w / 2
    strip_y = rect.top()
    painter.setBrush(QBrush(accent_color))
    # Закруглённый внизу, плоский вверху (закладка)
    painter.drawRoundedRect(QRectF(strip_x, strip_y, strip_w, strip_h),
                            0, 0)


def paint_ornamental_divider(painter: QPainter, rect: QRectF,
                             palette: dict, dot_color: str = "brass",
                             line_color: str = "border") -> None:
    """Тонкая 1px линия цвета line_color с центральной точкой ⌀4 цвета
    dot_color. Используется в editorial-местах как разделитель секций.
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    mid_y = rect.center().y()
    # Линия
    pen = QPen(QColor(palette[line_color]))
    pen.setWidthF(1.0)
    painter.setPen(pen)
    painter.drawLine(QPointF(rect.left(), mid_y), QPointF(rect.right(), mid_y))
    # Точка посередине
    dot_r = 2.0
    cx = rect.center().x()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(palette[dot_color])))
    # Заливка фоном бумаги под точкой, чтобы линия разрывалась
    gap = 10.0
    painter.drawRect(QRectF(cx - gap / 2, mid_y - 1, gap, 2))
    painter.setBrush(QBrush(QColor(palette[dot_color])))
    painter.drawEllipse(QPointF(cx, mid_y), dot_r, dot_r)
