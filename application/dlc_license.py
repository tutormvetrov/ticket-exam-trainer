from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import base64
import hashlib
import hmac
import json
from pathlib import Path
from uuid import uuid4

from domain.defense import DlcLicenseState


DEFAULT_DLC_SECRET = "tezis-dlc-manual-activation-v1"


class DlcLicenseService:
    def __init__(self, storage_path: Path, secret: str = DEFAULT_DLC_SECRET) -> None:
        self.storage_path = storage_path
        self.secret = secret.encode("utf-8")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_install_id(self) -> str:
        state = self.load_state()
        if state.install_id:
            return state.install_id
        install_id = uuid4().hex
        self.save_state(DlcLicenseState(install_id=install_id))
        return install_id

    def load_state(self) -> DlcLicenseState:
        if not self.storage_path.exists():
            return DlcLicenseState(install_id="")
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        return DlcLicenseState(
            install_id=str(payload.get("install_id", "")),
            activated=bool(payload.get("activated", False)),
            license_tier=str(payload.get("license_tier", "locked")),
            token=str(payload.get("token", "")),
            status=str(payload.get("status", "locked")),
            last_checked_at=_parse_dt(payload.get("last_checked_at")),
            activated_at=_parse_dt(payload.get("activated_at")),
            error_text=str(payload.get("error_text", "")),
        )

    def save_state(self, state: DlcLicenseState) -> None:
        payload = asdict(state)
        payload["last_checked_at"] = state.last_checked_at.isoformat() if state.last_checked_at else None
        payload["activated_at"] = state.activated_at.isoformat() if state.activated_at else None
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def activate(self, install_id: str, activation_code: str) -> DlcLicenseState:
        state = self.load_state()
        verification = self.inspect_code(install_id, activation_code)
        now = datetime.now()
        if verification != "valid":
            state.install_id = install_id
            state.activated = False
            state.license_tier = "locked"
            state.status = "wrong_install" if verification == "wrong_install" else "invalid"
            state.last_checked_at = now
            state.error_text = (
                "Ключ выдан для другой установки."
                if verification == "wrong_install"
                else "Ключ не подошёл к текущей установке."
            )
            self.save_state(state)
            return state

        state.install_id = install_id
        state.activated = True
        state.license_tier = "defense_prep"
        state.token = activation_code.strip()
        state.status = "active"
        state.last_checked_at = now
        state.activated_at = now
        state.error_text = ""
        self.save_state(state)
        return state

    def verify_code(self, install_id: str, activation_code: str) -> bool:
        return self.inspect_code(install_id, activation_code) == "valid"

    def inspect_code(self, install_id: str, activation_code: str) -> str:
        parts = activation_code.strip().split(".")
        if len(parts) != 2:
            return "invalid"
        payload_b64, signature = parts
        expected_signature = hmac.new(self.secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return "invalid"
        try:
            payload = json.loads(base64.urlsafe_b64decode(_pad_base64(payload_b64)).decode("utf-8"))
        except Exception:
            return "invalid"
        if payload.get("tier") != "defense_prep":
            return "invalid"
        if payload.get("install_id") != install_id:
            return "wrong_install"
        return "valid"

    def issue_code(self, install_id: str) -> str:
        payload = {
            "install_id": install_id,
            "tier": "defense_prep",
            "issued_at": datetime.now().isoformat(),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8").rstrip("=")
        signature = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"


def _pad_base64(text: str) -> str:
    return text + "=" * (-len(text) % 4)


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))
