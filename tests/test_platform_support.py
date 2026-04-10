from __future__ import annotations

from pathlib import Path

from app import paths
from app import platform as platform_helpers
from application.settings import OllamaSettings


def test_default_models_path_windows(monkeypatch) -> None:
    monkeypatch.setattr(platform_helpers.sys, "platform", "win32")
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(platform_helpers.Path, "exists", lambda self: str(self).startswith("D:"))
    assert platform_helpers.default_models_path() == Path(r"D:\OllamaModels")


def test_default_models_path_windows_falls_back_without_drive_d(monkeypatch) -> None:
    monkeypatch.setattr(platform_helpers.sys, "platform", "win32")
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(platform_helpers.Path, "exists", lambda self: False)
    assert platform_helpers.default_models_path() == Path.home() / ".ollama" / "models"


def test_default_models_path_prefers_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODELS", r"E:\PortableOllamaModels")
    assert platform_helpers.default_models_path() == Path(r"E:\PortableOllamaModels")


def test_default_models_path_macos(monkeypatch) -> None:
    monkeypatch.setattr(platform_helpers.sys, "platform", "darwin")
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    assert platform_helpers.default_models_path() == Path.home() / ".ollama"


def test_ollama_settings_pick_platform_default_models_path(monkeypatch) -> None:
    monkeypatch.setattr(platform_helpers.sys, "platform", "darwin")
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    settings = OllamaSettings()
    assert settings.models_path == Path.home() / ".ollama"


def test_script_paths_switch_to_macos(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths.platform_helpers.sys, "platform", "darwin")
    monkeypatch.setattr(paths, "get_app_root", lambda: tmp_path)

    assert paths.get_setup_script_path() == tmp_path / "scripts" / "setup_ollama_macos.sh"
    assert paths.get_check_script_path() == tmp_path / "scripts" / "check_ollama_macos.sh"
