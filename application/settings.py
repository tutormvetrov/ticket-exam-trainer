from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.platform import default_models_path
from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE

DEFAULT_OLLAMA_MODEL = "qwen3:8b"

@dataclass(slots=True)
class OllamaSettings:
    base_url: str = "http://localhost:11434"
    model: str = DEFAULT_OLLAMA_MODEL
    models_path: Path = field(default_factory=default_models_path)
    timeout_seconds: int = 60
    rewrite_questions: bool = True
    examiner_followups: bool = True
    rule_based_fallback: bool = True
    theme_name: str = "light"
    startup_view: str = "library"
    auto_check_ollama_on_start: bool = True
    show_dlc_teaser: bool = True
    default_import_dir: Path = Path.home()
    preferred_import_format: str = "docx"
    import_llm_assist: bool = False
    default_training_mode: str = "active-recall"
    review_mode: str = "standard_adaptive"
    training_queue_size: int = 8
    font_preset: str = DEFAULT_FONT_PRESET
    font_size: int = DEFAULT_FONT_SIZE
    auto_check_updates_on_start: bool = True


DEFAULT_OLLAMA_SETTINGS = OllamaSettings()
