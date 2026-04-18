from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from tests.support.app_driver import build_app_session, make_ollama_diagnostics
from tests.support.workspace_builder import (
    create_workspace_bundle,
    seed_reading_attempt,
    seed_standard_document,
    seed_state_exam_document,
)


def test_empty_workspace_guides_student_to_real_next_step(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    workspace_root = bundle.workspace_root
    bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.switch("library")
        assert session.library.is_empty() is True

        session.switch("training")
        assert session.training.view.session_empty_state.isVisible() is True

        session.switch("dialogue")
        assert session.dialogue.gate_visible() is True
        assert "Ollama:" in session.dialogue.status_text()
    finally:
        session.close()


def test_student_can_open_document_read_ticket_and_complete_training(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.switch("library")
        session.library.select_first_document()

        assert session.library.documents_collapsed() is True
        assert session.library.detail_title()

        ticket_id = session.library.open_reader_for_first_ticket()
        assert session.window.current_key == "tickets"
        assert session.tickets.current_ticket_id() == ticket_id
        assert session.tickets.reading_text().strip()

        session.switch("library")
        session.library.select_first_document()
        session.library.open_training_for_first_ticket()

        assert session.window.current_key == "training"
        assert session.training.current_ticket_title().strip()

        session.training.select_mode("reading")
        session.training.submit_reading_understood()

        attempts_total = session.window.facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"]

        assert attempts_total >= 1
        assert session.training.result_text().strip()

        session.switch("statistics")
        assert session.window.views["statistics"].empty_state.isVisible() is False
    finally:
        session.close()


def test_state_exam_ticket_opens_full_exam_workspace_for_student(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_state_exam_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.switch("training")
        session.training.select_mode("state-exam-full")

        assert session.training.state_exam_editor_count() >= 6

        session.training.submit_state_exam_answer(
            "Проблема связана с публичными ресурсами. Теоретическая база включает правовой режим имущества."
        )

        attempts_total = session.window.facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"]

        assert attempts_total >= 1
        assert session.training.result_text().strip()
    finally:
        session.close()


def test_student_progress_persists_after_restart(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        seed_reading_attempt(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.switch("statistics")
        assert session.window.views["statistics"].empty_state.isVisible() is False

        reopened = session.reopen(diagnostics=make_ollama_diagnostics(False))
        try:
            reopened.switch("library")
            assert reopened.library.is_empty() is False

            reopened.switch("statistics")
            assert reopened.window.views["statistics"].empty_state.isVisible() is False
        finally:
            reopened.close()
    except Exception:
        session.close()
        raise


def test_student_can_delete_document_and_return_to_clean_state(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        workspace_root = bundle.workspace_root
    finally:
        bundle.close()

    session = build_app_session(workspace_root, diagnostics=make_ollama_diagnostics(False))
    try:
        session.switch("library")
        session.library.select_first_document()
        session.library.delete_current_document()

        assert session.library.is_empty() is True

        reopened = session.reopen(diagnostics=make_ollama_diagnostics(False))
        try:
            reopened.switch("library")
            assert reopened.library.is_empty() is True
        finally:
            reopened.close()
    except Exception:
        session.close()
        raise
