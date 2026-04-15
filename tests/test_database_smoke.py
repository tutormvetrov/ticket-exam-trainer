from __future__ import annotations

from datetime import datetime
from pathlib import Path

from domain.answer_profile import AnswerProfileCode
from domain.knowledge import AtomType, CrossTicketLink, Exam, KnowledgeAtom, Section, SourceDocument, TicketKnowledgeMap
from infrastructure.db import connect_initialized
from infrastructure.db.repository import KnowledgeRepository


def test_database_schema_smoke(tmp_path: Path) -> None:
    database_path = tmp_path / "exam.db"
    connection = connect_initialized(database_path)
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    connection.close()
    assert "tickets" in tables
    assert "atoms" in tables
    assert "ticket_mastery_profiles" in tables
    assert "spaced_review_queue" in tables


def test_save_ticket_map_tolerates_duplicate_concept_ids(tmp_path: Path) -> None:
    database_path = tmp_path / "exam.db"
    connection = connect_initialized(database_path)
    repository = KnowledgeRepository(connection)
    repository.save_exam(Exam("exam", "Demo", "Demo", 1, "demo"))
    repository.save_section(Section("section", "exam", "Section", 1))
    repository.save_source_document(
        SourceDocument(
            document_id="doc-1",
            exam_id="exam",
            subject_id="demo",
            title="Demo doc",
            file_path=str(database_path),
            file_type="DOCX",
            size_bytes=1,
            imported_at=datetime.now(),
            answer_profile_code=AnswerProfileCode.STANDARD_TICKET,
        )
    )

    ticket = TicketKnowledgeMap(
        ticket_id="ticket-1",
        exam_id="exam",
        section_id="section",
        source_document_id="doc-1",
        title="Demo ticket",
        canonical_answer_summary="Summary",
        atoms=[
            KnowledgeAtom(
                atom_id="atom-1",
                type=AtomType.DEFINITION,
                label="Определение",
                text="Текст атома",
                keywords=["управление"],
                weight=1.0,
            )
        ],
        skills=[],
        exercise_templates=[],
        scoring_rubric=[],
        examiner_prompts=[],
        cross_links_to_other_tickets=[
            CrossTicketLink("concept-demo", "Управление", ["ticket-2"], "Rationale 1", 0.7),
            CrossTicketLink("concept-demo", "Управление", ["ticket-3"], "Rationale 2", 0.8),
        ],
        difficulty=1,
        estimated_oral_time_sec=60,
    )

    repository.save_ticket_map(ticket)
    repository.save_ticket_map(ticket)

    concepts = connection.execute("SELECT COUNT(*) AS total FROM ticket_concepts WHERE ticket_id = ?", ("ticket-1",)).fetchone()
    assert concepts["total"] == 1
    connection.close()
