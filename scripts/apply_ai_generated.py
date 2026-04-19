"""Apply Claude-generated AI-course content batches to the seed DB.

Each batch is a JSON file under build/ai-generated/ with this shape:

    [
      {
        "discipline_code": "1.1",
        "discipline_title": "Иностранный язык",
        "discipline_lecturer": "Беликова Евгения Константиновна, ВШГА МГУ, доцент",
        "ticket_num": 1,
        "title": "Государственное устройство Российской Федерации и других государств",
        "canonical_answer_summary": "Короткая аннотация 1-2 предложения для карточки.",
        "blocks": {
          "intro": {"title": "Введение", "content": "…"},
          "theory": {"title": "Теоретическая часть", "content": "…"},
          "practice": {"title": "Практическая часть", "content": "…"},
          "skills": {"title": "Навыки", "content": "…"},
          "conclusion": {"title": "Заключение", "content": "…"},
          "extra": {"title": "Дополнительные элементы", "content": "…"}
        }
      },
      …
    ]

Usage:
    python scripts/apply_ai_generated.py [batch1.json] [batch2.json] …
    # or with no args: apply every JSON in build/ai-generated/
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"
BATCH_DIR = REPO_ROOT / "build" / "ai-generated"
AI_PDF = REPO_ROOT / "3_1_MDE_IIiTsKvGA_2024_Kol_Konspekt_GMU_ot_03_05_2024.pdf"

AI_EXAM_ID = "exam-state-mde-ai-2024"
AI_EXAM_TITLE = "МДЭ ИИ и Цифровизация в ГА (2024)"
AI_EXAM_DESC = (
    "Государственный междисциплинарный экзамен по программе магистратуры «Искусственный "
    "интеллект и цифровые коммуникации в государственном администрировании», "
    "направление 38.04.04 ГМУ, ВШГА МГУ."
)
AI_DOC_ID = "doc-state-mde-ai-2024"
AI_DOC_TITLE = "МДЭ ИИ и Цифровизация в ГА (2024). Коллективный конспект ВШГА МГУ"
ANSWER_PROFILE_CODE = "state_exam_public_admin"

BLOCK_ORDER = ("intro", "theory", "practice", "skills", "conclusion", "extra")
BLOCK_TITLES = {
    "intro": "Введение",
    "theory": "Теоретическая часть",
    "practice": "Практическая часть",
    "skills": "Навыки",
    "conclusion": "Заключение",
    "extra": "Дополнительные элементы",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_hex(seed: str, length: int = 16) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:length]


def _section_id(discipline_code: str) -> str:
    return f"sec-ai-{_sha_hex('ai-disc::' + discipline_code, 16)}"


def _ticket_id(discipline_code: str, ticket_num: int, title: str) -> str:
    key = f"ai-tkt::{discipline_code}::{ticket_num}::{title}"
    return f"tkt-ai-{_sha_hex(key, 16)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_exam_and_source_document(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute("SELECT 1 FROM exams WHERE exam_id = ?", (AI_EXAM_ID,))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO exams (exam_id, title, description, total_tickets, subject_area)
            VALUES (?, ?, ?, 0, ?)
            """,
            (AI_EXAM_ID, AI_EXAM_TITLE, AI_EXAM_DESC, "Государственное и муниципальное управление"),
        )

    cur.execute("SELECT 1 FROM source_documents WHERE document_id = ?", (AI_DOC_ID,))
    if cur.fetchone() is None:
        if AI_PDF.exists():
            size_bytes = AI_PDF.stat().st_size
            checksum = _sha256(AI_PDF)
            file_path = str(AI_PDF)
        else:
            # PDF is git-ignored; downstream users won't have it. That's fine —
            # the seed only needs a valid source_document row to satisfy
            # tickets.source_document_id NOT NULL.
            size_bytes = 0
            checksum = ""
            file_path = "3_1_MDE_IIiTsKvGA_2024_Kol_Konspekt_GMU_ot_03_05_2024.pdf"
        cur.execute(
            """
            INSERT INTO source_documents (
                document_id, exam_id, answer_profile_code, title,
                file_path, file_type, size_bytes, checksum, imported_at,
                raw_text, status, warnings_json, used_llm_assist,
                ticket_total, tickets_llm_done, last_attempted_at, last_error
            ) VALUES (?, ?, ?, ?, ?, 'pdf', ?, ?, ?, '', 'structured', '[]', 0, 0, 0, ?, '')
            """,
            (
                AI_DOC_ID, AI_EXAM_ID, ANSWER_PROFILE_CODE, AI_DOC_TITLE,
                file_path, size_bytes, checksum, _now_iso(), _now_iso(),
            ),
        )


def _upsert_section(
    con: sqlite3.Connection,
    discipline_code: str,
    discipline_title: str,
    discipline_lecturer: str,
    order_index: int,
) -> str:
    section_id = _section_id(discipline_code)
    description = f"Преподаватель: {discipline_lecturer}" if discipline_lecturer else ""
    cur = con.cursor()
    cur.execute("SELECT 1 FROM sections WHERE section_id = ?", (section_id,))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO sections (section_id, exam_id, title, order_index, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (section_id, AI_EXAM_ID, discipline_title, order_index, description),
        )
    else:
        cur.execute(
            "UPDATE sections SET title = ?, order_index = ?, description = ? WHERE section_id = ?",
            (discipline_title, order_index, description, section_id),
        )
    return section_id


def _estimate_oral_time(blocks: dict) -> int:
    """Rough oral-answer time estimate in seconds, 150 wpm."""
    total_chars = sum(len(b.get("content", "")) for b in blocks.values())
    # ~5 chars per word, 150 wpm → 50 chars/sec reading but oral exam is slower.
    words = total_chars / 5
    return max(180, int(words / 2.2))


def _upsert_ticket(con: sqlite3.Connection, record: dict, section_id: str) -> str:
    ticket_id = _ticket_id(record["discipline_code"], record["ticket_num"], record["title"])
    summary = record.get("canonical_answer_summary", "") or record.get("blocks", {}).get(
        "intro", {}
    ).get("content", "")[:500]
    summary = summary.strip()
    oral_time = _estimate_oral_time(record.get("blocks", {}))
    cur = con.cursor()
    cur.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (ticket_id,))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO tickets (
                ticket_id, exam_id, section_id, source_document_id, answer_profile_code,
                title, canonical_answer_summary, difficulty, estimated_oral_time_sec,
                source_confidence, status, llm_status, llm_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 3, ?, 1.0, 'structured', 'claude-regen', '')
            """,
            (
                ticket_id, AI_EXAM_ID, section_id, AI_DOC_ID, ANSWER_PROFILE_CODE,
                record["title"], summary, oral_time,
            ),
        )
    else:
        cur.execute(
            """
            UPDATE tickets
            SET title = ?,
                canonical_answer_summary = ?,
                estimated_oral_time_sec = ?,
                source_confidence = 1.0,
                status = 'structured',
                llm_status = 'claude-regen',
                llm_error = ''
            WHERE ticket_id = ?
            """,
            (record["title"], summary, oral_time, ticket_id),
        )
    return ticket_id


def _upsert_blocks(con: sqlite3.Connection, ticket_id: str, blocks: dict) -> None:
    cur = con.cursor()
    for code in BLOCK_ORDER:
        spec = blocks.get(code) or {}
        title = (spec.get("title") or BLOCK_TITLES[code]).strip() or BLOCK_TITLES[code]
        content = (spec.get("content") or "").strip()
        is_missing = 0 if content else 1
        cur.execute(
            "SELECT 1 FROM ticket_answer_blocks WHERE ticket_id = ? AND block_code = ?",
            (ticket_id, code),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO ticket_answer_blocks (
                    ticket_id, block_code, title, expected_content, source_excerpt,
                    confidence, llm_assisted, is_missing
                ) VALUES (?, ?, ?, ?, '', 1.0, 1, ?)
                """,
                (ticket_id, code, title, content, is_missing),
            )
        else:
            cur.execute(
                """
                UPDATE ticket_answer_blocks
                SET title = ?,
                    expected_content = ?,
                    confidence = 1.0,
                    llm_assisted = 1,
                    is_missing = ?
                WHERE ticket_id = ? AND block_code = ?
                """,
                (title, content, is_missing, ticket_id, code),
            )


_DISCIPLINE_ORDER = (
    "1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8",
    "2.9","2.10","2.11","2.12","2.13","2.14","2.15","2.16","2.17","2.18",
    "3.19","3.20","3.21","3.22","3.23","3.24","3.25","3.26",
)


def _order_index(code: str) -> int:
    try:
        return _DISCIPLINE_ORDER.index(code)
    except ValueError:
        return 99


def apply_batch(con: sqlite3.Connection, batch: list[dict]) -> dict:
    inserted = 0
    updated = 0
    skipped = 0
    touched_sections: set[str] = set()
    for record in batch:
        required = ("discipline_code", "discipline_title", "ticket_num", "title", "blocks")
        if not all(record.get(k) for k in required):
            skipped += 1
            continue
        section_id = _upsert_section(
            con,
            record["discipline_code"],
            record["discipline_title"],
            record.get("discipline_lecturer", ""),
            _order_index(record["discipline_code"]),
        )
        touched_sections.add(section_id)
        cur = con.cursor()
        cur.execute(
            "SELECT 1 FROM tickets WHERE ticket_id = ?",
            (_ticket_id(record["discipline_code"], record["ticket_num"], record["title"]),),
        )
        existed = cur.fetchone() is not None
        ticket_id = _upsert_ticket(con, record, section_id)
        _upsert_blocks(con, ticket_id, record["blocks"])
        if existed:
            updated += 1
        else:
            inserted += 1
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "sections_touched": len(touched_sections),
    }


def refresh_totals(con: sqlite3.Connection) -> dict:
    cur = con.cursor()
    n = cur.execute(
        "SELECT COUNT(*) FROM tickets WHERE exam_id = ?", (AI_EXAM_ID,)
    ).fetchone()[0]
    cur.execute("UPDATE exams SET total_tickets = ? WHERE exam_id = ?", (n, AI_EXAM_ID))
    cur.execute(
        "UPDATE source_documents SET ticket_total = ?, tickets_llm_done = ? WHERE document_id = ?",
        (n, n, AI_DOC_ID),
    )
    return {"ai_exam_tickets_total": n}


def main() -> int:
    if not SEED_DB.exists():
        print(f"Seed DB missing: {SEED_DB}", file=sys.stderr)
        return 1

    if len(sys.argv) > 1:
        batch_paths = [Path(p) for p in sys.argv[1:]]
    else:
        batch_paths = sorted(BATCH_DIR.glob("*.json")) if BATCH_DIR.exists() else []

    if not batch_paths:
        print(f"No batch files to apply (looked in {BATCH_DIR}).")
        return 0

    con = sqlite3.connect(str(SEED_DB))
    con.execute("PRAGMA foreign_keys = ON;")
    try:
        ensure_exam_and_source_document(con)
        grand = {"inserted": 0, "updated": 0, "skipped": 0}
        for path in batch_paths:
            batch = json.loads(path.read_text(encoding="utf-8"))
            stats = apply_batch(con, batch)
            print(
                f"{path.name}: inserted={stats['inserted']} updated={stats['updated']} "
                f"skipped={stats['skipped']} sections={stats['sections_touched']}"
            )
            for k in ("inserted", "updated", "skipped"):
                grand[k] += stats[k]
        totals = refresh_totals(con)
        con.commit()
        print(f"TOTAL: {grand}; {totals}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
