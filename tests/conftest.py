from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_addoption(parser):
    parser.addoption(
        "--run-live-ollama",
        action="store_true",
        default=False,
        help="run integration tests that require a real local Ollama service and model",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live-ollama"):
        return
    live_items = [item for item in items if "live_ollama" in item.keywords]
    if not live_items:
        return
    config.hook.pytest_deselected(items=live_items)
    items[:] = [item for item in items if "live_ollama" not in item.keywords]


@pytest.fixture(scope="session", autouse=True)
def _shutdown_qt_app():
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # noqa: BLE001
        return
    app = QApplication.instance()
    if app is None:
        return
    app.closeAllWindows()
    app.processEvents()
    app.quit()
    app.processEvents()
