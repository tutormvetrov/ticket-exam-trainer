from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from infrastructure.importers.common import ImportedDocumentText, normalize_import_title


def import_pdf(path: str) -> ImportedDocumentText:
    pdf_path = Path(path)
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    raw_text = "\n\n".join(page for page in pages if page)
    return ImportedDocumentText(
        path=pdf_path,
        title=normalize_import_title(pdf_path.stem),
        file_type="PDF",
        raw_text=raw_text,
        unit_count=len(reader.pages),
    )
