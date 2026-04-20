from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from infrastructure.ollama.runtime import OllamaBootstrapStatus
from ui_flet.components.ollama_fallback_notice import build_ollama_fallback_notice
from ui_flet.state import AppState
from ui_flet.views.settings_view import (
    _candidate_gemini_key_from_env,
    _describe_ollama_setup,
    _looks_like_gemini_key,
)


def test_looks_like_gemini_key_accepts_google_style_prefix() -> None:
    assert _looks_like_gemini_key("AIzaSyDemoKey1234567890abcdefghijkl")


def test_candidate_gemini_key_from_env_prefers_supported_names(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyEnvKey1234567890abcdefghijkl")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert _candidate_gemini_key_from_env() == "AIzaSyEnvKey1234567890abcdefghijkl"


def test_describe_ollama_setup_maps_not_installed_to_download_cta() -> None:
    status = OllamaBootstrapStatus(state="not_installed", preferred_model="qwen3:8b")

    descriptor = _describe_ollama_setup(status, "qwen3:8b", macos=True)

    assert descriptor.action_kind == "download_mac"
    assert descriptor.action_label == "Скачать Ollama for Mac"


def test_describe_ollama_setup_surfaces_ready_fallback_model() -> None:
    status = OllamaBootstrapStatus(
        state="ready",
        preferred_model="qwen3:8b",
        resolved_model="qwen3:4b",
        models_path="/tmp/.ollama",
    )

    descriptor = _describe_ollama_setup(status, "qwen3:8b", macos=True)

    assert descriptor.action_kind == "inspect"
    assert "qwen3:4b" in descriptor.body
    assert "/tmp/.ollama" in descriptor.meta


class _MockPage:
    route = "/training"

    def go(self, route: str) -> None:
        self.route = route

    def update(self) -> None:
        pass


def _collect_texts(control: ft.Control | None) -> list[str]:
    if control is None:
        return []
    values: list[str] = []
    for attr in ("text", "value", "label", "hint_text", "tooltip"):
        raw = getattr(control, attr, None)
        if isinstance(raw, str) and raw:
            values.append(raw)
    content = getattr(control, "content", None)
    if content is not None:
        values.extend(_collect_texts(content))
    controls = getattr(control, "controls", None)
    if isinstance(controls, list):
        for child in controls:
            values.extend(_collect_texts(child))
    return values


def test_ollama_fallback_notice_contains_settings_cta() -> None:
    facade = SimpleNamespace(settings=SimpleNamespace(model="qwen3:8b", ollama_enabled=True))
    state = AppState(page=_MockPage(), facade=facade)

    control = build_ollama_fallback_notice(state, "model_missing")
    text_blob = " ".join(_collect_texts(control))

    assert "qwen3:8b" in text_blob
    assert "Настроить полную рецензию" in text_blob
