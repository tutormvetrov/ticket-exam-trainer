from __future__ import annotations

import pytest

from application.settings import validate_ollama_base_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://127.0.0.1",
        "http://[::1]:11434",
        "http://192.168.1.50:11434",
        "http://10.0.0.5:11434",
        "http://172.16.10.1:11434",
        "https://localhost:11434",
    ],
)
def test_accepts_local_and_private_urls(url: str) -> None:
    ok, message = validate_ollama_base_url(url)
    assert ok is True, message
    assert message == ""


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "localhost:11434",  # нет схемы
        "ftp://localhost:11434",  # неподдерживаемая схема
        "http://example.com",  # публичный хост
        "http://8.8.8.8",  # публичный IP
        "http://attacker.ngrok.io:11434",
    ],
)
def test_rejects_non_local_urls(url: str) -> None:
    ok, message = validate_ollama_base_url(url)
    assert ok is False
    assert message
