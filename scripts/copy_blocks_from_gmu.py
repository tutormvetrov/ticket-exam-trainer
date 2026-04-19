"""Duplicate GMU answer blocks into matching AI-course tickets.

Uses build/ai-extract/gmu_overlap.json produced by
scripts/find_ai_gmu_overlap.py. For every AI ticket with match_strategy
∈ {"exact_title", "fuzzy"}, we:

  1. ensure the AI ticket itself exists (create the section + ticket row
     mirroring scripts/apply_ai_generated.py's conventions);
  2. read the 6 answer blocks of the matched GMU ticket;
  3. upsert them onto the AI ticket, preserving titles / content.

Idempotent — re-running only refreshes content, never duplicates rows.
Respects an optional --skip-existing flag so already hand-generated AI
tickets (e.g. those already in build/ai-generated/) are left alone.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.apply_ai_generated import (  # reuse ticket/section helpers
    AI_DOC_ID,
    AI_EXAM_ID,
    ANSWER_PROFILE_CODE,
    BLOCK_ORDER,
    _order_index,
    _section_id,
    _ticket_id,
    ensure_exam_and_source_document,
    refresh_totals,
)

SEED_DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"
OVERLAP_JSON = REPO_ROOT / "build" / "ai-extract" / "gmu_overlap.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy matching GMU blocks into AI course tickets.")
    parser.add_argument(
        "--include-fuzzy",
        action="store_true",
        help="Also copy for match_strategy='fuzzy' (Jaccard ≥ 0.5). Default: only exact_title.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Leave AI tickets already present in the DB untouched (default on).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing AI tickets even if they already have blocks.",
    )
    return parser.parse_args()


def _ensure_section(con: sqlite3.Connection, discipline_code: str, discipline_title: str) -> str:
    section_id = _section_id(discipline_code)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM sections WHERE section_id = ?", (section_id,))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO sections (section_id, exam_id, title, order_index, description)
            VALUES (?, ?, ?, ?, '')
            """,
            (section_id, AI_EXAM_ID, discipline_title, _order_index(discipline_code)),
        )
    return section_id


def _ensure_ticket(
    con: sqlite3.Connection,
    section_id: str,
    discipline_code: str,
    ticket_num: int,
    title: str,
    canonical_summary: str,
    oral_time_sec: int,
) -> tuple[str, bool]:
    ticket_id = _ticket_id(discipline_code, ticket_num, title)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (ticket_id,))
    existed = cur.fetchone() is not None
    if not existed:
        cur.execute(
            """
            INSERT INTO tickets (
                ticket_id, exam_id, section_id, source_document_id, answer_profile_code,
                title, canonical_answer_summary, difficulty, estimated_oral_time_sec,
                source_confidence, status, llm_status, llm_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 3, ?, 1.0, 'structured', 'gmu-copy', '')
            """,
            (
                ticket_id, AI_EXAM_ID, section_id, AI_DOC_ID, ANSWER_PROFILE_CODE,
                title, canonical_summary, oral_time_sec,
            ),
        )
    return ticket_id, existed


def _copy_blocks(
    con: sqlite3.Connection, gmu_ticket_id: str, ai_ticket_id: str
) -> int:
    cur = con.cursor()
    rows = list(
        cur.execute(
            """
            SELECT block_code, title, expected_content, source_excerpt, confidence
              FROM ticket_answer_blocks
             WHERE ticket_id = ?
            """,
            (gmu_ticket_id,),
        )
    )
    if not rows:
        return 0
    written = 0
    for block_code, title, content, source_excerpt, confidence in rows:
        if block_code not in BLOCK_ORDER:
            continue
        is_missing = 0 if content else 1
        cur.execute(
            "SELECT 1 FROM ticket_answer_blocks WHERE ticket_id = ? AND block_code = ?",
            (ai_ticket_id, block_code),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO ticket_answer_blocks (
                    ticket_id, block_code, title, expected_content, source_excerpt,
                    confidence, llm_assisted, is_missing
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (ai_ticket_id, block_code, title, content, source_excerpt, confidence, is_missing),
            )
        else:
            cur.execute(
                """
                UPDATE ticket_answer_blocks
                SET title = ?, expected_content = ?, source_excerpt = ?, confidence = ?,
                    llm_assisted = 0, is_missing = ?
                WHERE ticket_id = ? AND block_code = ?
                """,
                (title, content, source_excerpt, confidence, is_missing, ai_ticket_id, block_code),
            )
        written += 1
    return written


def _read_gmu_summary(con: sqlite3.Connection, gmu_ticket_id: str) -> tuple[str, int]:
    cur = con.cursor()
    row = cur.execute(
        "SELECT canonical_answer_summary, estimated_oral_time_sec FROM tickets WHERE ticket_id = ?",
        (gmu_ticket_id,),
    ).fetchone()
    if row:
        return (row[0] or "", int(row[1] or 420))
    return ("", 420)


def main() -> int:
    args = _parse_args()
    if not SEED_DB.exists():
        print(f"Seed DB missing: {SEED_DB}", file=sys.stderr)
        return 1
    if not OVERLAP_JSON.exists():
        print("overlap JSON missing — run find_ai_gmu_overlap.py first", file=sys.stderr)
        return 1

    overlap = json.loads(OVERLAP_JSON.read_text(encoding="utf-8"))
    allowed_strategies = {"exact_title"}
    if args.include_fuzzy:
        allowed_strategies.add("fuzzy")

    relevant = [r for r in overlap if r["match_strategy"] in allowed_strategies and r["gmu_ticket_id"]]
    print(f"Candidates to copy: {len(relevant)} (strategies={sorted(allowed_strategies)})")

    con = sqlite3.connect(str(SEED_DB))
    con.execute("PRAGMA foreign_keys = ON;")
    try:
        ensure_exam_and_source_document(con)
        copied = 0
        skipped = 0
        updated = 0
        for r in relevant:
            section_id = _ensure_section(
                con,
                r["ai_discipline_code"],
                r["ai_discipline_title"],
            )
            canonical, oral_time = _read_gmu_summary(con, r["gmu_ticket_id"])
            ticket_id, existed = _ensure_ticket(
                con,
                section_id,
                r["ai_discipline_code"],
                r["ai_ticket_num"],
                r["ai_title"],
                canonical,
                oral_time,
            )
            if existed and not args.force:
                skipped += 1
                continue
            _copy_blocks(con, r["gmu_ticket_id"], ticket_id)
            if existed:
                updated += 1
            else:
                copied += 1
        totals = refresh_totals(con)
        con.commit()
        print(f"Copied new: {copied}")
        print(f"Updated existing: {updated}")
        print(f"Skipped (already exists, no --force): {skipped}")
        print(f"Totals: {totals}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
