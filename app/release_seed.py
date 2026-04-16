from __future__ import annotations

from pathlib import Path


def resolve_seed_database(path_value: str | Path | None) -> Path | None:
    if path_value is None:
        return None
    raw_value = str(path_value).strip()
    if not raw_value:
        return None
    try:
        resolved = Path(raw_value).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"Seed database not found: {raw_value}") from exc
    if not resolved.is_file():
        raise ValueError(f"Seed database path is not a file: {resolved}")
    try:
        size_bytes = resolved.stat().st_size
    except OSError as exc:
        raise ValueError(f"Cannot inspect seed database: {exc}") from exc
    if size_bytes <= 0:
        raise ValueError(f"Seed database is empty: {resolved}")
    return resolved
