from __future__ import annotations

import importlib

import pytest


RUNTIME_MODULES = ("PySide6", "requests", "docx", "pypdf")


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_dependency_importable(module_name: str) -> None:
    importlib.import_module(module_name)
