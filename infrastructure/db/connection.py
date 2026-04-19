from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from infrastructure.db.schema import initialize_schema

SQLITE_TIMEOUT_SECONDS = 15.0
SQLITE_BUSY_TIMEOUT_MS = 15_000


class AppConnection(sqlite3.Connection):
    """Расширение sqlite3.Connection — подавление commit + сериализация atomic().

    Два расширения:

    1. ``_suppress_commit`` — нужно для ``atomic()`` context-manager'а:
       репозитории исторически делают ``self.connection.commit()`` внутри
       save/replace-методов. Когда вызывающий сервис хочет объединить серию
       save'ов в одну транзакцию, он выставляет ``_suppress_commit = True``,
       и все вложенные commit() становятся no-op до конца блока.

    2. ``_txn_lock`` (RLock) — соединение живёт с ``check_same_thread=False``
       и реально шарится между UI- и worker-потоками. Без сериализации два
       ``atomic()`` могли бы стартовать вложенный ``BEGIN IMMEDIATE``
       (SQLite ругается ``cannot start a transaction within a transaction``)
       или затирать друг другу ``_suppress_commit``. RLock даёт взаимное
       исключение для транзакционных блоков, при этом оставляет возможность
       вложенного ``atomic()`` в одном потоке. Инициализируется в ``connect()``.
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
    connection = sqlite3.connect(database_path, timeout=SQLITE_TIMEOUT_SECONDS, factory=AppConnection, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # RLock нужен для сериализации atomic()-блоков между потоками. См. docstring AppConnection.
    connection._txn_lock = threading.RLock()  # type: ignore[attr-defined]
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def connect_initialized(database_path: Path) -> sqlite3.Connection:
    connection = connect(database_path)
    initialize_schema(connection)
    return connection
