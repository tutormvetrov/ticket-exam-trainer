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

RAW_PATH = REPO_ROOT / "build" / "ai-extract" / "raw.txt"
OUT_PATH = REPO_ROOT / "build" / "ai-extract" / "tickets.json"

# Discipline header start marker: "X.Y. " at beginning of line.
DISCIPLINE_START_RE = re.compile(r"(?:^|\n)\s*(?P<code>\d+\.\d+)\.\s+")

# Ticket header: "1. Вопрос…" OR "1 Вопрос…" (без точки — встречается в 2.12).
# Ограничение по длине и монотонности в post-processing не даёт ложным
# срабатываниям (номера глав, даты) прорваться.
TICKET_RE = re.compile(r"^\s*(?P<num>\d{1,2})\.?\s+(?P<title>\S[^\n]+?)\s*$", re.MULTILINE)


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


def parse(raw: str) -> list[dict]:
    body_start = _find_body_start(raw)
    body = raw[body_start:]
    body = _strip_page_noise(body)

    # Map offsets where each part starts.
    part_positions: dict[int, str] = {}
    for marker, part in PART_MARKERS.items():
        for m in re.finditer(re.escape(marker), body):
            part_positions[m.start()] = part

    # Find every discipline header.
    discipline_hits = _find_discipline_headers(body)
    if not discipline_hits:
        raise SystemExit("No discipline headers matched — check regex against raw.txt")

    tickets: list[dict] = []
    for idx, dhit in enumerate(discipline_hits):
        code = dhit["code"]
        d_title = dhit["title"]
        d_lecturer = dhit["lecturer"]
        start = dhit["end"]
        end = discipline_hits[idx + 1]["start"] if idx + 1 < len(discipline_hits) else len(body)
        discipline_body = body[start:end]
        part = _current_part(dhit["start"], part_positions)

        ticket_hits = list(TICKET_RE.finditer(discipline_body))
        # Filter: keep only tickets numbered 1..9 (max 9 tickets per discipline
        # in this конспект; higher numbers would be noise).
        ticket_hits = [
            m for m in ticket_hits
            if 1 <= int(m.group("num")) <= 9 and len(m.group("title").strip()) >= 4
        ]
        # Dedup consecutive headers (sometimes parser matches a reference to
        # ticket N inside another ticket's body).
        picked: list[re.Match] = []
        seen_nums: list[int] = []
        for m in ticket_hits:
            num = int(m.group("num"))
            # Enforce monotonic: ticket numbers within a discipline must
            # increase by 1; skip anything out-of-order.
            if not picked:
                if num != 1:
                    continue
                picked.append(m)
                seen_nums.append(num)
                continue
            if num == seen_nums[-1] + 1:
                picked.append(m)
                seen_nums.append(num)

        for j, tmatch in enumerate(picked):
            t_num = int(tmatch.group("num"))
            t_title = tmatch.group("title").strip().rstrip(".")
            t_start = tmatch.end()
            t_end = picked[j + 1].start() if j + 1 < len(picked) else len(discipline_body)
            raw_content = discipline_body[t_start:t_end].strip()
            tickets.append(
                {
                    "discipline_code": code,
                    "discipline_title": d_title,
                    "discipline_lecturer": d_lecturer,
                    "part": part,
                    "ticket_num": t_num,
                    "title": t_title,
                    "raw_content": raw_content,
                }
            )

    return tickets


def main() -> int:
    raw = RAW_PATH.read_text(encoding="utf-8")
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
