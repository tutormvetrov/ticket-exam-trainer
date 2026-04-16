from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path
import secrets

from app.json_storage import load_json_dict, save_json_dict


_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 200_000
_LEGACY_ALGO = "sha256"


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
        algo = str(payload.get("algo", "")) or _LEGACY_ALGO
        if not password_hash or not salt or not password:
            return False
        if algo == _PBKDF2_ALGO:
            iterations = int(payload.get("iterations", _PBKDF2_ITERATIONS))
            candidate = self._pbkdf2_hash(password, salt, iterations)
            return hmac.compare_digest(candidate, password_hash)
        if algo == _LEGACY_ALGO:
            candidate = self._legacy_sha256_hash(password, salt)
            if not hmac.compare_digest(candidate, password_hash):
                return False
            # Upgrade legacy hash to PBKDF2 on successful login.
            self._rewrite_password_hash(password, payload)
            return True
        return False

    def set_password(self, password: str, password_hint: str = "") -> None:
        if not password.strip():
            raise ValueError("Пароль администратора не может быть пустым.")
        salt = secrets.token_hex(16)
        payload = self._load_payload()
        payload["salt"] = salt
        payload["password_hash"] = self._pbkdf2_hash(password, salt, _PBKDF2_ITERATIONS)
        payload["algo"] = _PBKDF2_ALGO
        payload["iterations"] = _PBKDF2_ITERATIONS
        payload["password_hint"] = password_hint.strip()
        payload.setdefault("debug_mode", False)
        self._save_payload(payload)

    def clear_password(self) -> None:
        payload = self._load_payload()
        payload["salt"] = ""
        payload["password_hash"] = ""
        payload["password_hint"] = ""
        payload["algo"] = ""
        payload["iterations"] = 0
        payload["debug_mode"] = False
        self._save_payload(payload)

    def set_debug_mode(self, enabled: bool) -> None:
        payload = self._load_payload()
        payload["debug_mode"] = bool(enabled)
        self._save_payload(payload)

    def _load_payload(self) -> dict:
        payload = load_json_dict(self.path)
        if not payload:
            return {
                "salt": "",
                "password_hash": "",
                "password_hint": "",
                "debug_mode": False,
            }
        return payload

    def _save_payload(self, payload: dict) -> None:
        save_json_dict(self.path, payload)

    def _rewrite_password_hash(self, password: str, payload: dict) -> None:
        salt = secrets.token_hex(16)
        payload["salt"] = salt
        payload["password_hash"] = self._pbkdf2_hash(password, salt, _PBKDF2_ITERATIONS)
        payload["algo"] = _PBKDF2_ALGO
        payload["iterations"] = _PBKDF2_ITERATIONS
        self._save_payload(payload)

    @staticmethod
    def _pbkdf2_hash(password: str, salt: str, iterations: int) -> str:
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return derived.hex()

    @staticmethod
    def _legacy_sha256_hash(password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
