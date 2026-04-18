from __future__ import annotations

from pathlib import Path

import pytest

from app.release_seed import resolve_seed_database


def test_release_seed_returns_none_without_explicit_path() -> None:
    assert resolve_seed_database(None) is None
    assert resolve_seed_database("") is None


def test_release_seed_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        resolve_seed_database(tmp_path / "missing.db")


def test_release_seed_rejects_empty_file(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.db"
    empty_db.write_bytes(b"")

    with pytest.raises(ValueError, match="empty"):
        resolve_seed_database(empty_db)


def test_release_seed_accepts_existing_nonempty_file(tmp_path: Path) -> None:
    seeded_db = tmp_path / "seed.db"
    seeded_db.write_bytes(b"sqlite-data")

    assert resolve_seed_database(seeded_db) == seeded_db.resolve()


def test_release_seed_no_longer_exposes_repo_default_helpers() -> None:
    import app.release_seed as module

    assert not hasattr(module, "default_release_seed_target")
    assert not hasattr(module, "resolve_default_seed_database")
    assert not hasattr(module, "DEFAULT_RELEASE_SEED_RELATIVE")
