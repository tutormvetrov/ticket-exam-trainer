from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.platform import default_models_path

@dataclass(slots=True)
class OllamaSettings:
    base_url: str = "http://localhost:11434"
    model: str = "mistral:instruct"
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
    import_llm_assist: bool = True
    default_training_mode: str = "active-recall"
    review_mode: str = "standard_adaptive"
    training_queue_size: int = 8


DEFAULT_OLLAMA_SETTINGS = OllamaSettings()
