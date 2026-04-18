"""Pick 5 tickets with reasonable content for R0 review-engine validation.

Writes one JSON per ticket into tests/fixtures/review_validation/ticket_N.json.
Used by validate_review_engine.py to empirically test qwen3 tiers on the
«Рецензент» mode before committing to a default model.

Run once: python scripts/r0/pick_validation_tickets.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DB = REPO_ROOT / "build" / "demo_seed" / "state_exam_public_admin_demo.db"
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "review_validation"


def main() -> int:
    if not SEED_DB.exists():
        print(f"ERROR: seed DB not found at {SEED_DB}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{SEED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Берём 5 билетов с substantial content, фиксированным seed для воспроизводимости
    rows = list(conn.execute(
        """
        SELECT ticket_id, title, canonical_answer_summary
        FROM tickets
        WHERE LENGTH(canonical_answer_summary) >= 500
          AND canonical_answer_summary NOT LIKE '%Абдулаева%'  -- избегаем byline-problem tickets
        ORDER BY ticket_id
        LIMIT 5
        """
    ))

    if len(rows) < 5:
        print(f"ERROR: only {len(rows)} suitable tickets found, need 5", file=sys.stderr)
        return 1

    for i, row in enumerate(rows, start=1):
        ticket = {
            "ticket_id": row["ticket_id"],
            "title": row["title"],
            "canonical_answer_summary": row["canonical_answer_summary"],
        }
        out_path = OUT_DIR / f"ticket_{i}.json"
        out_path.write_text(
            json.dumps(ticket, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[{i}/5] {row['title'][:80]}")
        print(f"       -> {out_path.relative_to(REPO_ROOT)}")

    conn.close()
    print(f"\nDone. {len(rows)} tickets saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
