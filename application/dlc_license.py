from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import base64
import hashlib
import hmac
import json
from pathlib import Path
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.json_storage import load_json_dict, save_json_dict
from domain.defense import DlcLicenseState


# --- Ed25519 public key (production) ---------------------------------------
# Пустая строка по умолчанию = Ed25519-активация выключена и принимаются только
# legacy HMAC-коды. В релизной сборке сюда подставляется ваш реальный
# public key PEM (приватный ключ хранится ВНЕ репозитория и не попадает в
# бинарь). Сгенерировать пару: `python local_tools/dlc_issuer.py generate`.
DEFAULT_DLC_PUBLIC_KEY_PEM: bytes = b""

# --- Legacy HMAC (backward compatibility) ----------------------------------
# Используется только для проверки ранее выпущенных кодов, чтобы существующие
# пользователи не теряли активацию после обновления. Новые коды выпускаются
# через dlc_issuer.py в формате Ed25519.
LEGACY_DLC_SECRET = "tezis-dlc-manual-activation-v1"

_ED25519_PREFIX = "v2."


class DlcLicenseService:
    def __init__(
        self,
        storage_path: Path,
        *,
        public_key_pem: bytes = DEFAULT_DLC_PUBLIC_KEY_PEM,
        legacy_secret: str | None = LEGACY_DLC_SECRET,
    ) -> None:
        self.storage_path = storage_path
        self._public_key = _load_public_key(public_key_pem) if public_key_pem else None
        self._legacy_secret = legacy_secret.encode("utf-8") if legacy_secret else b""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_install_id(self) -> str:
        state = self.load_state()
        if state.install_id:
            return state.install_id
        install_id = uuid4().hex
        self.save_state(DlcLicenseState(install_id=install_id))
        return install_id

    def load_state(self) -> DlcLicenseState:
        payload = load_json_dict(self.storage_path)
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
        save_json_dict(self.storage_path, payload)

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
        code = (activation_code or "").strip()
        if not code:
            return "invalid"
        if code.startswith(_ED25519_PREFIX):
            return self._inspect_ed25519(install_id, code)
        if self._legacy_secret:
            return self._inspect_legacy_hmac(install_id, code)
        return "invalid"

    def _inspect_ed25519(self, install_id: str, code: str) -> str:
        if self._public_key is None:
            return "invalid"
        try:
            _, payload_b64, signature_b64 = code.split(".", 2)
        except ValueError:
            return "invalid"
        try:
            signature = base64.urlsafe_b64decode(_pad_base64(signature_b64))
        except Exception:
            return "invalid"
        try:
            self._public_key.verify(signature, payload_b64.encode("utf-8"))
        except InvalidSignature:
            return "invalid"
        except Exception:
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

    def _inspect_legacy_hmac(self, install_id: str, code: str) -> str:
        parts = code.split(".")
        if len(parts) != 2:
            return "invalid"
        payload_b64, signature = parts
        expected = hmac.new(self._legacy_secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
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

    # Kept for legacy compatibility: tests and migration. В production коды
    # выпускаются отдельным CLI (local_tools/dlc_issuer.py), который держит
    # Ed25519-приватный ключ вне бинаря.
    def issue_legacy_code(self, install_id: str) -> str:
        if not self._legacy_secret:
            raise RuntimeError("Legacy секрет отключён, legacy-код выпустить нельзя.")
        payload = {
            "install_id": install_id,
            "tier": "defense_prep",
            "issued_at": datetime.now().isoformat(),
        }
        encoded = (
            base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            .decode("utf-8")
            .rstrip("=")
        )
        signature = hmac.new(self._legacy_secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"


def build_ed25519_activation_code(install_id: str, private_key_pem: bytes) -> str:
    """Подписать install_id приватным Ed25519-ключом и вернуть код формата
    v2.{payload_b64}.{signature_b64}.

    Используется в CLI-утилите и тестах. В рантайме приложения эта функция
    не вызывается — приложение только верифицирует публичным ключом.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Ожидался Ed25519 private key в PEM.")
    payload = {
        "install_id": install_id,
        "tier": "defense_prep",
        "issued_at": datetime.now().isoformat(),
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    signature = private_key.sign(payload_b64.encode("utf-8"))
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{_ED25519_PREFIX}{payload_b64}.{signature_b64}"


def _load_public_key(pem: bytes) -> Ed25519PublicKey | None:
    try:
        key = serialization.load_pem_public_key(pem)
    except Exception:
        return None
    if not isinstance(key, Ed25519PublicKey):
        return None
    return key


def _pad_base64(text: str) -> str:
    return text + "=" * (-len(text) % 4)


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))
