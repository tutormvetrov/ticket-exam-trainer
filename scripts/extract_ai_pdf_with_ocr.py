"""Re-extract the AI-course PDF into raw_with_ocr.txt — same as
extract_ai_pdf_to_tickets but additionally OCRs every embedded image
so that content trapped in screenshots / formulas / tables becomes
plain text.

Uses the app's own infrastructure.importers.ocr_support (rapidocr_onnxruntime
with the Cyrillic PP-OCRv5 model). Modes download once into
app_data/ocr_models and are cached thereafter.

Output:
    build/ai-extract/raw_with_ocr.txt   — one giant text blob with
    page banners identical to raw.txt but with `[OCR:…]` blocks inserted
    wherever an image was decoded.

Takes 5-25 minutes depending on image count. Run once, then point
parse_ai_pdf_to_tickets.py at the new file.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fitz  # pymupdf

from infrastructure.importers.ocr_support import (
    is_meaningful_image,
    ocr_image_bytes,
    should_keep_ocr_text,
)

PDF_PATH = REPO_ROOT / "3_1_MDE_IIiTsKvGA_2024_Kol_Konspekt_GMU_ot_03_05_2024.pdf"
OUT_PATH = REPO_ROOT / "build" / "ai-extract" / "raw_with_ocr.txt"


def _extract_page_images(page: fitz.Page) -> list[bytes]:
    """Return the raw bytes of every image embedded on the page."""
    out: list[bytes] = []
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            pix = fitz.Pixmap(page.parent, xref)
            if pix.colorspace and pix.colorspace.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)  # drop alpha for JPEG-like encoders
            out.append(pix.tobytes("png"))
            pix = None  # release
        except Exception:
            continue
    return out


def main() -> int:
    if not PDF_PATH.exists():
        print(f"PDF missing: {PDF_PATH}", file=sys.stderr)
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(PDF_PATH))
    started = time.monotonic()
    total_pages = len(doc)
    total_images = 0
    kept_images = 0
    total_ocr_chars = 0

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for i, page in enumerate(doc):
            text = page.get_text()
            out.write(f"\n\n===== PAGE {i + 1} =====\n{text}")

            images = _extract_page_images(page)
            for j, img_bytes in enumerate(images):
                total_images += 1
                if not is_meaningful_image(img_bytes):
                    continue
                try:
                    ocr_text = ocr_image_bytes(
                        img_bytes, workspace_root=REPO_ROOT
                    )
                except Exception as exc:
                    sys.stderr.write(f"[page {i+1} img {j}] OCR error: {exc}\n")
                    continue
                if not ocr_text:
                    continue
                # Only keep OCR text that adds new content vs the page text.
                if not should_keep_ocr_text(text, ocr_text):
                    continue
                kept_images += 1
                total_ocr_chars += len(ocr_text)
                out.write(f"\n[OCR image {i + 1}.{j}]\n{ocr_text}\n")

            if (i + 1) % 10 == 0:
                elapsed = time.monotonic() - started
                print(
                    f"[page {i+1}/{total_pages}] images seen={total_images} "
                    f"kept={kept_images} ocr_chars={total_ocr_chars} elapsed={elapsed:.0f}s",
                    flush=True,
                )

    elapsed = time.monotonic() - started
    print(
        f"DONE: {total_pages} pages, {total_images} images seen, "
        f"{kept_images} OCR-kept, {total_ocr_chars} OCR chars added in {elapsed:.0f}s"
    )
    print(f"Saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
