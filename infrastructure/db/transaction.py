"""Явная транзакция для цепочки операций через несколько репозиториев.

Наши repository-методы исторически коммитят сами (`self.connection.commit()`).
Это удобно для одиночных вызовов, но ломает атомарность, когда сервис делает
несколько `save_*()` подряд: сбой посередине оставляет БД в полусостоянии.

`atomic(connection)` подменяет `connection.commit()` no-op'ом, пока идёт блок,
и окружает всё явным `BEGIN IMMEDIATE` + `COMMIT`/`ROLLBACK`. Это позволяет
переиспользовать существующие репозитории без массового рефакторинга.

Пример:

    with atomic(self.connection):
        self.repository.save_sources(sources)
        self.repository.replace_claims(project_id, claims)
        self.repository.replace_outline(project_id, "7", segments)
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def atomic(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    # Полагается на AppConnection из infrastructure/db/connection.py.
    # Stock sqlite3.Connection не поддерживает `_suppress_commit` и упадёт.
    was_suppressed = getattr(connection, "_suppress_commit", False)
    connection.execute("BEGIN IMMEDIATE")
    connection._suppress_commit = True  # type: ignore[attr-defined]
    try:
        yield connection
    except Exception:
        connection._suppress_commit = was_suppressed  # type: ignore[attr-defined]
        connection.rollback()
        raise
    else:
        connection._suppress_commit = was_suppressed  # type: ignore[attr-defined]
        connection.commit()
