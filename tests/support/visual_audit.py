from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QWidget


def label_text_fits(label: QLabel, *, tolerance: int = 4) -> bool:
    if not label.isVisible():
        return True
    text = (label.text() or "").strip()
    if not text:
        return True
    rect = label.contentsRect()
    if rect.width() <= 0 or rect.height() <= 0:
        return True
    if label.wordWrap() and label.hasHeightForWidth():
        return label.heightForWidth(rect.width()) <= rect.height() + tolerance
    line_width = max((label.fontMetrics().horizontalAdvance(line) for line in text.splitlines() if line), default=0)
    return line_width <= rect.width() + tolerance


def button_text_fits(button: QPushButton, *, tolerance: int = 4) -> bool:
    if not button.isVisible():
        return True
    if button.property("variant") == "tab":
        return True
    text = (button.text() or "").strip()
    if not text:
        return True
    rect = button.contentsRect()
    if rect.width() <= 0 or rect.height() <= 0:
        return True
    return button.fontMetrics().horizontalAdvance(text) <= rect.width() + tolerance


def collect_text_clipping_issues(root: QWidget) -> list[str]:
    issues: list[str] = []

    for label in root.findChildren(QLabel):
        text = (label.text() or "").strip()
        if not label_text_fits(label):
            issues.append(f"label:{label.objectName() or text[:32]}")

    for button in root.findChildren(QPushButton):
        text = (button.text() or "").strip()
        if not button_text_fits(button):
            issues.append(f"button:{button.objectName() or text[:32]}")

    return issues


def collect_click_target_issues(root: QWidget, *, min_height: int = 32, min_width: int = 72) -> list[str]:
    issues: list[str] = []
    for button in root.findChildren(QPushButton):
        if not button.isVisible():
            continue
        if button.property("variant") == "tab":
            continue
        if button.height() < min_height or button.width() < min_width:
            issues.append(f"{button.objectName() or button.text()}: {button.width()}x{button.height()}")
    return issues
