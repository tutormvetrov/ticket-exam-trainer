from __future__ import annotations

import importlib

import pytest


RUNTIME_MODULES = ("PySide6", "requests", "docx", "pypdf")


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_dependency_importable(module_name: str) -> None:
    """Smoke test: every package listed in requirements.txt must be importable.
    Catches the 'works on my machine because I installed it manually but the
    requirements file is missing a line' regression."""
    importlib.import_module(module_name)
