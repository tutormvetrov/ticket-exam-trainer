from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.db import connect_initialized, get_database_path
from infrastructure.db.migrations import (
    MIGRATIONS,
    SCHEMA_BASELINE_VERSION,
    SchemaDowngradeError,
    current_schema_version,
    latest_schema_version,
    run_pending_migrations,
)
from infrastructure.db.schema import initialize_schema


def test_empty_db_is_initialized_at_baseline_version(tmp_path: Path) -> None:
    db_path = get_database_path(tmp_path)
    connection = connect_initialized(db_path)
    try:
        assert current_schema_version(connection) == SCHEMA_BASELINE_VERSION
    finally:
        connection.close()


def test_initializing_existing_db_is_idempotent(tmp_path: Path) -> None:
    db_path = get_database_path(tmp_path)
    first = connect_initialized(db_path)
    first.close()
    second = connect_initialized(db_path)
    try:
        assert current_schema_version(second) == SCHEMA_BASELINE_VERSION
    finally:
        second.close()


def test_downgrade_is_rejected(tmp_path: Path) -> None:
    db_path = get_database_path(tmp_path)
    connection = connect_initialized(db_path)
    # Пользователь «пришёл» с более новой версии приложения.
    connection.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_BASELINE_VERSION + 99),),
    )
    connection.commit()
    connection.close()

    with pytest.raises(SchemaDowngradeError):
        initialize_schema(connect_raw_connection(db_path))


def test_run_pending_migrations_applies_registered_migrations(tmp_path: Path, monkeypatch) -> None:
    db_path = get_database_path(tmp_path)
    connection = connect_initialized(db_path)

    calls: list[int] = []

    def migration_7(conn: sqlite3.Connection) -> None:
        calls.append(7)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS migration_probe (value TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO migration_probe (value) VALUES ('v7')")

    monkeypatch.setitem(MIGRATIONS, SCHEMA_BASELINE_VERSION + 1, migration_7)

    applied = run_pending_migrations(connection)
    assert applied == [SCHEMA_BASELINE_VERSION + 1]
    assert calls == [7]
    assert current_schema_version(connection) == SCHEMA_BASELINE_VERSION + 1
    rows = connection.execute("SELECT value FROM migration_probe").fetchall()
    assert [row[0] for row in rows] == ["v7"]

    # Повторный запуск — no-op.
    calls.clear()
    applied_again = run_pending_migrations(connection)
    assert applied_again == []
    assert calls == []


def test_migration_failure_rolls_back_and_keeps_version(tmp_path: Path, monkeypatch) -> None:
    db_path = get_database_path(tmp_path)
    connection = connect_initialized(db_path)
    baseline = current_schema_version(connection)

    def broken_migration(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE broken_probe (value TEXT NOT NULL)")
        conn.execute("INSERT INTO broken_probe (value) VALUES ('before-fail')")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setitem(MIGRATIONS, baseline + 1, broken_migration)

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        run_pending_migrations(connection)

    # Версия не должна сдвинуться, и таблица не должна остаться.
    assert current_schema_version(connection) == baseline
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='broken_probe'"
    ).fetchone()
    assert tables is None


def test_latest_version_follows_registered_migrations(monkeypatch) -> None:
    monkeypatch.setitem(MIGRATIONS, SCHEMA_BASELINE_VERSION + 3, lambda conn: None)
    assert latest_schema_version() == SCHEMA_BASELINE_VERSION + 3


def connect_raw_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection
