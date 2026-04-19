from __future__ import annotations

from ui_flet.views.settings_view import _candidate_gemini_key_from_env, _looks_like_gemini_key


def test_looks_like_gemini_key_accepts_google_style_prefix() -> None:
    assert _looks_like_gemini_key("AIzaSyDemoKey1234567890abcdefghijkl")


def test_candidate_gemini_key_from_env_prefers_supported_names(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyEnvKey1234567890abcdefghijkl")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert _candidate_gemini_key_from_env() == "AIzaSyEnvKey1234567890abcdefghijkl"
