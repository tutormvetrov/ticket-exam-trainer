from __future__ import annotations

import subprocess
from pathlib import Path

import infrastructure.ollama.runtime as runtime_module
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


def test_resolve_executable_path_checks_standard_macos_locations(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "Applications" / "Ollama.app" / "Contents" / "Resources" / "ollama"
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_text("ollama", encoding="utf-8")

    monkeypatch.delenv("OLLAMA_BIN", raising=False)
    monkeypatch.setattr(runtime_module, "is_macos", lambda: True)
    monkeypatch.setattr(runtime_module, "is_windows", lambda: False)
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(runtime_module.Path, "home", lambda: tmp_path)

    assert OllamaRuntimeManager.resolve_executable_path() == bundled


def test_ensure_ready_uses_open_app_on_macos_when_bundle_exists(tmp_path: Path, monkeypatch) -> None:
    app_bundle = tmp_path / "Applications" / "Ollama.app"
    executable = app_bundle / "Contents" / "Resources" / "ollama"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("ollama", encoding="utf-8")

    configured = tmp_path / ".ollama"
    manager = OllamaRuntimeManager("http://localhost:11434", configured)

    launches: list[list[str]] = []

    def _fake_popen(args, **kwargs):
        launches.append(list(args))
        class _Proc:
            pass
        return _Proc()

    readiness = iter([False, True])

    monkeypatch.setattr(runtime_module, "is_macos", lambda: True)
    monkeypatch.setattr(runtime_module, "is_windows", lambda: False)
    monkeypatch.setattr(runtime_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(manager, "_endpoint_ready", lambda timeout_seconds: next(readiness))
    monkeypatch.setattr(manager, "_fetch_tags", lambda timeout_seconds: {"models": [{"name": "qwen3:8b"}]})
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    status = manager.ensure_ready("qwen3:8b", wait_timeout_seconds=1.0)

    assert status.state == "ready"
    assert status.started_server is True
    assert launches == [["open", "-a", str(app_bundle)]]


def test_inspect_bootstrap_reports_model_missing_when_preferred_model_absent(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "ollama"
    executable.write_text("ollama", encoding="utf-8")
    manager = OllamaRuntimeManager("http://localhost:11434", tmp_path / ".ollama")

    monkeypatch.setattr(OllamaRuntimeManager, "resolve_executable_path", staticmethod(lambda: executable))
    monkeypatch.setattr(OllamaRuntimeManager, "resolve_app_bundle_path", staticmethod(lambda: None))
    monkeypatch.setattr(manager, "_endpoint_ready", lambda timeout_seconds: True)
    monkeypatch.setattr(manager, "_fetch_tags", lambda timeout_seconds: {"models": [{"name": "llama3:8b"}]})

    status = manager.inspect_bootstrap("qwen3:8b")

    assert status.state == "model_missing"
    assert status.endpoint_ready is True
    assert status.preferred_model == "qwen3:8b"
