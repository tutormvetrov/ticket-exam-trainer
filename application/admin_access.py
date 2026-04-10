from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import secrets


@dataclass(slots=True)
class AdminAccessState:
    configured: bool
    debug_mode: bool
    password_hint: str = ""


class AdminAccessStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_state(self) -> AdminAccessState:
        payload = self._load_payload()
        return AdminAccessState(
            configured=bool(payload.get("password_hash")),
            debug_mode=bool(payload.get("debug_mode", False)),
            password_hint=str(payload.get("password_hint", "")),
        )

    def verify_password(self, password: str) -> bool:
        payload = self._load_payload()
        password_hash = payload.get("password_hash", "")
        salt = payload.get("salt", "")
        if not password_hash or not salt or not password:
            return False
        candidate = self._hash_password(password, salt)
        return hmac.compare_digest(candidate, password_hash)

    def set_password(self, password: str, password_hint: str = "") -> None:
        if not password.strip():
            raise ValueError("Пароль администратора не может быть пустым.")
        salt = secrets.token_hex(16)
        payload = self._load_payload()
        payload["salt"] = salt
        payload["password_hash"] = self._hash_password(password, salt)
        payload["password_hint"] = password_hint.strip()
        payload.setdefault("debug_mode", False)
        self._save_payload(payload)

    def clear_password(self) -> None:
        payload = self._load_payload()
        payload["salt"] = ""
        payload["password_hash"] = ""
        payload["password_hint"] = ""
        payload["debug_mode"] = False
        self._save_payload(payload)

    def set_debug_mode(self, enabled: bool) -> None:
        payload = self._load_payload()
        payload["debug_mode"] = bool(enabled)
        self._save_payload(payload)

    def _load_payload(self) -> dict:
        if not self.path.exists():
            return {
                "salt": "",
                "password_hash": "",
                "password_hint": "",
                "debug_mode": False,
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_payload(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
