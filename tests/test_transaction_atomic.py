from __future__ import annotations

import threading
from pathlib import Path

import pytest

from infrastructure.db import connect_initialized, get_database_path
from infrastructure.db.transaction import atomic


@pytest.fixture()
def connection(tmp_path: Path):
    conn = connect_initialized(get_database_path(tmp_path))
    conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def test_atomic_commits_on_success(connection) -> None:
    with atomic(connection):
        connection.execute("INSERT INTO probe (value) VALUES ('a')")
        connection.execute("INSERT INTO probe (value) VALUES ('b')")
    rows = [row[0] for row in connection.execute("SELECT value FROM probe ORDER BY id")]
    assert rows == ["a", "b"]


def test_atomic_rollbacks_on_exception(connection) -> None:
    connection.execute("INSERT INTO probe (value) VALUES ('pre')")
    connection.commit()

    with pytest.raises(RuntimeError, match="boom"):
        with atomic(connection):
            connection.execute("INSERT INTO probe (value) VALUES ('during')")
            raise RuntimeError("boom")

    rows = [row[0] for row in connection.execute("SELECT value FROM probe ORDER BY id")]
    assert rows == ["pre"]


def test_inner_commit_is_suppressed_during_atomic(connection) -> None:
    # Это тот случай, из-за которого нужна `atomic`: репозитории делают
    # connection.commit() внутри, и без подавления первый commit закрыл бы
    # транзакцию, оставив БД частично обновлённой при следующем падении.
    with pytest.raises(RuntimeError, match="boom"):
        with atomic(connection):
            connection.execute("INSERT INTO probe (value) VALUES ('x')")
            connection.commit()  # должно быть no-op внутри atomic
            connection.execute("INSERT INTO probe (value) VALUES ('y')")
            raise RuntimeError("boom")

    rows = [row[0] for row in connection.execute("SELECT value FROM probe ORDER BY id")]
    assert rows == []  # ВСЁ откатилось, включая запись после "commit"


def test_atomic_restores_suppress_flag(connection) -> None:
    assert getattr(connection, "_suppress_commit", False) is False
    with atomic(connection):
        assert connection._suppress_commit is True
    assert connection._suppress_commit is False


def test_atomic_serializes_across_threads(connection) -> None:
    """Two threads hammering atomic() on the shared connection must not clash.

    The connection lives with check_same_thread=False — without serialization
    both threads could race on `BEGIN IMMEDIATE` (nested-txn error) or on
    `_suppress_commit` (one thread resets the flag mid-flight of the other).
    """
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker(tag: str) -> None:
        try:
            barrier.wait(timeout=2.0)
            for i in range(50):
                with atomic(connection):
                    connection.execute(
                        "INSERT INTO probe (value) VALUES (?)", (f"{tag}{i}",)
                    )
        except BaseException as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=("a",), daemon=True)
    t2 = threading.Thread(target=worker, args=("b",), daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"atomic clashed under concurrent use: {errors!r}"
    rows = connection.execute("SELECT COUNT(*) FROM probe").fetchone()[0]
    assert rows == 100
