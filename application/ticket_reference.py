from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from domain.answer_profile import AnswerBlockCode

BLOCK_ORDER: tuple[str, ...] = ("intro", "theory", "practice", "skills", "conclusion", "extra")
BLOCK_LABELS: dict[str, str] = {
    "intro": "Введение",
    "theory": "Теоретическая часть",
    "practice": "Практическая часть",
    "skills": "Навыки",
    "conclusion": "Заключение",
    "extra": "Дополнительные элементы",
}

_BLOCK_ORDER_INDEX = {code: index for index, code in enumerate(BLOCK_ORDER)}
_LIST_MARKER_RE = re.compile(r"^(?P<marker>(?:\d+[\.)])|[•●·*]|[-–—])\s+(?P<body>.+)$")
_SPACES_RE = re.compile(r"[ \t\f\v]+")
_SERVICE_PREFIX_RE = re.compile(
    r"^(?:\*\*)?\s*(?:основное содержание|основная часть|фрагмент\s+\d+)\s*[\.:]?\s*(?:\*\*)?\s*",
    re.IGNORECASE,
)
_TITLE_BYLINE_SUFFIXES: tuple[str, ...] = (
    "Шаруханов Шарухан",
    "Чернышов Елисей",
    "Шаруханов",
    "Камила",
)


@dataclass(frozen=True, slots=True)
class ReferenceAnswerBlock:
    code: str
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class ReferenceTextSegment:
    kind: str
    lines: tuple[str, ...]


def block_code_value(raw: object) -> str:
    if isinstance(raw, AnswerBlockCode):
        return raw.value
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw or "").lower().split(".")[-1]


def normalize_reference_text(text: str | None) -> str:
    """Make imported ticket text readable without changing its meaning."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("\u200b", "")
    normalized = normalized.replace("•\t", "• ").replace("·\t", "· ")
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for raw_line in normalized.split("\n"):
        line = _normalize_line(raw_line)
        if not line:
            if current:
                paragraphs.append(current)
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(current)

    rendered: list[str] = []
    for lines in paragraphs:
        if _all_list_items(lines):
            rendered.append("\n".join(_normalize_list_item(line) for line in lines))
            continue
        rendered.extend(_split_mixed_paragraph(lines))

    return "\n\n".join(part for part in rendered if part).strip()


def clean_ticket_title(title: str | None) -> str:
    cleaned = _SPACES_RE.sub(" ", (title or "").replace("\xa0", " ")).strip()
    if not cleaned:
        return ""
    for suffix in sorted(_TITLE_BYLINE_SUFFIXES, key=len, reverse=True):
        pattern = re.compile(rf"(?:[\s.]*\(?\s*{re.escape(suffix)}\s*\)?\s*)$", re.IGNORECASE)
        updated = pattern.sub("", cleaned).strip()
        if updated != cleaned:
            cleaned = updated.rstrip(" .(").strip()
            break
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([.])(?=[А-ЯЁ])", r"\1 ", cleaned)
    return cleaned


def reference_answer_blocks(ticket: object) -> list[ReferenceAnswerBlock]:
    blocks = list(getattr(ticket, "answer_blocks", None) or [])
    sorted_blocks = sorted(
        blocks,
        key=lambda block: _BLOCK_ORDER_INDEX.get(block_code_value(getattr(block, "block_code", "")), len(BLOCK_ORDER)),
    )

    result: list[ReferenceAnswerBlock] = []
    for block in sorted_blocks:
        if bool(getattr(block, "is_missing", False)):
            continue
        content = normalize_reference_text(getattr(block, "expected_content", "") or "")
        if not content:
            continue
        code = block_code_value(getattr(block, "block_code", ""))
        title = (getattr(block, "title", "") or BLOCK_LABELS.get(code, code)).strip()
        result.append(ReferenceAnswerBlock(code=code, title=title, content=content))
    return result


def compose_reference_answer(
    ticket: object,
    *,
    include_headings: bool = False,
    heading_level: int = 3,
) -> str:
    blocks = reference_answer_blocks(ticket)
    if blocks:
        if include_headings:
            marker = "#" * max(1, min(6, int(heading_level)))
            return "\n\n".join(f"{marker} {block.title}\n\n{block.content}" for block in blocks)
        return "\n\n".join(block.content for block in blocks)
    return normalize_reference_text(getattr(ticket, "canonical_answer_summary", "") or "")


def reference_answer_preview(ticket: object, *, limit: int = 500) -> str:
    return truncate_reference_text(compose_reference_answer(ticket), limit=limit)


def truncate_reference_text(text: str | None, *, limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", normalize_reference_text(text)).strip()
    if limit <= 0 or len(compact) <= limit:
        return compact
    hard_limit = max(1, limit - 1)
    window = compact[:hard_limit]
    sentence_cut = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if sentence_cut >= int(limit * 0.55):
        return window[: sentence_cut + 1].rstrip() + "…"
    return window.rstrip(" ,;:-") + "…"


def iter_reference_segments(text: str | None) -> Iterable[ReferenceTextSegment]:
    normalized = normalize_reference_text(text)
    if not normalized:
        return
    for paragraph in normalized.split("\n\n"):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        if _all_list_items(lines):
            yield ReferenceTextSegment(
                kind="list",
                lines=tuple(_strip_list_marker(line) for line in lines),
            )
        else:
            yield ReferenceTextSegment(kind="paragraph", lines=(" ".join(lines),))


def _normalize_line(line: str) -> str:
    line = _SPACES_RE.sub(" ", (line or "").strip())
    if not line:
        return ""
    line = _SERVICE_PREFIX_RE.sub("", line).strip()
    line = re.sub(r"\s+([,.;:!?])", r"\1", line)
    line = re.sub(r"([«(\[])\s+", r"\1", line)
    line = re.sub(r"\s+([»)\]])", r"\1", line)
    line = re.sub(r"([№§])\s+", r"\1 ", line)
    line = re.sub(r"\b([А-ЯЁа-яё])\s+-\s*([А-ЯЁа-яё])", r"\1-\2", line)
    return line.strip()


def _all_list_items(lines: list[str]) -> bool:
    return bool(lines) and all(_LIST_MARKER_RE.match(line) for line in lines)


def _normalize_list_item(line: str) -> str:
    match = _LIST_MARKER_RE.match(line)
    if not match:
        return line
    marker = match.group("marker")
    body = match.group("body").strip()
    if marker in {"•", "●", "·", "*", "-", "–", "—"}:
        return f"- {body}"
    return f"{marker} {body}"


def _strip_list_marker(line: str) -> str:
    match = _LIST_MARKER_RE.match(line)
    if not match:
        return line
    return match.group("body").strip()


def _split_mixed_paragraph(lines: list[str]) -> list[str]:
    parts: list[str] = []
    prose: list[str] = []
    list_items: list[str] = []

    def flush_prose() -> None:
        nonlocal prose
        if prose:
            parts.append(" ".join(prose).strip())
            prose = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            parts.append("\n".join(_normalize_list_item(item) for item in list_items))
            list_items = []

    for line in lines:
        if _LIST_MARKER_RE.match(line):
            flush_prose()
            list_items.append(line)
            continue
        if list_items:
            list_items[-1] = f"{list_items[-1]} {line}"
            continue
        prose.append(line)

    flush_prose()
    flush_list()
    return [part for part in parts if part]
