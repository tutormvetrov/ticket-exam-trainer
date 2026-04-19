from __future__ import annotations

import importlib

import pytest

RUNTIME_MODULES = (
    "flet",
    "requests",
    "docx",
    "pypdf",
    "reportlab",
    "cryptography",
    "fsrs",
    "pytest",
    "PyInstaller",
)


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_dependency_importable(module_name: str) -> None:
    """Smoke test: packages listed in requirements.txt import cleanly."""
    importlib.import_module(module_name)
