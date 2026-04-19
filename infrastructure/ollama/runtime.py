from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.platform import default_models_path, is_windows


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

    def ensure_server_ready(self, wait_timeout_seconds: float = 20.0) -> OllamaRuntimeStatus:
        executable_path = self.resolve_executable_path()
        effective_models_path = self.resolve_models_path()
        if executable_path is None:
            return OllamaRuntimeStatus(
                executable_path="",
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                error="Ollama executable not found.",
            )

        if self._endpoint_ready(timeout_seconds=3.0):
            return OllamaRuntimeStatus(
                executable_path=str(executable_path),
                endpoint_ready=True,
                started_server=False,
                models_path=str(effective_models_path),
            )

        if not self._can_autostart():
            return OllamaRuntimeStatus(
                executable_path=str(executable_path),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                error="Automatic start is only supported for local Ollama at localhost:11434.",
            )

        try:
            effective_models_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return OllamaRuntimeStatus(
                executable_path=str(executable_path),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                error=f"Cannot prepare models path: {exc}",
            )

        try:
            subprocess.Popen(
                [str(executable_path), "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=self._creation_flags(),
                env=self._build_environment(effective_models_path),
            )
        except OSError as exc:
            return OllamaRuntimeStatus(
                executable_path=str(executable_path),
                endpoint_ready=False,
                started_server=False,
                models_path=str(effective_models_path),
                error=f"Cannot start Ollama server: {exc}",
            )

        deadline = time.monotonic() + max(5.0, wait_timeout_seconds)
        while time.monotonic() < deadline:
            if self._endpoint_ready(timeout_seconds=2.5):
                return OllamaRuntimeStatus(
                executable_path=str(executable_path),
                endpoint_ready=True,
                started_server=True,
                models_path=str(effective_models_path),
            )
            time.sleep(0.5)

        return OllamaRuntimeStatus(
            executable_path=str(executable_path),
            endpoint_ready=False,
            started_server=True,
            models_path=str(effective_models_path),
            error=f"Ollama server did not become ready at {self.base_url} in time.",
        )

    @staticmethod
    def resolve_executable_path() -> Path | None:
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = []
        if local_appdata:
            candidates.extend(
                [
                    local_appdata / "Programs" / "Ollama" / "ollama.exe",
                    local_appdata / "Programs" / "Ollama" / "ollama",
                ]
            )
        which_result = shutil.which("ollama")
        if which_result:
            candidates.append(Path(which_result))

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
        return host in {"localhost", "127.0.0.1"} and port == 11434
