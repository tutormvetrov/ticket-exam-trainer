from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import platform
import re
import subprocess

from application.defense_ui_data import ModelRecommendation
from infrastructure.ollama.service import OllamaService


@dataclass(slots=True)
class HardwareProfile:
    memory_gb: float
    cpu_threads: int
    platform_name: str


class ModelProfileResolver:
    INSTALL_TIERS: tuple[tuple[str, float], ...] = (
        ("qwen3:14b", 32.0),
        ("qwen3:8b", 20.0),
        ("qwen3:4b", 12.0),
        ("qwen3:1.7b", 8.0),
        ("qwen3:0.6b", 0.0),
    )

    def detect_hardware(self) -> HardwareProfile:
        return HardwareProfile(
            memory_gb=self._detect_memory_gb(),
            cpu_threads=max(1, os.cpu_count() or 1),
            platform_name=platform.system().lower(),
        )

    def recommend_install_target(self, hardware: HardwareProfile | None = None) -> ModelRecommendation:
        profile = hardware or self.detect_hardware()
        model_name = self._pick_install_target(profile)
        return ModelRecommendation(
            model_name=model_name,
            label=f"Рекомендуемая модель: {model_name}",
            rationale=(
                f"RAM: {profile.memory_gb:.1f} GB, threads: {profile.cpu_threads}. "
                f"Для такого ПК комфортнее начинать с {model_name}."
            ),
            available=False,
        )

    def recommend(self, service: OllamaService, preferred_model: str) -> ModelRecommendation:
        hardware = self.detect_hardware()
        diagnostics = service.inspect(preferred_model)
        available = [name for name in diagnostics.available_models if name]
        install_target = self.recommend_install_target(hardware)
        rationale = f"RAM: {hardware.memory_gb:.1f} GB, threads: {hardware.cpu_threads}."

        if available:
            target = self._pick_best_installed(available, hardware, preferred_model)
            if target:
                return ModelRecommendation(
                    model_name=target,
                    label=f"Рекомендуемая модель: {target}",
                    rationale=(
                        f"{rationale} Выбрана самая сильная локально доступная {self._family_label(target)} "
                        "в комфортном диапазоне для этого железа."
                    ),
                    available=True,
                )

            smallest = self._pick_smallest_installed(available)
            return ModelRecommendation(
                model_name=install_target.model_name,
                label=install_target.label,
                rationale=(
                    f"{rationale} Локально уже есть только более тяжёлый профиль {smallest}. "
                    f"Для комфортной работы на этом ПК лучше поставить {install_target.model_name}."
                ),
                available=False,
            )

        return ModelRecommendation(
            model_name=install_target.model_name,
            label=install_target.label,
            rationale=f"{rationale} Нужная локальная модель пока не найдена.",
            available=False,
        )

    def _pick_install_target(self, hardware: HardwareProfile) -> str:
        for model_name, min_memory_gb in self.INSTALL_TIERS:
            if hardware.memory_gb >= min_memory_gb:
                return model_name
        return self.INSTALL_TIERS[-1][0]

    @staticmethod
    def _pick_best_installed(models: list[str], hardware: HardwareProfile, preferred_model: str) -> str:
        comfort_cap = _comfort_size_cap(hardware.memory_gb)
        ranked = sorted(models, key=lambda name: _model_rank(name, preferred_model), reverse=True)
        compatible = [
            name for name in ranked
            if (size_b := _model_size_b(name)) is None or size_b <= comfort_cap + 0.05
        ]
        return compatible[0] if compatible else ""

    @staticmethod
    def _pick_smallest_installed(models: list[str]) -> str:
        ranked = sorted(models, key=lambda name: (_model_size_b(name) or 999.0, -_family_rank(name)))
        return ranked[0] if ranked else ""

    @staticmethod
    def _family_label(model_name: str) -> str:
        lower = model_name.lower()
        if lower.startswith("qwen"):
            return "Qwen-модель"
        if "gemma" in lower:
            return "Gemma-модель"
        if "llama" in lower:
            return "Llama-модель"
        return "локальная LLM-модель"

    @staticmethod
    def _detect_memory_gb() -> float:
        system = platform.system().lower()
        if system == "windows":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memoryLoad", ctypes.c_ulong),
                    ("totalPhys", ctypes.c_ulonglong),
                    ("availPhys", ctypes.c_ulonglong),
                    ("totalPageFile", ctypes.c_ulonglong),
                    ("availPageFile", ctypes.c_ulonglong),
                    ("totalVirtual", ctypes.c_ulonglong),
                    ("availVirtual", ctypes.c_ulonglong),
                    ("availExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.totalPhys / (1024 ** 3)
        if system == "darwin":
            output = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(output) / (1024 ** 3)
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 ** 2)
        return 8.0


def _model_rank(name: str, preferred_model: str) -> tuple[int, int, float, int]:
    lower = name.lower()
    preferred = 1 if name == preferred_model else 0
    family_rank = _family_rank(name)
    size_rank = _model_size_b(name) or 0.0
    variant_bonus = 1 if "instruct" in lower or "latest" in lower else 0
    return (family_rank, preferred, size_rank, variant_bonus)


def _family_rank(name: str) -> int:
    lower = name.lower()
    if lower.startswith("qwen3"):
        return 5
    if lower.startswith("qwen"):
        return 4
    if "gemma" in lower:
        return 3
    if "llama" in lower:
        return 1
    return 0


def _model_size_b(name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*b", name.lower())
    if match is None:
        return None
    return float(match.group(1))


def _comfort_size_cap(memory_gb: float) -> float:
    if memory_gb >= 32:
        return 14.0
    if memory_gb >= 20:
        return 8.0
    if memory_gb >= 12:
        return 4.0
    if memory_gb >= 8:
        return 1.7
    return 0.6
