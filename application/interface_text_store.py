from __future__ import annotations

from pathlib import Path

from app.json_storage import load_json_dict, save_json_dict


class InterfaceTextStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        payload = load_json_dict(self.path)
        return {str(key): str(value) for key, value in payload.items() if str(value).strip()}

    def save(self, overrides: dict[str, str]) -> None:
        cleaned = {key: value for key, value in overrides.items() if value.strip()}
        save_json_dict(self.path, cleaned)
