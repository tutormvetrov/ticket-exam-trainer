from __future__ import annotations

from pathlib import Path

from infrastructure.ollama.runtime import OllamaRuntimeManager


def _prepare_models_path(path: Path) -> None:
    (path / "manifests" / "registry.ollama.ai" / "library" / "qwen3").mkdir(parents=True, exist_ok=True)
    (path / "manifests" / "registry.ollama.ai" / "library" / "qwen3" / "8b").write_text("manifest", encoding="utf-8")
    (path / "blobs").mkdir(parents=True, exist_ok=True)
    (path / "blobs" / "sha256-demo").write_text("blob", encoding="utf-8")


def test_runtime_prefers_configured_models_path_when_populated(tmp_path: Path) -> None:
    configured = tmp_path / "configured-models"
    _prepare_models_path(configured)

    import os
    original_env = os.environ.pop("OLLAMA_MODELS", None)
    try:
        manager = OllamaRuntimeManager("http://localhost:11434", configured)
        assert manager.resolve_models_path() == configured
    finally:
        if original_env is not None:
            os.environ["OLLAMA_MODELS"] = original_env


def test_runtime_falls_back_to_legacy_models_path_when_configured_is_empty(tmp_path: Path, monkeypatch) -> None:
    configured = tmp_path / "configured-models"
    configured.mkdir(parents=True, exist_ok=True)
    legacy_home = tmp_path / "legacy-home"
    legacy_models = legacy_home / ".ollama" / "models"
    _prepare_models_path(legacy_models)

    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(Path, "home", lambda: legacy_home)
    manager = OllamaRuntimeManager("http://localhost:11434", configured)

    assert manager.resolve_models_path() == legacy_models


def test_runtime_prefers_environment_models_path_when_populated(tmp_path: Path, monkeypatch) -> None:
    configured = tmp_path / "configured-models"
    configured.mkdir(parents=True, exist_ok=True)
    env_models = tmp_path / "env-models"
    _prepare_models_path(env_models)

    monkeypatch.setenv("OLLAMA_MODELS", str(env_models))
    manager = OllamaRuntimeManager("http://localhost:11434", configured)

    assert manager.resolve_models_path() == env_models


def test_runtime_falls_back_to_shared_windows_legacy_models_path(tmp_path: Path, monkeypatch) -> None:
    configured = tmp_path / "configured-models"
    configured.mkdir(parents=True, exist_ok=True)
    shared_legacy = tmp_path / "shared-legacy-models"
    _prepare_models_path(shared_legacy)

    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(
        OllamaRuntimeManager,
        "_legacy_models_paths",
        staticmethod(lambda: [shared_legacy]),
    )
    manager = OllamaRuntimeManager("http://localhost:11434", configured)

    assert manager.resolve_models_path() == shared_legacy
