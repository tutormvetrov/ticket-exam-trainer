"""Ollama integration."""

from infrastructure.ollama.service import (
    LLMStructuringResult,
    OllamaDiagnostics,
    OllamaScenarioResult,
    OllamaService,
)
from infrastructure.ollama.dialogue import DialogueTranscriptLine, DialogueTurnContext, DialogueTurnPayload, DialogueTurnResult

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
