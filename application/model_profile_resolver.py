from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import platform
import subprocess

from application.defense_ui_data import ModelRecommendation
from infrastructure.ollama.service import OllamaDiagnostics, OllamaService


@dataclass(slots=True)
class HardwareProfile:
    memory_gb: float
    cpu_threads: int
    platform_name: str


class ModelProfileResolver:
    def detect_hardware(self) -> HardwareProfile:
        return HardwareProfile(
            memory_gb=self._detect_memory_gb(),
            cpu_threads=max(1, os.cpu_count() or 1),
            platform_name=platform.system().lower(),
        )

    def recommend(self, service: OllamaService, preferred_model: str) -> ModelRecommendation:
        hardware = self.detect_hardware()
        diagnostics = service.inspect(preferred_model)
        available = diagnostics.available_models
        installed_mistral = [name for name in available if "mistral" in name.lower()]

        target = preferred_model
        rationale = f"RAM: {hardware.memory_gb:.1f} GB, threads: {hardware.cpu_threads}."
        if installed_mistral:
            target = self._pick_best_installed(installed_mistral, hardware.memory_gb, preferred_model)
            return ModelRecommendation(
                model_name=target,
                label=f"Рекомендуемая модель: {target}",
                rationale=f"{rationale} Выбрана самая сильная доступная локально Mistral-модель.",
                available=True,
            )
        return ModelRecommendation(
            model_name=preferred_model,
            label=f"Рекомендуемая модель: {preferred_model}",
            rationale=f"{rationale} Других локально доступных Mistral-моделей не найдено.",
            available=diagnostics.endpoint_ok and diagnostics.model_ok,
        )

    @staticmethod
    def _pick_best_installed(models: list[str], memory_gb: float, preferred_model: str) -> str:
        ranked = sorted(models, key=lambda name: _model_rank(name, preferred_model), reverse=True)
        if memory_gb < 12:
            for name in ranked:
                if "7b" in name.lower() or name.lower() == "mistral:instruct":
                    return name
        if memory_gb < 24:
            for name in ranked:
                if "12b" in name.lower() or "nemo" in name.lower():
                    return name
        return ranked[0]

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


def _model_rank(name: str, preferred_model: str) -> tuple[int, int, int]:
    lower = name.lower()
    preferred = 1 if name == preferred_model else 0
    if "24b" in lower:
        return (3, preferred, len(name))
    if "12b" in lower or "nemo" in lower:
        return (2, preferred, len(name))
    if "7b" in lower or "instruct" in lower:
        return (1, preferred, len(name))
    return (0, preferred, len(name))
