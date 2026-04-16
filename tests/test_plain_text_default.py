from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.bootstrap import _install_plain_text_default_for_qlabel
from ui.components.common import harden_plain_text


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_harden_plain_text_marks_labels_plain(qt_app) -> None:
    label = QLabel("test")
    label.setTextFormat(Qt.TextFormat.AutoText)
    harden_plain_text(label)
    assert label.textFormat() == Qt.TextFormat.PlainText


def test_global_bootstrap_default_applies_to_new_labels(qt_app) -> None:
    _install_plain_text_default_for_qlabel()
    label = QLabel("<img src=x>")
    assert label.textFormat() == Qt.TextFormat.PlainText
    # Несмотря на HTML-подобный текст, QLabel должен показать его буквально.
    assert label.text() == "<img src=x>"
