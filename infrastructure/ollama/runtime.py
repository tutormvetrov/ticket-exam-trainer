from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.platform import default_models_path, is_macos, is_windows

_LOCAL_OLLAMA_HOSTS = {"localhost", "127.0.0.1"}


@dataclass(slots=True)
class OllamaBootstrapStatus:
    state: str
    executable_path: str = ""
    app_bundle_path: str = ""
    endpoint_ready: bool = False
    started_server: bool = False
    models_path: str = ""
    preferred_model: str = ""
    resolved_model: str = ""
    available_models: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(slots=True)
class OllamaRuntimeStatus:
    executable_path: str = ""
    endpoint_ready: bool = False
    started_server: bool = False
    models_path: str = ""
    error: str = ""


class OllamaRuntimeManager:
    def __init__(self, base_url: str, models_path: Path | str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.models_path = Path(models_path) if models_path else default_models_path()

    def inspect_bootstrap(self, preferred_model: str = "") -> OllamaBootstrapStatus:
        executable_path = self.resolve_executable_path()
        app_bundle_path = self.resolve_app_bundle_path()
        effective_models_path = self.resolve_models_path()
        if executable_path is None and app_bundle_path is None:
            return OllamaBootstrapStatus(
                state="not_installed",
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error="Ollama не найдена на этом компьютере.",
            )

        if not self._endpoint_ready(timeout_seconds=2.5):
            return OllamaBootstrapStatus(
                state="installed_not_running",
                executable_path=str(executable_path or ""),
                app_bundle_path=str(app_bundle_path or ""),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error="Локальный endpoint Ollama не отвечает.",
            )

        return self._bootstrap_status_from_ready_endpoint(
            executable_path=executable_path,
            app_bundle_path=app_bundle_path,
            effective_models_path=effective_models_path,
            preferred_model=preferred_model,
            started_server=False,
        )

    def ensure_ready(
        self,
        preferred_model: str = "",
        wait_timeout_seconds: float = 20.0,
    ) -> OllamaBootstrapStatus:
        executable_path = self.resolve_executable_path()
        app_bundle_path = self.resolve_app_bundle_path()
        effective_models_path = self.resolve_models_path()
        if executable_path is None and app_bundle_path is None:
            return OllamaBootstrapStatus(
                state="not_installed",
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error="Ollama не найдена на этом компьютере.",
            )

        if self._endpoint_ready(timeout_seconds=3.0):
            return self._bootstrap_status_from_ready_endpoint(
                executable_path=executable_path,
                app_bundle_path=app_bundle_path,
                effective_models_path=effective_models_path,
                preferred_model=preferred_model,
                started_server=False,
            )

        if not self._can_autostart():
            return OllamaBootstrapStatus(
                state="error",
                executable_path=str(executable_path or ""),
                app_bundle_path=str(app_bundle_path or ""),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error="Автозапуск Ollama поддерживается только для localhost:11434.",
            )

        try:
            effective_models_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return OllamaBootstrapStatus(
                state="error",
                executable_path=str(executable_path or ""),
                app_bundle_path=str(app_bundle_path or ""),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error=f"Не удалось подготовить каталог моделей: {exc}",
            )

        try:
            self._start_server(executable_path, app_bundle_path, effective_models_path)
        except OSError as exc:
            return OllamaBootstrapStatus(
                state="error",
                executable_path=str(executable_path or ""),
                app_bundle_path=str(app_bundle_path or ""),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error=f"Не удалось запустить Ollama: {exc}",
            )

        deadline = time.monotonic() + max(5.0, wait_timeout_seconds)
        while time.monotonic() < deadline:
            if self._endpoint_ready(timeout_seconds=2.5):
                return self._bootstrap_status_from_ready_endpoint(
                    executable_path=executable_path,
                    app_bundle_path=app_bundle_path,
                    effective_models_path=effective_models_path,
                    preferred_model=preferred_model,
                    started_server=True,
                )
            time.sleep(0.5)

        return OllamaBootstrapStatus(
            state="installed_not_running",
            executable_path=str(executable_path or ""),
            app_bundle_path=str(app_bundle_path or ""),
            endpoint_ready=False,
            started_server=True,
            models_path=str(effective_models_path),
            preferred_model=preferred_model,
            error=f"Ollama не ответила по адресу {self.base_url} вовремя.",
        )

    def pull_model(
        self,
        model_name: str,
        *,
        wait_timeout_seconds: float = 25.0,
        pull_timeout_seconds: float = 1800.0,
    ) -> OllamaBootstrapStatus:
        target_model = (model_name or "").strip()
        status = self.ensure_ready(wait_timeout_seconds=wait_timeout_seconds)
        if not status.endpoint_ready or not target_model:
            if target_model and not status.preferred_model:
                status.preferred_model = target_model
            return status

        executable_path = Path(status.executable_path) if status.executable_path else self.resolve_executable_path()
        if executable_path is None:
            return OllamaBootstrapStatus(
                state="error",
                endpoint_ready=status.endpoint_ready,
                started_server=status.started_server,
                models_path=status.models_path,
                preferred_model=target_model,
                error="Исполняемый файл Ollama недоступен для загрузки модели.",
            )

        try:
            subprocess.run(
                [str(executable_path), "pull", target_model],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=max(30.0, pull_timeout_seconds),
                creationflags=self._creation_flags(),
                env=self._build_environment(Path(status.models_path) if status.models_path else self.resolve_models_path()),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return OllamaBootstrapStatus(
                state="error",
                executable_path=str(executable_path),
                app_bundle_path=status.app_bundle_path,
                endpoint_ready=status.endpoint_ready,
                started_server=status.started_server,
                models_path=status.models_path,
                preferred_model=target_model,
                error=f"Не удалось скачать модель {target_model}: {exc}",
            )

        return self.inspect_bootstrap(target_model)

    def ensure_server_ready(self, wait_timeout_seconds: float = 20.0) -> OllamaRuntimeStatus:
        bootstrap = self.ensure_ready(wait_timeout_seconds=wait_timeout_seconds)
        return OllamaRuntimeStatus(
            executable_path=bootstrap.executable_path,
            endpoint_ready=bootstrap.endpoint_ready,
            started_server=bootstrap.started_server,
            models_path=bootstrap.models_path,
            error=bootstrap.error,
        )

    @staticmethod
    def resolve_executable_path() -> Path | None:
        env_candidate = os.environ.get("OLLAMA_BIN", "").strip()
        if env_candidate:
            path = Path(env_candidate).expanduser()
            if path.exists():
                return path

        candidates: list[Path] = []
        which_result = shutil.which("ollama")
        if which_result:
            candidates.append(Path(which_result))

        if is_windows():
            local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
            if local_appdata:
                candidates.extend(
                    [
                        local_appdata / "Programs" / "Ollama" / "ollama.exe",
                        local_appdata / "Programs" / "Ollama" / "ollama",
                    ]
                )
        elif is_macos():
            candidates.extend(
                [
                    Path("/opt/homebrew/bin/ollama"),
                    Path("/usr/local/bin/ollama"),
                    Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                    Path.home() / "Applications" / "Ollama.app" / "Contents" / "Resources" / "ollama",
                ]
            )

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def resolve_app_bundle_path() -> Path | None:
        if not is_macos():
            return None
        candidates = [
            Path("/Applications/Ollama.app"),
            Path.home() / "Applications" / "Ollama.app",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def resolve_models_path(self) -> Path:
        env_path = os.environ.get("OLLAMA_MODELS", "").strip()
        if env_path and self._path_has_models(Path(env_path)):
            return Path(env_path)
        desired_path = self.models_path
        if self._path_has_models(desired_path):
            return desired_path
        for legacy_path in self._legacy_models_paths():
            if self._path_has_models(legacy_path):
                return legacy_path
        if env_path:
            return Path(env_path)
        return desired_path

    def _bootstrap_status_from_ready_endpoint(
        self,
        *,
        executable_path: Path | None,
        app_bundle_path: Path | None,
        effective_models_path: Path,
        preferred_model: str,
        started_server: bool,
    ) -> OllamaBootstrapStatus:
        response = self._fetch_tags(timeout_seconds=3.0)
        if response is None:
            return OllamaBootstrapStatus(
                state="error",
                executable_path=str(executable_path or ""),
                app_bundle_path=str(app_bundle_path or ""),
                endpoint_ready=False,
                started_server=started_server,
                models_path=str(effective_models_path),
                preferred_model=preferred_model,
                error="Endpoint Ollama ответил некорректно.",
            )

        models = response.get("models", [])
        available_models = [
            str(model.get("name", "")).strip()
            for model in models
            if isinstance(model, dict) and str(model.get("name", "")).strip()
        ]
        resolved_model = self._resolve_model_name(available_models, preferred_model)
        state = "ready"
        error = ""
        if preferred_model and not resolved_model:
            state = "model_missing"
            error = f"Модель {preferred_model} не найдена локально."

        return OllamaBootstrapStatus(
            state=state,
            executable_path=str(executable_path or ""),
            app_bundle_path=str(app_bundle_path or ""),
            endpoint_ready=True,
            started_server=started_server,
            models_path=str(effective_models_path),
            preferred_model=preferred_model,
            resolved_model=resolved_model,
            available_models=available_models,
            error=error,
        )

    def _start_server(
        self,
        executable_path: Path | None,
        app_bundle_path: Path | None,
        models_path: Path,
    ) -> None:
        if is_macos() and app_bundle_path is not None:
            subprocess.Popen(
                ["open", "-a", str(app_bundle_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=self._build_environment(models_path),
            )
            return

        if executable_path is None:
            raise OSError("Ollama executable not found.")

        subprocess.Popen(
            [str(executable_path), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=self._creation_flags(),
            env=self._build_environment(models_path),
        )

    def _build_environment(self, models_path: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(models_path)
        return env

    def _endpoint_ready(self, timeout_seconds: float) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=timeout_seconds)
        except requests.RequestException:
            return False
        return response.ok

    def _fetch_tags(self, timeout_seconds: float) -> dict[str, object] | None:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=timeout_seconds)
        except requests.RequestException:
            return None
        if not response.ok:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _creation_flags() -> int:
        if not is_windows():
            return 0
        return (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    @staticmethod
    def _legacy_models_paths() -> list[Path]:
        if is_windows():
            return [
                Path.home() / ".ollama" / "models",
                Path(r"D:\OllamaModels"),
            ]
        legacy_paths: list[Path] = [Path.home() / ".ollama" / "models"]
        default_path = default_models_path()
        if default_path not in legacy_paths:
            legacy_paths.append(default_path)
        return legacy_paths

    @staticmethod
    def _path_has_models(path: Path) -> bool:
        manifests = path / "manifests"
        blobs = path / "blobs"
        if not manifests.exists() or not blobs.exists():
            return False
        try:
            has_manifests = any(manifests.rglob("*"))
            has_blobs = any(blobs.iterdir())
        except OSError:
            return False
        return has_manifests and has_blobs

    def _can_autostart(self) -> bool:
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host in _LOCAL_OLLAMA_HOSTS and port == 11434

    @staticmethod
    def _resolve_model_name(available_models: list[str], preferred_model: str) -> str:
        if not available_models:
            return ""
        if not preferred_model:
            return available_models[0]
        for candidate in available_models:
            if candidate == preferred_model:
                return candidate

        family = preferred_model.split(":", 1)[0].strip().lower()
        if not family:
            return ""
        for candidate in available_models:
            if family in candidate.lower():
                return candidate
        return ""
