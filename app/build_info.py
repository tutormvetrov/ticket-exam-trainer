from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess

from app.meta import APP_VERSION
from app.paths import get_app_root


@dataclass(slots=True)
class RuntimeBuildInfo:
    version: str = APP_VERSION
    commit: str = ""
    built_at: str = ""
    source: str = "runtime-default"

    @property
    def version_label(self) -> str:
        return f"v{self.version}"

    @property
    def commit_label(self) -> str:
        return self.commit or "source"

    @property
    def release_label(self) -> str:
        return f"{self.version_label} • {self.commit_label}"

    @property
    def built_at_label(self) -> str:
        if not self.built_at:
            return "Время сборки не зафиксировано"
        try:
            return datetime.fromisoformat(self.built_at).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return self.built_at


def get_runtime_build_info(app_root: Path | None = None) -> RuntimeBuildInfo:
    root = app_root or get_app_root()
    build_info_path = root / "build_info.json"
    if build_info_path.exists():
        try:
            payload = json.loads(build_info_path.read_text(encoding="utf-8-sig"))
            return RuntimeBuildInfo(
                version=str(payload.get("version") or APP_VERSION),
                commit=str(payload.get("commit") or ""),
                built_at=str(payload.get("built_at") or ""),
                source="build-info-json",
            )
        except Exception:  # noqa: BLE001
            pass

    return RuntimeBuildInfo(
        version=APP_VERSION,
        commit=_git_output(root, "rev-parse", "--short=12", "HEAD"),
        built_at=_git_output(root, "show", "-s", "--format=%cI", "HEAD"),
        source="git",
    )


def _git_output(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()
