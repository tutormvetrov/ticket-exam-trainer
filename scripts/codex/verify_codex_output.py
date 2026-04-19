"""Verify structured tickets JSON from Codex meets quality bar.

Checks:
- All 208 tickets present (or close to expected count)
- canonical_answer_summary ≥ 800 chars (unless warnings say insufficient source)
- exactly 6 answer_blocks per ticket with correct labels
- 3-5 reference_theses per ticket, each 80-300 chars
- No byline leaks in any text field
- Atom types from enum, labels ≤ 30 chars
- Section metadata present

Exit non-zero on any violation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "build" / "codex_output" / "structured_tickets.json"

EXPECTED_ANSWER_BLOCK_LABELS = [
    "Введение", "Определения", "Классификация",
    "Механизм", "Примеры", "Заключение",
]
VALID_ATOM_TYPES = {
    "definition", "features", "classification",
    "example", "context", "mechanism", "consequence",
}
BYLINE_PATTERNS = [
    re.compile(r"^\s*\([А-ЯЁ]"),
    re.compile(r"^\s*Автор:"),
    re.compile(r"^\s*Выполнил[а]?:"),
]


class Violation(Exception):
    pass


def _check_no_byline(text: str, location: str) -> list[str]:
    issues = []
    for pat in BYLINE_PATTERNS:
        if pat.match(text):
            issues.append(f"{location}: byline-like prefix in text: {text[:80]!r}")
    return issues


def verify_ticket(t: dict, idx: int) -> list[str]:
    errors: list[str] = []
    loc = f"ticket[{idx}] #{t.get('ticket_number', '?')}"

    # Required fields
    for field in ("ticket_number", "title", "canonical_answer_summary",
                  "section", "atoms", "answer_blocks", "reference_theses"):
        if field not in t:
            errors.append(f"{loc}: missing field '{field}'")

    if errors:
        return errors  # bail on severe missing fields

    warnings = set(t.get("warnings") or [])

    # Content length
    summary = t["canonical_answer_summary"] or ""
    if "source_is_toc_artifact" not in warnings and "source_fragmented" not in warnings:
        if len(summary) < 800:
            errors.append(f"{loc}: canonical_answer_summary too short ({len(summary)} < 800)")
    if len(summary) > 5000:
        errors.append(f"{loc}: canonical_answer_summary unusually long ({len(summary)} > 5000)")

    errors.extend(_check_no_byline(summary, f"{loc}.canonical_answer_summary"))

    # Section
    section = t["section"] or {}
    if not section.get("title"):
        errors.append(f"{loc}: section.title missing")

    # Atoms
    atoms = t["atoms"] or []
    if len(atoms) < 3:
        errors.append(f"{loc}: only {len(atoms)} atoms (expect 3-10)")
    for i, a in enumerate(atoms):
        al = f"{loc}.atoms[{i}]"
        if a.get("atom_type") not in VALID_ATOM_TYPES:
            errors.append(f"{al}: invalid atom_type {a.get('atom_type')!r}")
        if not a.get("label") or len(a["label"]) > 30:
            errors.append(f"{al}: label missing or too long")
        if not a.get("text") or len(a["text"]) < 50:
            errors.append(f"{al}: text too short ({len(a.get('text') or '')} < 50)")
        errors.extend(_check_no_byline(a.get("text", ""), f"{al}.text"))

    # Answer blocks
    blocks = t["answer_blocks"] or []
    if len(blocks) != 6:
        errors.append(f"{loc}: {len(blocks)} answer_blocks, expected 6")
    else:
        labels = [b.get("label") for b in blocks]
        if labels != EXPECTED_ANSWER_BLOCK_LABELS:
            errors.append(f"{loc}: answer_blocks labels {labels} don't match expected order")
        for i, b in enumerate(blocks):
            bl = f"{loc}.answer_blocks[{i}]"
            text = b.get("text", "")
            if text and len(text) < 200 and "source_fragmented" not in warnings:
                errors.append(f"{bl}: text too short ({len(text)} < 200)")

    # Reference theses
    theses = t["reference_theses"] or []
    if not (3 <= len(theses) <= 5):
        errors.append(f"{loc}: {len(theses)} reference_theses, expected 3-5")
    for i, th in enumerate(theses):
        tl = f"{loc}.reference_theses[{i}]"
        text = th.get("text", "")
        if not (80 <= len(text) <= 300):
            errors.append(f"{tl}: text length {len(text)} outside 80-300")
        errors.extend(_check_no_byline(text, f"{tl}.text"))

    return errors


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--min-tickets", type=int, default=200,
                        help="Minimum expected ticket count (default 200 of 208)")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"ERROR: not found {args.path}", file=sys.stderr)
        return 2

    raw = args.path.read_text(encoding="utf-8")
    data = json.loads(raw)

    tickets = data if isinstance(data, list) else data.get("tickets")
    if not isinstance(tickets, list):
        print("ERROR: expected list of tickets or {tickets: [...]}", file=sys.stderr)
        return 2

    print(f"Loaded {len(tickets)} tickets from {args.path.relative_to(REPO_ROOT)}")

    if len(tickets) < args.min_tickets:
        print(f"❌ Only {len(tickets)} tickets, expected ≥{args.min_tickets}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    warnings_count = 0
    for i, t in enumerate(tickets):
        errs = verify_ticket(t, i)
        if errs:
            all_errors.extend(errs)
        if t.get("warnings"):
            warnings_count += 1

    if all_errors:
        print(f"\n❌ {len(all_errors)} violations found:", file=sys.stderr)
        for e in all_errors[:50]:
            print(f"  {e}", file=sys.stderr)
        if len(all_errors) > 50:
            print(f"  ... and {len(all_errors) - 50} more", file=sys.stderr)
        return 1

    print(f"\n✓ All {len(tickets)} tickets pass structural invariants")
    print(f"  {warnings_count} tickets carry explicit warnings (likely low-quality input)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
