from __future__ import annotations

from pathlib import Path
import sys

from app import platform as platform_helpers


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_readme_path() -> Path:
    return get_app_root() / "README.md"


def get_docs_path() -> Path:
    return get_app_root() / "docs"


def get_setup_script_path() -> Path | None:
    script_name = platform_helpers.setup_script_name()
    if script_name is None:
        return None
    return get_app_root() / "scripts" / script_name


def get_check_script_path() -> Path | None:
    script_name = platform_helpers.check_script_name()
    if script_name is None:
        return None
    return get_app_root() / "scripts" / script_name
