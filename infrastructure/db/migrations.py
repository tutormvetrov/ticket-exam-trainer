"""Простая миграционная система для SQLite.

Принципы:
- `SCHEMA_BASELINE_VERSION` — версия, которую создаёт `initialize_schema`
  на пустой БД (идемпотентный bootstrap). Менять её нельзя: существующие
  инсталляции отметили этим числом свою схему.
- `MIGRATIONS[version]` — функции, которые поднимают схему с `version-1`
  на `version`. Первая новая миграция должна быть `SCHEMA_BASELINE_VERSION + 1`.
- Каждая миграция запускается в отдельной транзакции. При падении миграции
  состояние БД откатывается до версии, которая была перед её запуском.
- Downgrade не поддерживается: если БД новее приложения, это ошибка.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

SCHEMA_BASELINE_VERSION = 7


class SchemaDowngradeError(RuntimeError):
    """База данных сохранена более новой версией приложения, чем запущена сейчас."""


# Регистр миграций: {версия: функция(connection)->None}
# Функция не должна сама звать commit/rollback — runner обёрнет её в транзакцию.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def latest_schema_version() -> int:
    return max(SCHEMA_BASELINE_VERSION, max(MIGRATIONS.keys(), default=0))


def current_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def run_pending_migrations(connection: sqlite3.Connection) -> list[int]:
    """Прогнать все зарегистрированные миграции выше текущей версии.

    Возвращает список применённых версий (пустой, если всё актуально).
    """
    target = latest_schema_version()
    current = current_schema_version(connection)
    if current > target:
        raise SchemaDowngradeError(
            f"База данных использует schema_version={current}, "
            f"но приложение знает только до версии {target}. "
            "Возможно, файл создан более новой версией приложения. "
            "Не запускайте эту версию на нём."
        )
    applied: list[int] = []
    for version in sorted(MIGRATIONS):
        if version <= current:
            continue
        if version > target:
            # Не должно происходить, но на всякий случай.
            break
        migration = MIGRATIONS[version]
        # Каждая миграция — отдельная транзакция.
        connection.execute("BEGIN")
        try:
            migration(connection)
            _set_schema_version(connection, version)
        except Exception:
            connection.rollback()
            raise
        connection.commit()
        applied.append(version)
    return applied
