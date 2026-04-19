from __future__ import annotations

import importlib
import logging
from hashlib import sha256
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from infrastructure.importers.common import ImportedDocumentText, normalize_import_title
from infrastructure.importers.ocr_support import (
    is_meaningful_image,
    ocr_image_bytes,
    should_keep_ocr_text,
)

_LOG = logging.getLogger(__name__)
_MIN_PAGE_TEXT_BEFORE_FALLBACK = 120


def import_pdf(path: str, *, workspace_root: Path | None = None) -> ImportedDocumentText:
    pdf_path = Path(path)
    reader = PdfReader(str(pdf_path))
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    warnings: list[str] = []

    try:
        page_texts = _augment_pages_with_ocr(pdf_path, page_texts, workspace_root=workspace_root)
    except Exception as exc:
        _LOG.exception("PDF OCR augmentation failed path=%s", pdf_path)
        warnings.append(f"OCR skipped for {pdf_path.name}: {exc}")

    raw_text = "\n\n".join(page_text for page_text in page_texts if page_text)
    return ImportedDocumentText(
        path=pdf_path,
        title=normalize_import_title(pdf_path.stem),
        file_type="PDF",
        raw_text=raw_text,
        unit_count=len(reader.pages),
        warnings=tuple(warnings),
    )


def _augment_pages_with_ocr(
    pdf_path: Path,
    page_texts: list[str],
    *,
    workspace_root: Path | None = None,
) -> list[str]:
    augmented_pages = list(page_texts)
    fitz = _load_fitz()
    with fitz.open(str(pdf_path)) as document:
        for page_index in range(document.page_count):
            base_text = page_texts[page_index] if page_index < len(page_texts) else ""
            ocr_blocks = _extract_page_ocr_blocks(
                document,
                page_index,
                base_text,
                workspace_root=workspace_root,
                fitz_module=fitz,
            )
            if ocr_blocks:
                augmented_pages[page_index] = "\n\n".join(part for part in [base_text, *ocr_blocks] if part)
    return augmented_pages


def _extract_page_ocr_blocks(
    document: Any,
    page_index: int,
    base_text: str,
    *,
    workspace_root: Path | None = None,
    fitz_module: Any,
) -> list[str]:
    page = document.load_page(page_index)
    blocks: list[str] = []
    seen_digests: set[str] = set()

    for image_info in page.get_images(full=True):
        xref = int(image_info[0] or 0)
        if xref <= 0:
            continue
        extracted = document.extract_image(xref)
        image_bytes = extracted.get("image", b"")
        if not image_bytes or not is_meaningful_image(image_bytes):
            continue

        digest = sha256(image_bytes).hexdigest()
        if digest in seen_digests:
            continue
        seen_digests.add(digest)

        ocr_text = ocr_image_bytes(image_bytes, workspace_root=workspace_root)
        existing_text = "\n\n".join([base_text, *blocks])
        if should_keep_ocr_text(existing_text, ocr_text):
            blocks.append(ocr_text)

    if blocks or len(base_text.strip()) >= _MIN_PAGE_TEXT_BEFORE_FALLBACK:
        return blocks

    page_bytes = page.get_pixmap(matrix=fitz_module.Matrix(2, 2), alpha=False).tobytes("png")
    if not is_meaningful_image(page_bytes):
        return blocks

    fallback_text = ocr_image_bytes(page_bytes, workspace_root=workspace_root)
    if should_keep_ocr_text(base_text, fallback_text):
        blocks.append(fallback_text)
    return blocks


def _load_fitz() -> Any:
    try:
        return importlib.import_module("fitz")
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF backend is unavailable: {exc}") from exc
