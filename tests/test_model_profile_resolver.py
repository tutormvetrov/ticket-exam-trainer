from __future__ import annotations

from application.model_profile_resolver import HardwareProfile, ModelProfileResolver
from infrastructure.ollama.service import OllamaDiagnostics


class _FakeService:
    def __init__(self, available_models: list[str]) -> None:
        self.available_models = available_models

    def inspect(self, preferred_model: str) -> OllamaDiagnostics:
        return OllamaDiagnostics(
            endpoint_ok=True,
            model_ok=preferred_model in self.available_models,
            endpoint_message="Endpoint: OK",
            model_message="ready",
            model_name=preferred_model if preferred_model in self.available_models else "",
            available_models=self.available_models,
        )


def test_recommend_install_target_prefers_qwen3_4b_for_16gb_machine() -> None:
    resolver = ModelProfileResolver()
    hardware = HardwareProfile(memory_gb=16.0, cpu_threads=12, platform_name="windows")

    recommendation = resolver.recommend_install_target(hardware)

    assert recommendation.model_name == "qwen3:4b"
    assert "16.0 GB" in recommendation.rationale


def test_recommend_prefers_installed_model_within_comfort_tier(monkeypatch) -> None:
    resolver = ModelProfileResolver()
    hardware = HardwareProfile(memory_gb=16.0, cpu_threads=12, platform_name="windows")
    monkeypatch.setattr(resolver, "detect_hardware", lambda: hardware)

    recommendation = resolver.recommend(_FakeService(["qwen3:8b", "qwen3:4b"]), "qwen3:8b")

    assert recommendation.model_name == "qwen3:4b"
    assert recommendation.available is True


def test_recommend_keeps_install_target_when_only_heavy_model_is_installed(monkeypatch) -> None:
    resolver = ModelProfileResolver()
    hardware = HardwareProfile(memory_gb=12.0, cpu_threads=8, platform_name="windows")
    monkeypatch.setattr(resolver, "detect_hardware", lambda: hardware)

    recommendation = resolver.recommend(_FakeService(["qwen3:8b"]), "qwen3:8b")

    assert recommendation.model_name == "qwen3:4b"
    assert recommendation.available is False
    assert "qwen3:8b" in recommendation.rationale
