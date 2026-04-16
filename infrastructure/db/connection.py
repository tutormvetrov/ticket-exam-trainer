from __future__ import annotations

from pathlib import Path
import sqlite3

from infrastructure.db.schema import initialize_schema

SQLITE_TIMEOUT_SECONDS = 15.0
SQLITE_BUSY_TIMEOUT_MS = 15_000


class AppConnection(sqlite3.Connection):
    """Расширение sqlite3.Connection, поддерживающее временное подавление commit.

    Нужно для `atomic()` context-manager'а: репозитории исторически делают
    `self.connection.commit()` внутри save/replace-методов. Когда вызывающий
    сервис хочет объединить серию save'ов в одну транзакцию, он выставляет
    `connection._suppress_commit = True`, и все вложенные commit() становятся
    no-op до конца блока.
    """

    _suppress_commit: bool = False

    def commit(self) -> None:  # type: ignore[override]
        if self._suppress_commit:
            return
        super().commit()


def get_database_path(base_dir: Path) -> Path:
    return base_dir / "exam_trainer.db"


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=SQLITE_TIMEOUT_SECONDS, factory=AppConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def connect_initialized(database_path: Path) -> sqlite3.Connection:
    connection = connect(database_path)
    initialize_schema(connection)
    return connection
