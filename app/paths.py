from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app import platform as platform_helpers

APP_WORKSPACE_DIRNAME = "Tezis"
_MIGRATABLE_APP_DATA_FILES = (
    "settings.json",
    "admin_access.json",
    "dlc_license.json",
    "ui_text_overrides.json",
)


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_app_root() -> Path:
    return get_bundle_root()


def get_workspace_root() -> Path:
    configured = os.environ.get("TEZIS_WORKSPACE_ROOT", "").strip()
    if configured:
        workspace_root = Path(configured).expanduser()
        _ensure_workspace_dirs(workspace_root)
        return workspace_root

    bundle_root = get_bundle_root()
    if not getattr(sys, "frozen", False):
        _ensure_workspace_dirs(bundle_root)
        return bundle_root

    workspace_root = _default_user_workspace_root()
    _ensure_workspace_dirs(workspace_root)
    _migrate_legacy_workspace(bundle_root, workspace_root)
    return workspace_root


def get_readme_path() -> Path:
    return get_bundle_root() / "README.md"


def get_docs_path() -> Path:
    return get_bundle_root() / "docs"


def get_setup_script_path() -> Path | None:
    script_name = platform_helpers.setup_script_name()
    if script_name is None:
        return None
    return get_bundle_root() / "scripts" / script_name


def get_check_script_path() -> Path | None:
    script_name = platform_helpers.check_script_name()
    if script_name is None:
        return None
    return get_bundle_root() / "scripts" / script_name


def logo_assets_dir() -> Path:
    """Папка с брендовыми SVG-шаблонами логотипа.

    В dev-режиме — `<repo>/assets/logo`. В упакованной сборке `sys.frozen`
    выставлено, и данные лежат под `sys._MEIPASS` после `flet pack`.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "logo"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1] / "assets" / "logo"


def _default_user_workspace_root() -> Path:
    if platform_helpers.is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base_dir = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        return base_dir / APP_WORKSPACE_DIRNAME
    if platform_helpers.is_macos():
        return Path.home() / "Library" / "Application Support" / APP_WORKSPACE_DIRNAME
    return Path.home() / ".local" / "share" / APP_WORKSPACE_DIRNAME


def _ensure_workspace_dirs(workspace_root: Path) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "app_data").mkdir(parents=True, exist_ok=True)
    (workspace_root / "backups").mkdir(parents=True, exist_ok=True)


def _migrate_legacy_workspace(bundle_root: Path, workspace_root: Path) -> None:
    candidate_roots = _legacy_workspace_candidates(bundle_root, workspace_root)
    target_db = workspace_root / "exam_trainer.db"
    if not target_db.exists():
        source_db = _pick_legacy_database(candidate_roots)
        if source_db is not None:
            shutil.copy2(source_db, target_db)

    for filename in _MIGRATABLE_APP_DATA_FILES:
        target_path = workspace_root / "app_data" / filename
        if target_path.exists():
            continue
        for root in candidate_roots:
            source_path = root / "app_data" / filename
            if source_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                break


def _legacy_workspace_candidates(bundle_root: Path, workspace_root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in [*bundle_root.parents[:2], bundle_root]:
        resolved = root.resolve()
        if resolved == workspace_root.resolve():
            continue
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        candidates.append(resolved)
    return candidates


def _pick_legacy_database(candidate_roots: list[Path]) -> Path | None:
    best_path: Path | None = None
    best_size = -1
    for root in candidate_roots:
        database_path = root / "exam_trainer.db"
        if not database_path.exists():
            continue
        try:
            size = database_path.stat().st_size
        except OSError:
            continue
        if size > best_size:
            best_size = size
            best_path = database_path
    return best_path
