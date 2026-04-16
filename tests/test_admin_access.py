from __future__ import annotations

import hashlib
from pathlib import Path

from app.json_storage import load_json_dict, save_json_dict
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


def test_new_password_uses_pbkdf2(tmp_path: Path) -> None:
    path = tmp_path / "admin_access.json"
    store = AdminAccessStore(path)
    store.set_password("secret-123")

    payload = load_json_dict(path)
    assert payload["algo"] == "pbkdf2_sha256"
    assert int(payload["iterations"]) >= 100_000
    # Убедимся, что это не голый SHA-256.
    salt = payload["salt"]
    legacy = hashlib.sha256(f"{salt}:secret-123".encode("utf-8")).hexdigest()
    assert payload["password_hash"] != legacy


def test_legacy_sha256_hash_is_verified_and_upgraded(tmp_path: Path) -> None:
    path = tmp_path / "admin_access.json"
    # Эмулируем хранилище, созданное старой версией приложения.
    salt = "abc123"
    legacy_hash = hashlib.sha256(f"{salt}:old-password".encode("utf-8")).hexdigest()
    save_json_dict(
        path,
        {
            "salt": salt,
            "password_hash": legacy_hash,
            "password_hint": "",
            "debug_mode": False,
        },
    )

    store = AdminAccessStore(path)
    assert store.verify_password("old-password") is True

    # После успешной проверки хэш должен быть переписан в PBKDF2.
    upgraded = load_json_dict(path)
    assert upgraded["algo"] == "pbkdf2_sha256"
    assert upgraded["password_hash"] != legacy_hash
    assert upgraded["salt"] != salt
    # Повторный вход по тому же паролю всё ещё работает.
    assert store.verify_password("old-password") is True
    assert store.verify_password("wrong") is False


def test_legacy_wrong_password_does_not_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "admin_access.json"
    salt = "abc123"
    legacy_hash = hashlib.sha256(f"{salt}:correct".encode("utf-8")).hexdigest()
    save_json_dict(
        path,
        {
            "salt": salt,
            "password_hash": legacy_hash,
            "password_hint": "",
            "debug_mode": False,
        },
    )

    store = AdminAccessStore(path)
    assert store.verify_password("wrong") is False

    after = load_json_dict(path)
    assert after.get("algo", "") != "pbkdf2_sha256"
    assert after["password_hash"] == legacy_hash
