from __future__ import annotations

from pathlib import Path

from application.admin_access import AdminAccessStore
from application.dlc_license import DlcLicenseService
from application.interface_text_store import InterfaceTextStore
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore


def test_settings_store_falls_back_to_defaults_and_quarantines_invalid_json(tmp_path: Path) -> None:
    storage_path = tmp_path / "settings.json"
    storage_path.write_text("{broken", encoding="utf-8")

    store = SettingsStore(storage_path)
    settings = store.load()

    assert settings.base_url == DEFAULT_OLLAMA_SETTINGS.base_url
    assert settings.model == DEFAULT_OLLAMA_SETTINGS.model
    assert not storage_path.exists()
    assert list(tmp_path.glob("settings.corrupt-*.json"))


def test_admin_access_store_falls_back_to_empty_state_on_invalid_json(tmp_path: Path) -> None:
    storage_path = tmp_path / "admin_access.json"
    storage_path.write_text("[]", encoding="utf-8")

    store = AdminAccessStore(storage_path)
    state = store.load_state()

    assert state.configured is False
    assert state.debug_mode is False
    assert state.password_hint == ""
    assert not storage_path.exists()
    assert list(tmp_path.glob("admin_access.corrupt-*.json"))


def test_interface_text_store_ignores_invalid_json_payload(tmp_path: Path) -> None:
    storage_path = tmp_path / "ui_text_overrides.json"
    storage_path.write_text("42", encoding="utf-8")

    store = InterfaceTextStore(storage_path)

    assert store.load() == {}
    assert not storage_path.exists()
    assert list(tmp_path.glob("ui_text_overrides.corrupt-*.json"))


def test_dlc_license_service_treats_invalid_json_as_locked_state(tmp_path: Path) -> None:
    storage_path = tmp_path / "dlc_license.json"
    storage_path.write_text("{oops", encoding="utf-8")

    service = DlcLicenseService(storage_path)
    state = service.load_state()

    assert state.install_id == ""
    assert state.activated is False
    assert state.status == "locked"
    assert not storage_path.exists()
    assert list(tmp_path.glob("dlc_license.corrupt-*.json"))
