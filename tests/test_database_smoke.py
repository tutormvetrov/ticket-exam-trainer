from __future__ import annotations

from pathlib import Path

from infrastructure.db import connect_initialized


def test_database_schema_smoke(tmp_path: Path) -> None:
    database_path = tmp_path / "exam.db"
    connection = connect_initialized(database_path)
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    connection.close()
    assert "tickets" in tables
    assert "atoms" in tables
    assert "ticket_mastery_profiles" in tables
    assert "spaced_review_queue" in tables
