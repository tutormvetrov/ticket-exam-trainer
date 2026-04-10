from __future__ import annotations

from pathlib import Path
import sqlite3

from infrastructure.db.schema import initialize_schema


def get_database_path(base_dir: Path) -> Path:
    return base_dir / "exam_trainer.db"


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def connect_initialized(database_path: Path) -> sqlite3.Connection:
    connection = connect(database_path)
    initialize_schema(connection)
    return connection
