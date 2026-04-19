"""Parse the AI-course PDF (already extracted to raw.txt) into a structured
JSON of tickets with raw source content, ready for Claude-side regeneration.

Expected layout in raw.txt:

    ===== PAGE N =====
    … body text with discipline headers like
    "1.1. Иностранный язык (ФИО, ВШГА МГУ, доцент, …)"
    followed by "1. Вопрос", "2. Вопрос", …

The first ~6 pages are TOC / cover and must be skipped — the body
starts with the banner "I. ДИСЦИПЛИНЫ БАЗОВОЙ ЧАСТИ".

Output JSON shape:

    [
      {
        "discipline_code": "1.1",
        "discipline_title": "Иностранный язык",
        "discipline_lecturer": "Беликова …, ВШГА МГУ …",
        "part": "I",
        "ticket_num": 1,
        "title": "Государственное устройство Российской Федерации …",
        "raw_content": "<тело билета из конспекта>"
      },
      …
    ]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RAW_PATH_DEFAULT = REPO_ROOT / "build" / "ai-extract" / "raw.txt"
RAW_PATH_OCR = REPO_ROOT / "build" / "ai-extract" / "raw_with_ocr.txt"
OUT_PATH = REPO_ROOT / "build" / "ai-extract" / "tickets.json"

# Discipline header start marker: "X.Y. " at beginning of line.
DISCIPLINE_START_RE = re.compile(r"(?:^|\n)\s*(?P<code>\d+\.\d+)\.\s+")

# TOC ticket line:  "1. Название билета ...... 8"
# Dot-leaders + a trailing page number uniquely identify TOC items. Long
# titles can wrap onto the next line, so we allow the title to span lines
# via DOTALL — the dot-leaders + pagenum anchor catches them.
TOC_TICKET_RE = re.compile(
    r"(?:^|\n)\s*(?P<num>\d{1,2})\.?\s+(?P<title>[^\n].*?)\s*\.{5,}\s*(?P<page>\d+)(?=\s*\n|\s*$)",
    re.DOTALL,
)


def _split_title_and_lecturer(rest: str) -> tuple[str, str]:
    """Take the header body and split off the trailing (lecturer) group.
    The title may contain its own (...) like '(на иностранном языке)'; we
    pick the RIGHTMOST balanced '(...)'."""
    rest = rest.strip()
    if not rest.endswith(")"):
        return rest, ""
    depth = 0
    for i in range(len(rest) - 1, -1, -1):
        c = rest[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                return rest[:i].strip(), rest[i + 1 : -1].strip()
    return rest, ""


def _find_discipline_headers(body: str) -> list[dict]:
    """Scan body for 'X.Y. … (lecturer)' headers, tolerating line wraps
    inside the (lecturer) block. Returns dicts with code/title/lecturer
    plus start/end offsets in `body`."""
    results: list[dict] = []
    MAX_HEADER_LEN = 600  # safety cap so we don't eat whole chapters

    for start_match in DISCIPLINE_START_RE.finditer(body):
        code = start_match.group("code")
        rest_start = start_match.end()
        depth = 0
        opened = False
        end: int | None = None
        for i in range(rest_start, min(rest_start + MAX_HEADER_LEN, len(body))):
            c = body[i]
            if c == "(":
                depth += 1
                opened = True
            elif c == ")":
                depth -= 1
                if depth == 0 and opened:
                    end = i + 1
                    break
            elif c == "\n" and not opened:
                # Header ended without a lecturer bracket — not a real
                # discipline header, just a numeric list item.
                break
        if end is None:
            continue
        rest_text = body[rest_start:end].replace("\n", " ").strip()
        # Another sanity filter: reject if a new "X.Y." starts inside
        # the captured rest (means we overran into the next discipline).
        if re.search(r"\s\d+\.\d+\.\s", rest_text):
            continue
        title, lecturer = _split_title_and_lecturer(rest_text)
        if not lecturer:
            continue
        results.append(
            {
                "code": code,
                "title": title,
                "lecturer": lecturer,
                "start": start_match.start(),
                "end": end,
            }
        )
    return results
PAGE_BREAK_RE = re.compile(r"\n\n===== PAGE \d+ =====\n")
PAGE_NUM_LINE_RE = re.compile(r"^\s*\d+\s*$", re.MULTILINE)

BODY_START_MARKER = "I. ДИСЦИПЛИНЫ БАЗОВОЙ ЧАСТИ"
PART_MARKERS = {
    "I. ДИСЦИПЛИНЫ БАЗОВОЙ ЧАСТИ": "I",
    "II. ДИСЦИПЛИНЫ ВАРИАТИВНОЙ ЧАСТИ": "II",
    "III. ДИСЦИПЛИНЫ ПО ВЫБОРУ": "III",
}


def _strip_page_noise(text: str) -> str:
    """Drop the '===== PAGE N =====' banners and standalone page numbers."""
    text = PAGE_BREAK_RE.sub("\n", text)
    text = PAGE_NUM_LINE_RE.sub("", text)
    return text


def _find_body_start(text: str) -> int:
    """Find the FIRST occurrence of the body marker *after* the TOC.

    TOC mentions these same markers, so we look for the occurrence that is
    followed by a discipline header within a small window.
    """
    # Simplest heuristic: skip the TOC by finding the SECOND occurrence of
    # the first body marker — the first is in the TOC, the second opens
    # the actual body.
    occurrences = [m.start() for m in re.finditer(re.escape(BODY_START_MARKER), text)]
    if len(occurrences) >= 2:
        return occurrences[1]
    if occurrences:
        return occurrences[0]
    return 0


def _current_part(text_so_far_offset: int, part_positions: dict[int, str]) -> str:
    best_part = "I"
    for pos, part in sorted(part_positions.items()):
        if pos <= text_so_far_offset:
            best_part = part
    return best_part


def _normalize_for_match(text: str) -> str:
    """Normalize title for robust substring matching: lowercase, drop
    punctuation, collapse whitespace, replace ё→е."""
    t = (text or "").lower().replace("ё", "е")
    t = re.sub(r"[«»\"()\[\]\.,;:!?\-–—/\\]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _parse_toc(toc_text: str) -> dict[str, list[tuple[int, str]]]:
    """Parse the TOC into {discipline_code: [(num, title), ...]}.

    Walks discipline headers in TOC order, collects TOC_TICKET_RE matches
    between consecutive discipline headers.
    """
    toc: dict[str, list[tuple[int, str]]] = {}
    disc_hits = _find_discipline_headers(toc_text)
    for idx, d in enumerate(disc_hits):
        code = d["code"]
        start = d["end"]
        end = disc_hits[idx + 1]["start"] if idx + 1 < len(disc_hits) else len(toc_text)
        chunk = toc_text[start:end]
        entries: list[tuple[int, str]] = []
        for m in TOC_TICKET_RE.finditer(chunk):
            num = int(m.group("num"))
            title = m.group("title")
            # Collapse multi-line wraps inside the title (TOC often breaks
            # long titles across 2–3 lines before the dot-leaders).
            title = re.sub(r"\s+", " ", title).strip().rstrip(".")
            if 1 <= num <= 9 and len(title) >= 4:
                entries.append((num, title))
        # Dedup keeping the first hit per number.
        seen: set[int] = set()
        unique: list[tuple[int, str]] = []
        for num, title in entries:
            if num in seen:
                continue
            seen.add(num)
            unique.append((num, title))
        if unique:
            # Keep the LAST TOC entry for each discipline code (sometimes
            # headers appear on the cover and again in the real TOC — we
            # want the real one with ticket lines).
            toc[code] = unique
    return toc


def parse(raw: str) -> list[dict]:
    body_start = _find_body_start(raw)
    toc_text = _strip_page_noise(raw[:body_start])
    body = _strip_page_noise(raw[body_start:])

    # TOC is the authoritative source of ticket titles. We then locate
    # each TOC-listed title in the body and carve the ticket's content
    # between consecutive title positions.
    toc = _parse_toc(toc_text)
    if not toc:
        raise SystemExit("TOC parsing yielded no tickets — check the TOC regex.")

    # Map offsets where each part starts.
    part_positions: dict[int, str] = {}
    for marker, part in PART_MARKERS.items():
        for m in re.finditer(re.escape(marker), body):
            part_positions[m.start()] = part

    # Find every discipline header in the BODY.
    body_disc_hits = _find_discipline_headers(body)
    if not body_disc_hits:
        raise SystemExit("No discipline headers found in body.")

    tickets: list[dict] = []
    for idx, dhit in enumerate(body_disc_hits):
        code = dhit["code"]
        d_title = dhit["title"]
        d_lecturer = dhit["lecturer"]
        start = dhit["end"]
        end = body_disc_hits[idx + 1]["start"] if idx + 1 < len(body_disc_hits) else len(body)
        discipline_body = body[start:end]
        part = _current_part(dhit["start"], part_positions)

        expected = toc.get(code, [])
        if not expected:
            continue

        # For each (num, title) from TOC, find its position in discipline_body
        # by normalized substring search. Normalize body the same way, but
        # preserve a mapping back to raw offsets via per-character index.
        norm_body, norm_to_raw = _normalize_with_offsets(discipline_body)

        positions: list[tuple[int, str, int]] = []  # (raw_start, title, num)
        search_from = 0
        for num, title in expected:
            norm_title = _normalize_for_match(title)
            if len(norm_title) < 4:
                continue
            idx_norm = norm_body.find(norm_title, search_from)
            if idx_norm < 0:
                # Try harder: first-half match for long titles that got
                # line-wrapped inside body with hyphenation etc.
                half = norm_title[: max(20, len(norm_title) // 2)]
                idx_norm = norm_body.find(half, search_from)
            if idx_norm < 0:
                # Still nothing — keep going with a placeholder so the
                # ticket is still emitted (content will be empty).
                positions.append((-1, title, num))
                continue
            raw_pos = norm_to_raw[idx_norm]
            # The header line itself ends at the next newline; content starts there.
            newline_after = discipline_body.find("\n", raw_pos)
            content_start = newline_after + 1 if newline_after != -1 else raw_pos + len(title)
            positions.append((content_start, title, num))
            search_from = idx_norm + len(norm_title)

        # Build raw_content: between current ticket's content_start and next
        # ticket's header start (raw_pos of next). For the last, until
        # discipline end.
        # We need raw_pos for slicing upper bound. Compute again:
        header_raws: list[int] = []
        for p_start, _title, _num in positions:
            # Recompute header raw position — simpler: scan for the first
            # 'num.' occurrence near p_start. Fall back to p_start itself.
            header_raws.append(p_start)
        for j, (content_start, title, num) in enumerate(positions):
            if content_start < 0:
                raw_content = ""
            else:
                upper = header_raws[j + 1] if j + 1 < len(positions) and header_raws[j + 1] > 0 else len(discipline_body)
                raw_content = discipline_body[content_start:upper].strip()
            tickets.append(
                {
                    "discipline_code": code,
                    "discipline_title": d_title,
                    "discipline_lecturer": d_lecturer,
                    "part": part,
                    "ticket_num": num,
                    "title": title,
                    "raw_content": raw_content,
                }
            )

    return tickets


def _normalize_with_offsets(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, offsets) where offsets[i] gives the
    original index in `text` corresponding to normalized_text[i]."""
    out_chars: list[str] = []
    out_offsets: list[int] = []
    last_was_space = True  # collapse leading whitespace
    for i, c in enumerate(text):
        ch = c.lower().replace("ё", "е")
        if ch in "«»\"()[].,;:!?-–—/\\":
            ch = " "
        if ch.isspace():
            if last_was_space:
                continue
            out_chars.append(" ")
            out_offsets.append(i)
            last_was_space = True
        else:
            out_chars.append(ch)
            out_offsets.append(i)
            last_was_space = False
    return "".join(out_chars), out_offsets


def main() -> int:
    # Prefer OCR-enriched source if available — it catches text stuck in
    # scanned screenshots and formula images that plain pdftotext misses.
    source = RAW_PATH_OCR if RAW_PATH_OCR.exists() else RAW_PATH_DEFAULT
    print(f"Parsing from: {source.name}")
    raw = source.read_text(encoding="utf-8")
    tickets = parse(raw)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Quick stats.
    by_discipline: dict[str, int] = {}
    for t in tickets:
        by_discipline[t["discipline_code"]] = by_discipline.get(t["discipline_code"], 0) + 1
    print(f"Parsed {len(tickets)} tickets across {len(by_discipline)} disciplines")
    print(f"Saved: {OUT_PATH}")
    print("\nBy discipline:")
    for code in sorted(by_discipline):
        first = next((t for t in tickets if t["discipline_code"] == code), None)
        title = first["discipline_title"] if first else "?"
        print(f"  {code:5s} ({by_discipline[code]}): {title}")

    # Sanity: content length distribution.
    lens = sorted(len(t["raw_content"]) for t in tickets)
    if lens:
        median = lens[len(lens) // 2]
        print(f"\nraw_content length — min: {lens[0]}, median: {median}, max: {lens[-1]}")
        shorts = [t for t in tickets if len(t["raw_content"]) < 200]
        if shorts:
            print(f"WARNING: {len(shorts)} tickets have <200 chars raw content:")
            for t in shorts[:5]:
                print(f"  {t['discipline_code']}/{t['ticket_num']}: {t['title'][:60]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
