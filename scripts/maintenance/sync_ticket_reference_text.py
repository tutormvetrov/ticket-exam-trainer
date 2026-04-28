from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.ticket_reference import clean_ticket_title, compose_reference_answer, normalize_reference_text

DEFAULT_DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync ticket canonical summaries with cleaned state-exam answer blocks.",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database to update.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing them.")
    return parser.parse_args()


def sync_ticket_reference_text(db_path: Path, *, dry_run: bool = False) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        summaries_changed = 0
        titles_changed = 0
        blocks_changed = 0
        tickets_seen = 0

        for ticket_row in conn.execute("SELECT ticket_id, title, canonical_answer_summary FROM tickets ORDER BY ticket_id"):
            tickets_seen += 1
            ticket_id = ticket_row["ticket_id"]
            old_title = ticket_row["title"] or ""
            new_title = clean_ticket_title(old_title)
            if new_title and new_title != old_title:
                titles_changed += 1
                if not dry_run:
                    conn.execute(
                        """
                        UPDATE tickets
                        SET title = ?
                        WHERE ticket_id = ?
                        """,
                        (new_title, ticket_id),
                    )
            block_rows = conn.execute(
                """
                SELECT block_code, title, expected_content, is_missing
                FROM ticket_answer_blocks
                WHERE ticket_id = ?
                ORDER BY block_code
                """,
                (ticket_id,),
            ).fetchall()
            blocks = []
            for row in block_rows:
                old_content = row["expected_content"] or ""
                new_content = normalize_reference_text(old_content)
                if new_content != old_content:
                    blocks_changed += 1
                    if not dry_run:
                        conn.execute(
                            """
                            UPDATE ticket_answer_blocks
                            SET expected_content = ?
                            WHERE ticket_id = ? AND block_code = ?
                            """,
                            (new_content, ticket_id, row["block_code"]),
                        )
                blocks.append(
                    SimpleNamespace(
                        block_code=row["block_code"],
                        title=row["title"] or "",
                        expected_content=new_content,
                        is_missing=bool(row["is_missing"]),
                    )
                )

            ticket = SimpleNamespace(
                canonical_answer_summary=ticket_row["canonical_answer_summary"] or "",
                answer_blocks=blocks,
            )
            new_summary = compose_reference_answer(ticket)
            if new_summary != (ticket_row["canonical_answer_summary"] or ""):
                summaries_changed += 1
                if not dry_run:
                    conn.execute(
                        """
                        UPDATE tickets
                        SET canonical_answer_summary = ?
                        WHERE ticket_id = ?
                        """,
                        (new_summary, ticket_id),
                    )

        if not dry_run:
            conn.commit()
        return {
            "tickets_seen": tickets_seen,
            "titles_changed": titles_changed,
            "summaries_changed": summaries_changed,
            "blocks_changed": blocks_changed,
        }
    finally:
        conn.close()


def main() -> int:
    args = parse_args()
    stats = sync_ticket_reference_text(args.db, dry_run=args.dry_run)
    prefix = "DRY RUN: " if args.dry_run else ""
    print(
        f"{prefix}tickets={stats['tickets_seen']}; "
        f"titles_updated={stats['titles_changed']}; "
        f"canonical_updated={stats['summaries_changed']}; "
        f"blocks_normalized={stats['blocks_changed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
