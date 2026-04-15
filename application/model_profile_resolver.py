from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import platform
import re
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
        available = [name for name in diagnostics.available_models if name]

        target = preferred_model
        rationale = f"RAM: {hardware.memory_gb:.1f} GB, threads: {hardware.cpu_threads}."
        if available:
            target = self._pick_best_installed(available, hardware.memory_gb, preferred_model)
            return ModelRecommendation(
                model_name=target,
                label=f"Рекомендуемая модель: {target}",
                rationale=f"{rationale} Выбрана самая сильная доступная локально {self._family_label(target)} для этого железа.",
                available=True,
            )
        return ModelRecommendation(
            model_name=preferred_model,
            label=f"Рекомендуемая модель: {preferred_model}",
            rationale=f"{rationale} Нужная локальная модель пока не найдена.",
            available=diagnostics.endpoint_ok and diagnostics.model_ok,
        )

    @staticmethod
    def _pick_best_installed(models: list[str], memory_gb: float, preferred_model: str) -> str:
        ranked = sorted(models, key=lambda name: _model_rank(name, preferred_model), reverse=True)
        if memory_gb < 18:
            for size_token in ("8b", "7b", "9b", "6b"):
                for name in ranked:
                    if size_token in name.lower():
                        return name
        if memory_gb < 24:
            for size_token in ("12b", "14b", "8b", "7b"):
                for name in ranked:
                    if size_token in name.lower():
                        return name
        if memory_gb < 32:
            for size_token in ("14b", "12b", "8b", "7b"):
                for name in ranked:
                    if size_token in name.lower():
                        return name
        return ranked[0]

    @staticmethod
    def _family_label(model_name: str) -> str:
        lower = model_name.lower()
        if lower.startswith("qwen"):
            return "Qwen-модель"
        if "gemma" in lower:
            return "Gemma-модель"
        if "mistral" in lower:
            return "Mistral-модель"
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


def _model_rank(name: str, preferred_model: str) -> tuple[int, int, int, int]:
    lower = name.lower()
    preferred = 1 if name == preferred_model else 0
    family_rank = 0
    if lower.startswith("qwen3"):
        family_rank = 5
    elif lower.startswith("qwen"):
        family_rank = 4
    elif "gemma" in lower:
        family_rank = 3
    elif "mistral" in lower:
        family_rank = 2
    elif "llama" in lower:
        family_rank = 1
    size_match = re.search(r"(\d+)\s*b", lower)
    size_rank = int(size_match.group(1)) if size_match else 0
    variant_bonus = 1 if "instruct" in lower or "latest" in lower else 0
    return (family_rank, preferred, size_rank, variant_bonus)
