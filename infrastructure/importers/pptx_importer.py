from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from infrastructure.importers.common import ImportedDocumentText, normalize_import_title


PRESENTATION_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def import_pptx(path: str) -> ImportedDocumentText:
    pptx_path = Path(path)
    slide_texts: list[str] = []
    with ZipFile(pptx_path, "r") as archive:
        slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        for slide_name in slide_names:
            root = ET.fromstring(archive.read(slide_name))
            texts = [node.text.strip() for node in root.findall(".//a:t", PRESENTATION_NS) if node.text and node.text.strip()]
            if texts:
                slide_texts.append("\n".join(texts))
    raw_text = "\n\n".join(slide_texts)
    return ImportedDocumentText(
        path=pptx_path,
        title=normalize_import_title(pptx_path.stem),
        file_type="PPTX",
        raw_text=raw_text,
        unit_count=len(slide_texts),
    )
