from __future__ import annotations

from pathlib import Path

import pytest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from application.dlc_license import DlcLicenseService, build_ed25519_activation_code


def _generate_keypair() -> tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def test_ed25519_valid_code_activates(tmp_path: Path) -> None:
    private_pem, public_pem = _generate_keypair()
    service = DlcLicenseService(tmp_path / "dlc.json", public_key_pem=public_pem)

    install_id = service.ensure_install_id()
    code = build_ed25519_activation_code(install_id, private_pem)

    state = service.activate(install_id, code)
    assert state.activated is True
    assert state.status == "active"
    assert state.license_tier == "defense_prep"


def test_ed25519_wrong_install_id_rejected(tmp_path: Path) -> None:
    private_pem, public_pem = _generate_keypair()
    service = DlcLicenseService(tmp_path / "dlc.json", public_key_pem=public_pem)

    code = build_ed25519_activation_code("install-a", private_pem)
    state = service.activate("install-b", code)

    assert state.activated is False
    assert state.status == "wrong_install"


def test_ed25519_wrong_key_rejected(tmp_path: Path) -> None:
    attacker_private_pem, _ = _generate_keypair()
    _, real_public_pem = _generate_keypair()
    service = DlcLicenseService(tmp_path / "dlc.json", public_key_pem=real_public_pem)

    install_id = service.ensure_install_id()
    # Атакующий подписывает своим ключом — приложение должно отклонить.
    forged = build_ed25519_activation_code(install_id, attacker_private_pem)
    state = service.activate(install_id, forged)

    assert state.activated is False
    assert state.status == "invalid"


def test_ed25519_tampered_signature_rejected(tmp_path: Path) -> None:
    private_pem, public_pem = _generate_keypair()
    service = DlcLicenseService(tmp_path / "dlc.json", public_key_pem=public_pem)

    install_id = service.ensure_install_id()
    code = build_ed25519_activation_code(install_id, private_pem)
    # Порча одного символа подписи.
    prefix, payload, signature = code.split(".", 2)
    tampered = f"{prefix}.{payload}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"

    state = service.activate(install_id, tampered)
    assert state.activated is False
    assert state.status == "invalid"


def test_legacy_hmac_code_still_accepted_for_backward_compat(tmp_path: Path) -> None:
    # Пользователь активировался старым HMAC-кодом. После апдейта на Ed25519
    # повторная активация тем же кодом должна работать.
    service = DlcLicenseService(tmp_path / "dlc.json")
    install_id = service.ensure_install_id()
    legacy_code = service.issue_legacy_code(install_id)

    state = service.activate(install_id, legacy_code)
    assert state.activated is True


def test_service_without_public_key_rejects_ed25519_codes(tmp_path: Path) -> None:
    private_pem, _ = _generate_keypair()
    # public_key_pem не передан → Ed25519 выключен, но legacy работает.
    service = DlcLicenseService(tmp_path / "dlc.json", public_key_pem=b"")

    install_id = service.ensure_install_id()
    code = build_ed25519_activation_code(install_id, private_pem)

    state = service.activate(install_id, code)
    assert state.activated is False
    assert state.status == "invalid"


def test_service_with_legacy_secret_disabled_rejects_legacy_codes(tmp_path: Path) -> None:
    _, public_pem = _generate_keypair()
    service = DlcLicenseService(
        tmp_path / "dlc.json",
        public_key_pem=public_pem,
        legacy_secret=None,
    )

    # Выпустим legacy-код отдельным сервисом — его не должен принять основной.
    legacy_issuer = DlcLicenseService(tmp_path / "other.json")
    install_id = "install-x"
    legacy_code = legacy_issuer.issue_legacy_code(install_id)

    state = service.activate(install_id, legacy_code)
    assert state.activated is False
