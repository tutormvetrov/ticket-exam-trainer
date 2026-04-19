"""Ollama integration."""

from infrastructure.ollama.dialogue import (
    DialogueTranscriptLine,
    DialogueTurnContext,
    DialogueTurnPayload,
    DialogueTurnResult,
)
from infrastructure.ollama.service import (
    LLMStructuringResult,
    OllamaDiagnostics,
    OllamaScenarioResult,
    OllamaService,
)

__all__ = [
    "DialogueTranscriptLine",
    "DialogueTurnContext",
    "DialogueTurnPayload",
    "DialogueTurnResult",
    "LLMStructuringResult",
    "OllamaDiagnostics",
    "OllamaScenarioResult",
    "OllamaService",
]
