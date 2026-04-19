from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

WINDOWS_DEFAULT_MODELS_PATH = Path(r"D:\Ollama\models")
WINDOWS_LEGACY_SHARED_MODELS_PATH = Path(r"D:\OllamaModels")


def platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def is_windows() -> bool:
    return platform_key() == "windows"


def is_macos() -> bool:
    return platform_key() == "macos"


def platform_label() -> str:
    mapping = {
        "windows": "Windows",
        "macos": "macOS",
        "linux": "Linux",
    }
    return mapping.get(platform_key(), "Desktop")


def default_models_path() -> Path:
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    if configured:
        return Path(configured)
    if is_windows():
        drive_d = Path(r"D:\\")
        if drive_d.exists():
            return WINDOWS_DEFAULT_MODELS_PATH
        return Path.home() / ".ollama" / "models"
    if is_macos():
        return Path.home() / ".ollama"
    return Path.home() / ".ollama"


def setup_script_name() -> str | None:
    if is_windows():
        return "setup_ollama_windows.ps1"
    if is_macos():
        return "setup_ollama_macos.sh"
    return None


def check_script_name() -> str | None:
    if is_windows():
        return "check_ollama.ps1"
    if is_macos():
        return "check_ollama_macos.sh"
    return None


def release_build_script_name() -> str | None:
    if is_windows():
        return "build_flet_exe.ps1"
    if is_macos():
        return "build_mac_app.sh"
    return None


def release_artifact_name() -> str:
    if is_windows():
        return "Tezis.exe"
    if is_macos():
        return "Tezis.app"
    return "Tezis"


def script_host_label() -> str:
    if is_windows():
        return "PowerShell"
    if is_macos():
        return "Terminal"
    return "shell"


def launch_support_script(script_path: Path) -> None:
    if is_windows():
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return

    if is_macos():
        command = f"bash {shlex.quote(str(script_path))}"
        subprocess.Popen(
            [
                "osascript",
                "-e",
                'tell application "Terminal" to activate',
                "-e",
                f'tell application "Terminal" to do script {json.dumps(command)}',
            ]
        )
        return

    subprocess.Popen(["bash", str(script_path)])
