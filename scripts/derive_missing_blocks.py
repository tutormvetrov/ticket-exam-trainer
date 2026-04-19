"""One-shot: дополнить недостающие answer-blocks из атомов.

Использование:
    python scripts/derive_missing_blocks.py            # на workspace-БД
    python scripts/derive_missing_blocks.py --db PATH  # произвольная БД
    python scripts/derive_missing_blocks.py --dry-run  # показать, что сделает

Скрипт идемпотентен: на повторных запусках существующие non-missing
блоки не трогает, заполняет только те, что ещё `is_missing = 1` И
могут быть derived из имеющихся атомов.

Пишет отчёт: сколько билетов затронуто, сколько блоков заполнено.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.paths import get_workspace_root
from application.block_derivation import derive_missing_blocks
from infrastructure.db import get_database_path

_LOG = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


class _AtomRow:
    """Минимальный wrapper поверх sqlite row — имеет .type, .label, .text, .atom_id."""

    def __init__(self, row: sqlite3.Row) -> None:
        self.atom_id = row["atom_id"]
        self.type = row["atom_type"]
        self.label = row["label"] or ""
        self.text = row["text"] or ""


class _BlockRow:
    def __init__(self, row: sqlite3.Row) -> None:
        self.block_code = row["block_code"]
        self.is_missing = bool(row["is_missing"])
        self.expected_content = row["expected_content"] or ""


def _load_ticket_atoms(conn: sqlite3.Connection, ticket_id: str) -> list[_AtomRow]:
    rows = conn.execute(
        "SELECT atom_id, atom_type, label, text FROM atoms WHERE ticket_id = ? ORDER BY atom_id",
        (ticket_id,),
    ).fetchall()
    return [_AtomRow(r) for r in rows]


def _load_ticket_blocks(conn: sqlite3.Connection, ticket_id: str) -> list[_BlockRow]:
    rows = conn.execute(
        "SELECT block_code, is_missing, expected_content FROM ticket_answer_blocks WHERE ticket_id = ?",
        (ticket_id,),
    ).fetchall()
    return [_BlockRow(r) for r in rows]


def _upsert_block(
    conn: sqlite3.Connection,
    ticket_id: str,
    block_code: str,
    title: str,
    expected_content: str,
) -> None:
    conn.execute(
        """
        UPDATE ticket_answer_blocks
        SET title = ?, expected_content = ?, is_missing = 0, confidence = MAX(confidence, 0.5)
        WHERE ticket_id = ? AND block_code = ?
        """,
        (title, expected_content, ticket_id, block_code),
    )


def run(database_path: Path, *, dry_run: bool) -> dict[str, int]:
    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row
    try:
        ticket_rows = conn.execute("SELECT ticket_id, title FROM tickets ORDER BY ticket_id").fetchall()
        touched_tickets = 0
        derived_blocks_total = 0
        for ticket_row in ticket_rows:
            ticket_id = ticket_row["ticket_id"]
            blocks = _load_ticket_blocks(conn, ticket_id)
            atoms = _load_ticket_atoms(conn, ticket_id)
            report = derive_missing_blocks(ticket_id, blocks, atoms)
            if report.count == 0:
                continue
            touched_tickets += 1
            derived_blocks_total += report.count
            if dry_run:
                _LOG.info(
                    "[dry-run] %s → %d derived (%s)",
                    ticket_id,
                    report.count,
                    ", ".join(b.block_code for b in report.derived_blocks),
                )
                continue
            for block in report.derived_blocks:
                _upsert_block(conn, ticket_id, block.block_code, block.title, block.expected_content)
            conn.commit()
        return {
            "tickets_total": len(ticket_rows),
            "tickets_touched": touched_tickets,
            "blocks_derived": derived_blocks_total,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive missing answer-blocks from atoms.")
    parser.add_argument("--db", type=Path, default=None, help="Путь к SQLite (по умолчанию — workspace-БД)")
    parser.add_argument("--dry-run", action="store_true", help="Не писать в БД — только отчёт")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG-логирование")
    args = parser.parse_args()

    _configure_logging(args.verbose)

    database_path = args.db or get_database_path(get_workspace_root())
    if not database_path.exists():
        _LOG.error("База не найдена: %s", database_path)
        sys.exit(1)

    _LOG.info("Derivation на %s (%s)", database_path, "dry-run" if args.dry_run else "write")
    stats = run(database_path, dry_run=args.dry_run)

    print()
    print(f"Tickets total:   {stats['tickets_total']}")
    print(f"Tickets touched: {stats['tickets_touched']}")
    print(f"Blocks derived:  {stats['blocks_derived']}")


if __name__ == "__main__":
    main()
