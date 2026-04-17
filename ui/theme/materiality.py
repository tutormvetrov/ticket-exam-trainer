from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_shadow(widget: QWidget, color: QColor, blur: int = 28, y_offset: int = 5) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(QPointF(0, y_offset))
    effect.setColor(color)
    widget.setGraphicsEffect(effect)
