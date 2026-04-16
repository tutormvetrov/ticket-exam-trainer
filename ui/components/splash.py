from __future__ import annotations

from app.build_info import RuntimeBuildInfo
from ui.components.common import CardFrame, LogoMark

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class BrandedSplash(QWidget):
    def __init__(self, build_info: RuntimeBuildInfo) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("tezis-splash")
        self.setFixedSize(540, 300)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        shell = CardFrame(role="card", shadow_color=None, shadow=False)
        shell.setObjectName("tezis-splash-shell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(28, 28, 28, 28)
        shell_layout.setSpacing(22)

        shell_layout.addWidget(LogoMark(88), 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(8)

        eyebrow = QLabel("LOCAL EXAM ENGINE")
        eyebrow.setProperty("role", "nav-caption")
        text_col.addWidget(eyebrow)

        title = QLabel("Тезис")
        title.setProperty("role", "hero")
        text_col.addWidget(title)

        subtitle = QLabel("Локальный тренажёр билетов, карт знаний и репетиции ответа.")
        subtitle.setProperty("role", "page-subtitle")
        subtitle.setWordWrap(True)
        text_col.addWidget(subtitle)

        version_label = QLabel(build_info.release_label)
        version_label.setProperty("role", "section-title")
        text_col.addWidget(version_label)

        built_label = QLabel(f"Сборка: {build_info.built_at_label}")
        built_label.setProperty("role", "muted")
        text_col.addWidget(built_label)

        text_col.addStretch(1)
        shell_layout.addLayout(text_col, 1)
        root.addWidget(shell)

    def center_on_screen(self, screen) -> None:
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(geometry.center() - self.rect().center())
