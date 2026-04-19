"""Extract raw ticket bundles from existing seed v1 DB for Codex to structure.

Uses seed v1 (state_exam_public_admin_demo.db) as source of 208 ticket titles
+ whatever raw content the old import pipeline captured. Codex consumes this
JSON and produces structured, high-quality output; for tickets where seed v1
content is garbage (bullet markers, fragments), Codex generates best-effort
from title.

Output: build/codex_input/raw_tickets.json

Usage:
    python scripts/codex/extract_raw_tickets.py
    python scripts/codex/extract_raw_tickets.py --seed-db <path>
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = REPO_ROOT / "build" / "demo_seed" / "state_exam_public_admin_demo.db"
OUT_PATH = REPO_ROOT / "build" / "codex_input" / "raw_tickets.json"

# Порог, ниже которого считаем content мусорным (пустые/bullet-only)
GARBAGE_THRESHOLD_CHARS = 100


def _load_section_title(conn: sqlite3.Connection, section_id: str | None) -> str:
    if not section_id:
        return ""
    row = conn.execute(
        "SELECT title FROM sections WHERE section_id = ?", (section_id,)
    ).fetchone()
    return row[0] if row else ""


def _load_document(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT document_id, title, file_path FROM source_documents LIMIT 1"
    ).fetchone()
    if not row:
        return {"source_filename": "", "display_title": ""}
    doc_id, title, file_path = row
    filename = Path(file_path).name if file_path else ""
    return {
        "document_id": doc_id,
        "source_filename": filename,
        "raw_title": title,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-db", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)

    if not args.seed_db.exists():
        print(f"ERROR: seed DB not found at {args.seed_db}", file=sys.stderr)
        return 1

    print(f"Reading seed v1 from {args.seed_db.name}...")
    conn = sqlite3.connect(f"file:{args.seed_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    document = _load_document(conn)

    rows = list(conn.execute("""
        SELECT ticket_id, title, canonical_answer_summary, section_id,
               difficulty, estimated_oral_time_sec
        FROM tickets
        ORDER BY ticket_id
    """))
    print(f"  Found {len(rows)} tickets")

    tickets = []
    garbage_count = 0
    for i, r in enumerate(rows, start=1):
        summary = r["canonical_answer_summary"] or ""
        section_title = _load_section_title(conn, r["section_id"])

        is_garbage = len(summary.strip()) < GARBAGE_THRESHOLD_CHARS
        if is_garbage:
            garbage_count += 1

        # Extract atoms to provide Codex with additional signal (may help structuring)
        atoms_rows = list(conn.execute(
            "SELECT atom_type, label, text FROM atoms WHERE ticket_id = ? ORDER BY order_index",
            (r["ticket_id"],)
        ))
        atoms_raw = [
            {"atom_type": a["atom_type"], "label": a["label"], "text": a["text"] or ""}
            for a in atoms_rows
        ]

        tickets.append({
            "ticket_number": i,
            "ticket_id": r["ticket_id"],
            "raw_title": r["title"],
            "raw_content": summary,
            "section_raw": section_title,
            "difficulty_hint": r["difficulty"],
            "atoms_hint": atoms_raw,  # старые атомы v1 — Codex может использовать как signal, но переработать
            "char_length": len(summary),
            "is_garbage_input": is_garbage,
        })

    conn.close()

    # Stats
    lengths = sorted(t["char_length"] for t in tickets)
    print(f"  Content length — min: {lengths[0]}, median: {lengths[len(lengths)//2]}, max: {lengths[-1]}")
    print(f"  Garbage (< {GARBAGE_THRESHOLD_CHARS} chars): {garbage_count}/{len(rows)}")
    print(f"  Substantive (≥ 500): {sum(1 for ln in lengths if ln >= 500)}/{len(rows)}")

    output = {
        "document": document,
        "extracted_at": "2026-04-18",
        "source_seed_db": str(args.seed_db.relative_to(REPO_ROOT)),
        "notes": (
            "Тикеты извлечены из seed v1. "
            f"{garbage_count} из {len(rows)} билетов имеют content < {GARBAGE_THRESHOLD_CHARS} символов "
            "(парсер v1 не справился, типично '● (N) N' артефакты). "
            "Codex должен для них сгенерировать best-effort канонический ответ по title + "
            "общему знанию предмета, пометив warnings: ['source_is_toc_artifact']. "
            "Для остальных — использовать raw_content как опорный текст, чистить байлайны, "
            "переосмысливать атомы. atoms_hint — сырые атомы v1, часто разорванные на "
            "токенах-аббревиатурах, брать как сигнал о границах, но перепроизводить целостно."
        ),
        "tickets": tickets,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ Wrote {args.output.relative_to(REPO_ROOT)} ({args.output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
