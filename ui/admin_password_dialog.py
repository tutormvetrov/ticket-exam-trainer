from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from application.admin_access import AdminAccessState, AdminAccessStore
from ui.components.common import CardFrame, IconBadge, file_badge_colors, tone_pair


class AdminPasswordDialog(QDialog):
    def __init__(self, store: AdminAccessStore, workspace_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.workspace_root = workspace_root
        self.setWindowTitle("Настройка админ-пароля")
        self.setModal(True)
        self.resize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = CardFrame(role="card", shadow=False)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(14)
        adm_bg, adm_fg = file_badge_colors("DOCX")
        header_layout.addWidget(IconBadge("ADM", adm_bg, adm_fg, size=44, radius=14, font_size=11), 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(4)
        title = QLabel("Локальный доступ к админ-функциям")
        title.setProperty("role", "section-title")
        header_text.addWidget(title)

        body = QLabel(
            "Здесь задаётся пароль для входа в режим администратора. После входа становятся доступны отладка "
            "интерфейса и редактор подписей."
        )
        body.setProperty("role", "body")
        body.setWordWrap(True)
        header_text.addWidget(body)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        header_text.addWidget(self.status_label)
        header_layout.addLayout(header_text, 1)
        root.addWidget(header)

        form_card = CardFrame(role="card", shadow=False)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(14)

        form_title = QLabel("Новый пароль")
        form_title.setProperty("role", "section-title")
        form_layout.addWidget(form_title)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        form_layout.addWidget(self.message_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Введите новый админ-пароль")
        self.password_input.setProperty("role", "form-input")
        form.addRow("Пароль", self.password_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Повторите пароль")
        self.confirm_input.setProperty("role", "form-input")
        form.addRow("Повтор", self.confirm_input)

        self.hint_input = QLineEdit()
        self.hint_input.setPlaceholderText("Короткая подсказка, если она нужна")
        self.hint_input.setProperty("role", "form-input")
        form.addRow("Подсказка", self.hint_input)
        form_layout.addLayout(form)

        helper_row = QHBoxLayout()
        helper_row.setContentsMargins(0, 0, 0, 0)
        helper_row.setSpacing(10)

        self.show_passwords_button = QPushButton("Показать пароль")
        self.show_passwords_button.setProperty("variant", "secondary")
        self.show_passwords_button.setCheckable(True)
        self.show_passwords_button.clicked.connect(self._toggle_password_visibility)
        helper_row.addWidget(self.show_passwords_button)

        helper_row.addStretch(1)
        form_layout.addLayout(helper_row)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setProperty("role", "table-row")
        form_layout.addWidget(separator)

        storage_note = QLabel(
            f"Настройки доступа сохраняются локально в `{self.workspace_root / 'app_data' / 'admin_access.json'}`."
        )
        storage_note.setProperty("role", "muted")
        storage_note.setWordWrap(True)
        form_layout.addWidget(storage_note)
        root.addWidget(form_card)

        buttons = QDialogButtonBox()
        self.save_button = QPushButton("Сохранить пароль")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self._save_password)
        buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.AcceptRole)

        self.reset_button = QPushButton("Сбросить пароль")
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.clicked.connect(self._reset_password)
        buttons.addButton(self.reset_button, QDialogButtonBox.ButtonRole.DestructiveRole)

        self.close_button = QPushButton("Закрыть")
        self.close_button.setProperty("variant", "outline")
        self.close_button.clicked.connect(self.reject)
        buttons.addButton(self.close_button, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        self._refresh_state()

    def _refresh_state(self) -> None:
        state = self.store.load_state()
        self._apply_state(state)

    def _apply_state(self, state: AdminAccessState) -> None:
        if state.configured:
            hint = f" Подсказка: {state.password_hint}" if state.password_hint else ""
            self.status_label.setText(f"Сейчас админ-пароль уже задан.{hint}")
            self.reset_button.setEnabled(True)
        else:
            self.status_label.setText("Сейчас админ-пароль ещё не задан.")
            self.reset_button.setEnabled(False)
        self.hint_input.setText(state.password_hint)

    def _toggle_password_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)
        self.confirm_input.setEchoMode(mode)
        self.show_passwords_button.setText("Скрыть пароль" if checked else "Показать пароль")

    def _show_inline_message(self, text: str, tone: str) -> None:
        bg, fg = tone_pair(tone)
        self.message_label.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {fg}; border-radius: 12px; padding: 10px 12px;"
        )
        self.message_label.setText(text)
        self.message_label.show()

    def _save_password(self) -> None:
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        hint = self.hint_input.text().strip()

        if not password.strip():
            self._show_inline_message("Пароль не может быть пустым.", "danger")
            return
        if password != confirm:
            self._show_inline_message("Повтор пароля не совпадает.", "danger")
            return

        self.store.set_password(password, hint)
        self._show_inline_message("Админ-пароль сохранён.", "success")
        self.password_input.clear()
        self.confirm_input.clear()
        self._refresh_state()
        self.accept()

    def _reset_password(self) -> None:
        answer = QMessageBox.question(
            self,
            "Сброс пароля",
            "Сбросить админ-пароль и отключить режим отладки?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.store.clear_password()
        self.password_input.clear()
        self.confirm_input.clear()
        self.hint_input.clear()
        self._show_inline_message("Админ-пароль сброшен.", "warning")
        self._refresh_state()
        self.accept()
