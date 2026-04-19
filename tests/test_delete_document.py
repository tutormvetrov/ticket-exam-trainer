from __future__ import annotations

from datetime import datetime
from pathlib import Path

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from domain.answer_profile import AnswerProfileCode
from domain.knowledge import (
    AtomType,
    CrossTicketLink,
    Exam,
    KnowledgeAtom,
    Section,
    SourceDocument,
    TicketKnowledgeMap,
    WeakArea,
    WeakAreaKind,
)
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.db.repository import KnowledgeRepository


def _make_document(document_id: str, *, exam_id: str = "exam", section_id: str = "section", title: str = "Doc") -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        exam_id=exam_id,
        subject_id="demo",
        title=title,
        file_path=f"/tmp/{document_id}.docx",
        file_type="DOCX",
        size_bytes=1024,
        imported_at=datetime.now(),
        answer_profile_code=AnswerProfileCode.STANDARD_TICKET,
    )


def _make_ticket(
    ticket_id: str,
    *,
    document_id: str,
    exam_id: str = "exam",
    section_id: str = "section",
    title: str = "Ticket",
    atoms: list[KnowledgeAtom] | None = None,
    cross_links: list[CrossTicketLink] | None = None,
) -> TicketKnowledgeMap:
    return TicketKnowledgeMap(
        ticket_id=ticket_id,
        exam_id=exam_id,
        section_id=section_id,
        source_document_id=document_id,
        title=title,
        canonical_answer_summary="Summary",
        atoms=atoms
        or [
            KnowledgeAtom(
                atom_id=f"{ticket_id}-atom-1",
                type=AtomType.DEFINITION,
                label="Определение",
                text="Текст атома",
                keywords=["demo"],
                weight=1.0,
            )
        ],
        skills=[],
        exercise_templates=[],
        scoring_rubric=[],
        examiner_prompts=[],
        cross_links_to_other_tickets=cross_links or [],
        difficulty=1,
        estimated_oral_time_sec=60,
    )


def _seed_document(repository: KnowledgeRepository, *, document_id: str, ticket_ids: list[str]) -> None:
    document = _make_document(document_id)
    repository.save_exam(Exam("exam", "Demo", "Demo", len(ticket_ids), "demo"))
    repository.save_section(Section("section", "exam", "Section", 1))
    repository.save_source_document(document)
    for ticket_id in ticket_ids:
        repository.save_ticket_map(_make_ticket(ticket_id, document_id=document_id))


def _make_facade(tmp_path: Path) -> AppFacade:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(DEFAULT_OLLAMA_SETTINGS)
    return AppFacade(workspace_root, connection, settings_store)


def test_delete_document_returns_false_for_missing_document(tmp_path: Path) -> None:
    connection = connect_initialized(get_database_path(tmp_path))
    repository = KnowledgeRepository(connection)
    try:
        assert repository.delete_document("nonexistent") is False
    finally:
        connection.close()


def test_delete_document_cascades_tickets_chunks_and_queue(tmp_path: Path) -> None:
    connection = connect_initialized(get_database_path(tmp_path))
    repository = KnowledgeRepository(connection)
    try:
        _seed_document(repository, document_id="doc-1", ticket_ids=["ticket-a", "ticket-b"])
        connection.execute(
            "INSERT INTO content_chunks (chunk_id, document_id, chunk_index, text) VALUES (?, ?, ?, ?)",
            ("chunk-1", "doc-1", 0, "body"),
        )
        connection.execute(
            """
            INSERT INTO import_ticket_queue (
                ticket_id, document_id, ticket_index, section_id, title, body_text,
                candidate_confidence, llm_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("ticket-a", "doc-1", 1, "section", "Ticket", "body", 0.5, "done"),
        )
        connection.commit()

        assert repository.delete_document("doc-1") is True

        def _count(table: str) -> int:
            return int(connection.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"])

        assert _count("source_documents") == 0
        assert _count("tickets") == 0
        assert _count("atoms") == 0
        assert _count("content_chunks") == 0
        assert _count("import_ticket_queue") == 0
    finally:
        connection.close()


def test_delete_document_preserves_unrelated_documents(tmp_path: Path) -> None:
    connection = connect_initialized(get_database_path(tmp_path))
    repository = KnowledgeRepository(connection)
    try:
        _seed_document(repository, document_id="doc-1", ticket_ids=["ticket-a"])
        repository.save_source_document(_make_document("doc-2", title="Other doc"))
        repository.save_ticket_map(_make_ticket("ticket-c", document_id="doc-2"))

        assert repository.delete_document("doc-1") is True

        remaining_docs = {row["document_id"] for row in connection.execute("SELECT document_id FROM source_documents").fetchall()}
        remaining_tickets = {row["ticket_id"] for row in connection.execute("SELECT ticket_id FROM tickets").fetchall()}
        assert remaining_docs == {"doc-2"}
        assert remaining_tickets == {"ticket-c"}
    finally:
        connection.close()


def test_delete_document_cleans_weak_areas_linked_to_deleted_ids(tmp_path: Path) -> None:
    connection = connect_initialized(get_database_path(tmp_path))
    repository = KnowledgeRepository(connection)
    try:
        _seed_document(repository, document_id="doc-1", ticket_ids=["ticket-a"])
        repository.save_source_document(_make_document("doc-2", title="Other doc"))
        repository.save_ticket_map(_make_ticket("ticket-c", document_id="doc-2"))

        repository.save_weak_areas(
            "local-user",
            "ticket-a",
            [
                WeakArea(
                    weak_area_id="weak-1",
                    user_id="local-user",
                    kind=WeakAreaKind.ATOM,
                    reference_id="ticket-a-atom-1",
                    title="Слабое определение",
                    severity=0.8,
                    evidence="",
                    related_ticket_ids=["ticket-a"],
                ),
                WeakArea(
                    weak_area_id="weak-2",
                    user_id="local-user",
                    kind=WeakAreaKind.ATOM,
                    reference_id="ticket-c-atom-1",
                    title="Слабое определение другой темы",
                    severity=0.6,
                    evidence="",
                    related_ticket_ids=["ticket-c"],
                ),
            ],
        )

        assert repository.delete_document("doc-1") is True

        remaining = [row["weak_area_id"] for row in connection.execute("SELECT weak_area_id FROM weak_areas").fetchall()]
        assert remaining == ["weak-2"]
    finally:
        connection.close()


def test_delete_document_removes_orphan_cross_ticket_concepts(tmp_path: Path) -> None:
    connection = connect_initialized(get_database_path(tmp_path))
    repository = KnowledgeRepository(connection)
    try:
        repository.save_exam(Exam("exam", "Demo", "Demo", 3, "demo"))
        repository.save_section(Section("section", "exam", "Section", 1))
        repository.save_source_document(_make_document("doc-1"))
        repository.save_source_document(_make_document("doc-2", title="Other doc"))

        orphan_link = CrossTicketLink("concept-orphan", "Изоляция", ["ticket-b"], "Rationale", 0.8)
        shared_link = CrossTicketLink("concept-shared", "Связь", ["ticket-b"], "Rationale", 0.7)

        repository.save_ticket_map(
            _make_ticket(
                "ticket-a",
                document_id="doc-1",
                cross_links=[orphan_link, shared_link],
            )
        )
        repository.save_ticket_map(
            _make_ticket(
                "ticket-b",
                document_id="doc-2",
                cross_links=[shared_link],
            )
        )

        concept_ids_before = {
            row["concept_id"] for row in connection.execute("SELECT concept_id FROM cross_ticket_concepts").fetchall()
        }
        assert concept_ids_before == {"concept-orphan", "concept-shared"}

        assert repository.delete_document("doc-1") is True

        remaining_concepts = {
            row["concept_id"] for row in connection.execute("SELECT concept_id FROM cross_ticket_concepts").fetchall()
        }
        assert remaining_concepts == {"concept-shared"}
    finally:
        connection.close()


def test_facade_delete_document_refreshes_review_queue(tmp_path: Path) -> None:
    facade = _make_facade(tmp_path)
    try:
        repository = facade.repository
        _seed_document(repository, document_id="doc-1", ticket_ids=["ticket-a"])

        facade.connection.execute(
            """
            INSERT INTO spaced_review_queue (
                review_item_id, user_id, ticket_id, reference_type, reference_id,
                mode, priority, due_at, scheduled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "queue-1",
                "local-user",
                "ticket-a",
                "ticket",
                "ticket-a",
                "standard_adaptive",
                1.0,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )
        facade.connection.commit()

        assert facade.delete_document("doc-1") is True
        remaining = facade.connection.execute("SELECT COUNT(*) AS total FROM spaced_review_queue").fetchone()["total"]
        assert remaining == 0
    finally:
        facade.connection.close()


def test_facade_delete_document_returns_false_for_missing(tmp_path: Path) -> None:
    facade = _make_facade(tmp_path)
    try:
        assert facade.delete_document("missing") is False
    finally:
        facade.connection.close()
