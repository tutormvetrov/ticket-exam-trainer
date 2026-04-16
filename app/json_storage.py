from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def load_json_dict(
    path: Path,
    *,
    default_factory: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    factory = default_factory or dict
    if not path.exists():
        return factory()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _quarantine_corrupt_file(path)
        return factory()
    if not isinstance(payload, dict):
        _quarantine_corrupt_file(path)
        return factory()
    return payload


def save_json_dict(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _quarantine_corrupt_file(path: Path) -> None:
    if not path.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}.corrupt-{timestamp}{path.suffix}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.corrupt-{timestamp}-{counter}{path.suffix}")
        counter += 1
    try:
        path.replace(candidate)
    except OSError:
        pass
