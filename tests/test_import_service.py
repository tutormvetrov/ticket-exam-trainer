from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from docx import Document
from reportlab.pdfgen import canvas

from application.facade import AppFacade
from application.import_service import DocumentImportService, TicketCandidate
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from domain.knowledge import Exam, Section
from infrastructure.db import connect_initialized, get_database_path


SOURCE_TEXT = """Section 1. Public assets

Ticket 1. What is public property as an object of management? Public property is a public resource assigned to public bodies. Examples include land, buildings and infrastructure. The asset has a legal regime and requires control. The management cycle includes accounting, valuation, use and review.

Ticket 2. How is efficiency of public property evaluated? Efficiency is evaluated through public goals, usage results and cost control. For example, analysts check utilization and social effect.
"""


def _build_facade(tmp_path: Path) -> AppFacade:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(replace(DEFAULT_OLLAMA_SETTINGS, auto_check_ollama_on_start=False))
    return AppFacade(workspace_root, connection, settings_store)


def test_build_ticket_model_from_text() -> None:
    service = DocumentImportService()
    candidate = TicketCandidate(
        index=1,
        title="What is public property as an object of management?",
        body="Public property is a public resource. Examples include land and buildings. The management cycle includes accounting and review.",
        confidence=0.9,
        section_title="public-assets",
    )
    ticket, used_llm, warning = service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    assert ticket.title.startswith("What is public property")
    assert len(ticket.atoms) >= 3
    assert ticket.skills
    assert not used_llm
    assert warning == ""


def test_docx_import_smoke(tmp_path: Path) -> None:
    document_path = tmp_path / "demo.docx"
    document = Document()
    for paragraph in SOURCE_TEXT.split("\n\n"):
        document.add_paragraph(paragraph)
    document.save(document_path)

    service = DocumentImportService()
    result = service.import_document(document_path, "exam-demo", "subject-demo", "public-assets")

    assert len(result.tickets) == 2
    assert len(result.tickets[0].atoms) >= 4
    assert not result.warnings


def test_pdf_import_smoke(tmp_path: Path) -> None:
    pdf_path = tmp_path / "demo.pdf"
    pdf = canvas.Canvas(str(pdf_path))
    text = pdf.beginText(40, 800)
    for line in SOURCE_TEXT.splitlines():
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()

    service = DocumentImportService()
    result = service.import_document(pdf_path, "exam-demo", "subject-demo", "public-assets")

    assert len(result.tickets) == 2
    assert len(result.tickets[1].atoms) >= 2


def test_incremental_import_preserves_saved_tickets_and_resume_finishes_tail(tmp_path: Path, monkeypatch) -> None:
    document_path = tmp_path / "demo.docx"
    document = Document()
    for paragraph in SOURCE_TEXT.split("\n\n"):
        document.add_paragraph(paragraph)
    document.save(document_path)

    facade = _build_facade(tmp_path)
    original_build = DocumentImportService.build_ticket_map
    state = {"failed_once": False}

    monkeypatch.setattr(DocumentImportService, "should_use_llm_for_structuring", lambda *args, **kwargs: False)

    def flaky_build(self, candidate, exam_id, section_id, source_document_id, ticket_id=None):
        if candidate.index == 2 and not state["failed_once"]:
            state["failed_once"] = True
            raise RuntimeError("forced partial failure")
        return original_build(self, candidate, exam_id, section_id, source_document_id, ticket_id=ticket_id)

    monkeypatch.setattr(DocumentImportService, "build_ticket_map", flaky_build)

    result = facade.import_document_with_progress(document_path)

    assert result.ok
    assert result.status == "partial_llm"
    assert result.resume_available
    assert facade.connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()["total"] == 1
    queue_counts = facade.repository.count_import_queue_statuses(result.document_id)
    assert queue_counts["done"] == 1
    assert queue_counts["failed"] == 1

    monkeypatch.setattr(DocumentImportService, "build_ticket_map", original_build)
    resumed = facade.resume_document_import_with_progress(result.document_id)

    assert resumed.ok
    assert resumed.status == "structured"
    assert resumed.llm_done_tickets == 2
    assert resumed.resume_available is False
    assert facade.connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()["total"] == 2
    queue_counts = facade.repository.count_import_queue_statuses(result.document_id)
    assert queue_counts["done"] == 2

    facade.connection.close()


def test_legacy_document_without_queue_is_marked_resumable(tmp_path: Path) -> None:
    document_path = tmp_path / "demo.docx"
    document = Document()
    for paragraph in SOURCE_TEXT.split("\n\n"):
        document.add_paragraph(paragraph)
    document.save(document_path)

    facade = _build_facade(tmp_path)
    service = DocumentImportService()
    structured = service.import_document(document_path, "local-exam", "demo", "public-assets")

    facade.repository.save_exam(
        Exam(
            exam_id="local-exam",
            title="Demo",
            description="Demo exam",
            total_tickets=len(structured.tickets),
            subject_area="demo",
        )
    )
    facade.repository.save_section(
        Section(
            section_id="public-assets",
            exam_id="local-exam",
            title="Public assets",
            order_index=1,
            description="Demo section",
        )
    )
    facade.repository.save_source_document(
        structured.source_document,
        raw_text=structured.normalized_text,
        status="structured",
        warnings=[],
        used_llm_assist=False,
        ticket_total=0,
        tickets_llm_done=0,
    )
    facade.repository.save_chunks(structured.source_document.document_id, structured.chunks)
    for ticket in structured.tickets:
        facade.repository.save_ticket_map(ticket, llm_status="done", llm_error="")

    latest = facade.load_latest_import_result()

    assert latest.status == "partial_llm"
    assert latest.resume_available
    assert latest.llm_pending_tickets == 2
    facade.connection.close()


def test_import_ollama_timeout_is_unbounded_for_long_import_runs(tmp_path: Path) -> None:
    facade = _build_facade(tmp_path)

    service = DocumentImportService(
        ollama_service=facade.build_import_ollama_service(),
        llm_model=facade.settings.model,
        enable_llm_structuring=True,
    )

    assert service.ollama_service is not None
    assert service.ollama_service.timeout_seconds is None
    assert service.ollama_service.client.timeout_seconds is None
    facade.connection.close()
