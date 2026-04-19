"""Tests for GeminiService — security-focused.

Covers the two P0 changes from the April 2026 security audit:

1. API key must be sent in the ``x-goog-api-key`` HTTP header, never as a
   ``?key=...`` query parameter. Query-string secrets leak into HTTP access
   logs, proxy logs and browser history.

2. When no explicit key is passed to the constructor, the service must pick
   it up from ``GOOGLE_API_KEY`` / ``GEMINI_API_KEY`` environment variables
   so that users can keep the key out of ``settings.json``.

All tests mock ``requests`` — no real network traffic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from infrastructure.gemini import service as gemini_service
from infrastructure.gemini.service import GeminiService


class _Resp:
    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.status_code = status
        self._payload = payload or {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        }
        self.text = ""

    def json(self) -> dict:
        return self._payload


# ── Header vs query-param (P0-A) ────────────────────────────────────────────


def test_probe_sends_api_key_in_header_not_in_query() -> None:
    captured: dict = {}

    def _fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return _Resp(200)

    svc = GeminiService(api_key="AIzaSyDemoKey1234567890abcdefghijkl")
    with patch.object(gemini_service.requests, "get", side_effect=_fake_get):
        ok, err = svc.probe()

    assert ok is True, err
    params = captured["params"] or {}
    headers = captured["headers"] or {}
    assert "key" not in params, "API key must not be in URL query params"
    assert headers.get("x-goog-api-key") == "AIzaSyDemoKey1234567890abcdefghijkl"


def test_ask_sends_api_key_in_header_not_in_query() -> None:
    captured: dict = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return _Resp(200)

    svc = GeminiService(api_key="AIzaSyDemoKey1234567890abcdefghijkl")
    with patch.object(gemini_service.requests, "post", side_effect=_fake_post):
        answer = svc.ask("what is the fifth block?")

    assert answer == "ok"
    params = captured["params"] or {}
    headers = captured["headers"] or {}
    assert "key" not in params
    assert headers.get("x-goog-api-key") == "AIzaSyDemoKey1234567890abcdefghijkl"


# ── Environment fallback (P0-B) ─────────────────────────────────────────────


def test_service_falls_back_to_env_var_when_api_key_empty(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyEnvKey1234567890abcdefghijkl")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    svc = GeminiService(api_key="")

    assert svc.is_configured()
    assert svc.api_key == "AIzaSyEnvKey1234567890abcdefghijkl"


def test_service_accepts_gemini_api_key_env_var(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyGemEnvKey1234567890abcdefghi")

    svc = GeminiService(api_key="")

    assert svc.is_configured()
    assert svc.api_key == "AIzaSyGemEnvKey1234567890abcdefghi"


def test_service_prefers_explicit_api_key_over_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyEnvKey1234567890abcdefghijkl")

    svc = GeminiService(api_key="AIzaSyExplicitKey1234567890abcdefgh")

    assert svc.api_key == "AIzaSyExplicitKey1234567890abcdefgh"


def test_service_is_not_configured_without_key_or_env(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    svc = GeminiService(api_key="")

    assert not svc.is_configured()
    ok, err = svc.probe()
    assert ok is False
    assert "ключ" in err.lower()


# ── No-key-leak: explicit check that the URL never contains the key ─────────


def test_request_url_never_contains_api_key() -> None:
    """Belt-and-braces — even via requests internals, the full URL must not embed the key."""
    captured_urls: list[str] = []
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "x"}]}}]
    }

    def _fake_post(url, **kwargs):
        # requests would build this URL — simulate the final URL by rendering params
        params = kwargs.get("params") or {}
        rendered = url if not params else f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items())
        captured_urls.append(rendered)
        return mock_resp

    svc = GeminiService(api_key="AIzaSyAuditKey1234567890abcdefghi")
    with patch.object(gemini_service.requests, "post", side_effect=_fake_post):
        svc.ask("ping")

    for url in captured_urls:
        assert "AIzaSyAuditKey" not in url, f"API key leaked into URL: {url}"
