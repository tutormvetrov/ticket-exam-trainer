from __future__ import annotations

import json
from pathlib import Path


class InterfaceTextStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in payload.items() if str(value).strip()}

    def save(self, overrides: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cleaned = {key: value for key, value in overrides.items() if value.strip()}
        self.path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
