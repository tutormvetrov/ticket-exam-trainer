from __future__ import annotations

from pathlib import Path

from application.admin_access import AdminAccessStore


def test_admin_access_store_sets_verifies_and_clears_password(tmp_path: Path) -> None:
    store = AdminAccessStore(tmp_path / "admin_access.json")

    state = store.load_state()
    assert state.configured is False
    assert store.verify_password("secret") is False

    store.set_password("secret-123", "рабочая подсказка")
    state = store.load_state()
    assert state.configured is True
    assert state.password_hint == "рабочая подсказка"
    assert store.verify_password("secret-123") is True
    assert store.verify_password("wrong") is False

    store.set_debug_mode(True)
    assert store.load_state().debug_mode is True

    store.clear_password()
    state = store.load_state()
    assert state.configured is False
    assert state.debug_mode is False
    assert state.password_hint == ""
