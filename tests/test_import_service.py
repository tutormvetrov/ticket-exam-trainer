from __future__ import annotations

from pathlib import Path

from docx import Document
from reportlab.pdfgen import canvas

from application.import_service import DocumentImportService, TicketCandidate


SOURCE_TEXT = """Section 1. Public assets

Ticket 1. What is public property as an object of management? Public property is a public resource assigned to public bodies. Examples include land, buildings and infrastructure. The asset has a legal regime and requires control. The management cycle includes accounting, valuation, use and review.

Ticket 2. How is efficiency of public property evaluated? Efficiency is evaluated through public goals, usage results and cost control. For example, analysts check utilization and social effect.
"""


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
