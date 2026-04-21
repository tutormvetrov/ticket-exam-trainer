from __future__ import annotations

from pathlib import Path

from application.user_profile import DEFAULT_EXAM_ID, ProfileStore, build_profile
from infrastructure.db import connect_initialized
from ui_flet.main import (
    _bootstrap_seed_if_empty,
    _ensure_profile_exam_compatibility,
    _select_seed_candidate,
)


def _seed_legacy_local_exam(database_path: Path) -> None:
    connection = connect_initialized(database_path)
    try:
        connection.execute(
            """
            INSERT INTO exams (exam_id, title, description, total_tickets, subject_area)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "local-exam",
                "Локальная база билетов",
                "legacy import bucket",
                1,
                "exam-training",
            ),
        )
        connection.execute(
            """
            INSERT INTO sections (section_id, exam_id, title, order_index, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "local-section",
                "local-exam",
                "Legacy section",
                1,
                "",
            ),
        )
        connection.execute(
            """
            INSERT INTO source_documents (
                document_id, exam_id, subject_id, answer_profile_code, title, file_path, file_type,
                size_bytes, checksum, imported_at, raw_text, status, warnings_json,
                used_llm_assist, ticket_total, tickets_llm_done, last_attempted_at, last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            """,
            (
                "local-doc",
                "local-exam",
                "local-subject",
                "standard_ticket",
                "Legacy document",
                "legacy.docx",
                "docx",
                123,
                "checksum",
                "legacy raw text",
                "structured",
                "[]",
                0,
                1,
                1,
                "",
            ),
        )
        connection.execute(
            """
            INSERT INTO tickets (
                ticket_id, exam_id, section_id, source_document_id, answer_profile_code, title,
                canonical_answer_summary, difficulty, estimated_oral_time_sec, source_confidence,
                status, llm_status, llm_error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                "local-ticket",
                "local-exam",
                "local-section",
                "local-doc",
                "standard_ticket",
                "Legacy ticket",
                "Legacy answer",
                1,
                60,
                0.5,
                "structured",
                "done",
                "",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_bootstrap_merges_release_content_into_legacy_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = workspace_root / "exam_trainer.db"
    _seed_legacy_local_exam(database_path)

    seed_path = _select_seed_candidate(workspace_root)
    assert seed_path is not None, "Bundled seed DB is required for release bootstrap tests."

    status = _bootstrap_seed_if_empty(workspace_root, database_path)

    assert status == "merged_release_content"

    connection = connect_initialized(database_path)
    try:
        local_count = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE exam_id = ?",
            ("local-exam",),
        ).fetchone()[0]
        release_count = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE exam_id = ?",
            (DEFAULT_EXAM_ID,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert local_count == 1
    assert release_count > 0


def test_profile_exam_is_repaired_when_active_exam_has_no_tickets(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = workspace_root / "exam_trainer.db"
    _seed_legacy_local_exam(database_path)

    profile_store = ProfileStore(workspace_root / "app_data" / "profile.json")
    profile = build_profile("Миша", "🦉", active_exam_id=DEFAULT_EXAM_ID)
    profile_store.save(profile)

    connection = connect_initialized(database_path)
    try:
        repaired = _ensure_profile_exam_compatibility(
            profile_store,
            profile_store.load(),
            connection,
        )
    finally:
        connection.close()

    assert repaired is not None
    assert repaired.active_exam_id == "local-exam"
    persisted = profile_store.load()
    assert persisted is not None
    assert persisted.active_exam_id == "local-exam"
