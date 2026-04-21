from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
    for candidate_root in _candidate_roots(root):
        build_info = _read_build_info_json(candidate_root / "build_info.json")
        if build_info is not None:
            return build_info

    return RuntimeBuildInfo(
        version=_git_version_label(root) or APP_VERSION,
        commit=_git_output(root, "rev-parse", "--short=12", "HEAD"),
        built_at=_git_output(root, "show", "-s", "--format=%cI", "HEAD"),
        source="git",
    )


def write_runtime_build_info(
    output_path: Path,
    *,
    version: str = "",
    commit: str = "",
    built_at: str = "",
) -> RuntimeBuildInfo:
    resolved_version = _normalize_version(version) or _git_version_label(output_path.parent) or APP_VERSION
    resolved_commit = commit.strip() or _git_output(output_path.parent, "rev-parse", "--short=12", "HEAD")
    resolved_built_at = built_at.strip() or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "version": resolved_version,
        "commit": resolved_commit,
        "built_at": resolved_built_at,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return RuntimeBuildInfo(
        version=resolved_version,
        commit=resolved_commit,
        built_at=resolved_built_at,
        source="build-info-json",
    )


def _candidate_roots(root: Path) -> list[Path]:
    bundle_root = get_app_root()
    candidates: list[Path] = []
    seen: set[Path] = set()
    meipass = getattr(sys, "_MEIPASS", None)
    dynamic_bundle_root = Path(meipass) if meipass else None
    for candidate in (root, bundle_root, dynamic_bundle_root):
        if candidate is None:
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(resolved)
    return candidates


def _read_build_info_json(build_info_path: Path) -> RuntimeBuildInfo | None:
    if not build_info_path.exists():
        return None
    try:
        payload = json.loads(build_info_path.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return None
    return RuntimeBuildInfo(
        version=_normalize_version(str(payload.get("version") or "")) or APP_VERSION,
        commit=str(payload.get("commit") or ""),
        built_at=str(payload.get("built_at") or ""),
        source="build-info-json",
    )


def _git_version_label(root: Path) -> str:
    described = _normalize_version(_git_output(root, "describe", "--tags", "--always", "--dirty"))
    if described:
        return described
    return _normalize_version(_git_output(root, "describe", "--tags", "--abbrev=0"))


def _normalize_version(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.lower().startswith("v"):
        return cleaned[1:]
    return cleaned


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
