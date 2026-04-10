from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class ImportedDocumentText:
    path: Path
    title: str
    file_type: str
    raw_text: str
    unit_count: int


def normalize_import_title(stem: str) -> str:
    text = stem.strip().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip(" .-_")
    tokens = [token for token in text.split(" ") if token and token.lower() not in {"ru", "rus"}]
    text = " ".join(tokens) if tokens else text
    if not text:
        return "Импортированный документ"
    if any(char.isalpha() for char in text) and text == text.lower():
        return text.title()
    return text
