from __future__ import annotations

from pathlib import Path

from docx import Document

from infrastructure.importers.common import ImportedDocumentText, normalize_import_title


def import_docx(path: str) -> ImportedDocumentText:
    docx_path = Path(path)
    document = Document(str(docx_path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    raw_text = "\n\n".join(paragraphs)
    return ImportedDocumentText(
        path=docx_path,
        title=normalize_import_title(docx_path.stem),
        file_type="DOCX",
        raw_text=raw_text,
        unit_count=len(paragraphs),
    )
