from __future__ import annotations

import pytest
from PySide6.QtWidgets import QBoxLayout, QLabel, QPushButton

pytest.importorskip("PySide6")

from tests.support.app_driver import build_app_session, make_ollama_diagnostics
from tests.support.visual_audit import button_text_fits, label_text_fits
from tests.support.workspace_builder import create_workspace_bundle, seed_standard_document, seed_state_exam_document


def test_library_visual_gate_keeps_document_detail_wide_and_clean(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.window.resize(1500, 920)
        session.switch("library")
        session.library.select_first_document()
        session.process_events(0.2)

        view = session.window.views["library"]
        training_buttons = [
            button
            for button in view.detail_panel.findChildren(QPushButton)
            if button.isVisible() and button.text() == "К упражнениям"
        ]

        assert view.detail_panel.width() >= 700
        assert label_text_fits(view.detail_panel.title_label)
        assert training_buttons
        assert min(button.width() for button in training_buttons) >= 136
        assert min(button.height() for button in training_buttons) >= 36
        assert view.detail_panel.delete_button.height() >= 34
    finally:
        session.close()


def test_tickets_visual_gate_keeps_reader_surface_large_and_readable(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.window.resize(1500, 920)
        session.switch("tickets")
        ticket_id = session.window.views["tickets"].tickets[0].ticket_id
        session.tickets.focus_ticket(ticket_id)
        session.process_events(0.2)

        view = session.window.views["tickets"]
        reading_body = view.detail_widget.findChild(QLabel, "tickets-reading-body")
        action_buttons = [button for button in (view.current_training_button, view.current_dialogue_button) if button is not None]

        assert view.detail_scroll.viewport().width() >= 700
        assert reading_body is not None
        assert label_text_fits(reading_body)
        assert reading_body.width() >= 620
        assert len(action_buttons) == 2
        assert min(button.height() for button in action_buttons) >= 36
        assert min(button.width() for button in action_buttons) >= 150
    finally:
        session.close()


def test_training_visual_gate_keeps_primary_workspace_readable(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_state_exam_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.window.resize(1500, 920)
        session.switch("training")
        session.training.select_mode("state-exam-full")
        session.process_events(0.2)

        view = session.window.views["training"]
        workspace = view.workspace_stack.currentWidget()
        submit_button = workspace.findChild(QPushButton, "training-state-exam-submit")

        assert view.session_card.width() >= 640
        assert workspace.width() >= 620
        assert submit_button is not None
        assert button_text_fits(submit_button)
        assert submit_button.height() >= 36
    finally:
        session.close()


def test_dialogue_visual_gate_prefers_long_layout_on_regular_width(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(True))
    try:
        session.window.resize(1500, 920)
        session.switch("dialogue")
        session.process_events(0.2)

        view = session.window.views["dialogue"]

        assert view.gate_card.isVisible() is False
        assert view.body_layout.direction() == QBoxLayout.Direction.TopToBottom
        assert view.center_column.width() >= 1000
        assert view.center_column.width() >= view.left_column.width()
        assert view.transcript_scroll.viewport().width() >= 1000
        assert view.transcript_card.width() >= 1000
        assert view.composer_card.width() >= 1000
        assert view.status_chip.isVisible() is True
    finally:
        session.close()
