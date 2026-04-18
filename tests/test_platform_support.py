from __future__ import annotations

from pathlib import Path

from app import paths
from app import platform as platform_helpers
from application.settings import OllamaSettings


def test_default_models_path_windows(monkeypatch) -> None:
    monkeypatch.setattr(platform_helpers.sys, "platform", "win32")
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(platform_helpers.Path, "exists", lambda self: str(self).startswith("D:"))
    assert platform_helpers.default_models_path() == Path(r"D:\Ollama\models")


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
    monkeypatch.setattr(paths, "get_bundle_root", lambda: tmp_path)

    assert paths.get_setup_script_path() == tmp_path / "scripts" / "setup_ollama_macos.sh"
    assert paths.get_check_script_path() == tmp_path / "scripts" / "check_ollama_macos.sh"


def test_workspace_root_uses_localappdata_for_frozen_windows(monkeypatch, tmp_path: Path) -> None:
    local_appdata = tmp_path / "localappdata"
    executable = tmp_path / "bundle" / "Tezis.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(paths.platform_helpers.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    workspace_root = paths.get_workspace_root()

    assert workspace_root == local_appdata / "Tezis"
    assert (workspace_root / "app_data").exists()
    assert (workspace_root / "backups").exists()


def test_workspace_root_migrates_largest_legacy_database_and_settings(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    bundle_root = repo_root / "dist" / "Tezis"
    local_appdata = tmp_path / "localappdata"
    executable = bundle_root / "Tezis.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")

    large_db = repo_root / "exam_trainer.db"
    large_db.parent.mkdir(parents=True, exist_ok=True)
    large_db.write_bytes(b"repo-db" * 100)
    (repo_root / "app_data").mkdir(parents=True, exist_ok=True)
    (repo_root / "app_data" / "settings.json").write_text('{"theme_name": "dark"}', encoding="utf-8")

    small_db = bundle_root / "exam_trainer.db"
    small_db.write_bytes(b"bundle")

    monkeypatch.setattr(paths.platform_helpers.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    workspace_root = paths.get_workspace_root()

    assert (workspace_root / "exam_trainer.db").read_bytes() == large_db.read_bytes()
    assert (workspace_root / "app_data" / "settings.json").read_text(encoding="utf-8") == '{"theme_name": "dark"}'
