"""Window-mode persistence tests.

Verifies that ``OllamaSettings`` exposes the new fullscreen/windowed
fields with sane defaults, and that ``SettingsStore.load()`` tolerates
legacy ``settings.json`` files that predate these fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.settings_store import SettingsStore


def test_defaults_start_fullscreen() -> None:
    assert DEFAULT_OLLAMA_SETTINGS.window_mode == "fullscreen"
    assert DEFAULT_OLLAMA_SETTINGS.window_width == 1440
    assert DEFAULT_OLLAMA_SETTINGS.window_height == 900


def test_window_fields_types_and_defaults() -> None:
    settings = OllamaSettings()
    assert isinstance(settings.window_mode, str)
    assert isinstance(settings.window_width, int)
    assert isinstance(settings.window_height, int)
    assert settings.window_mode in ("fullscreen", "windowed")
    assert settings.ollama_enabled is True


def test_settings_store_load_tolerates_legacy_json(tmp_path: Path) -> None:
    """A settings.json without the window_* keys must still load."""
    legacy_path = tmp_path / "settings.json"
    legacy_path.write_text(
        json.dumps(
            {
                "base_url": "http://127.0.0.1:11434",
                "model": "qwen3:8b",
                "theme_name": "light",
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(legacy_path)
    settings = store.load()
    # Defaults fill in for missing keys
    assert settings.window_mode == "fullscreen"
    assert settings.window_width == 1440
    assert settings.window_height == 900


def test_settings_store_round_trip_preserves_window_mode(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    base = store.load()
    from dataclasses import replace

    modified = replace(base, window_mode="windowed", window_width=1600, window_height=1000)
    store.save(modified)

    loaded = store.load()
    assert loaded.window_mode == "windowed"
    assert loaded.window_width == 1600
    assert loaded.window_height == 1000


def test_settings_store_round_trip_preserves_style_and_gemini_fields(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    base = store.load()
    from dataclasses import replace

    modified = replace(
        base,
        theme_family="deco",
        gemini_api_key="test-key",
        gemini_model="gemini-2.5-pro",
    )
    store.save(modified)

    loaded = store.load()
    assert loaded.theme_family == "deco"
    assert loaded.gemini_api_key == "test-key"
    assert loaded.gemini_model == "gemini-2.5-pro"


def test_settings_store_round_trip_preserves_ollama_enabled(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    base = store.load()
    from dataclasses import replace

    modified = replace(base, ollama_enabled=False)
    store.save(modified)

    loaded = store.load()
    assert loaded.ollama_enabled is False


def test_settings_store_load_falls_back_on_empty_strings(tmp_path: Path) -> None:
    """If a user hand-edits settings.json with blanks, we still boot."""
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "window_mode": "",
                "window_width": None,
                "window_height": None,
            }
        ),
        encoding="utf-8",
    )
    settings = SettingsStore(path).load()
    assert settings.window_mode == "fullscreen"
    assert settings.window_width == 1440
    assert settings.window_height == 900
