from __future__ import annotations

import sys
from pathlib import Path

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
