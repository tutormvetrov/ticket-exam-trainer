from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from app.platform import default_models_path
from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE

DEFAULT_OLLAMA_MODEL = "qwen3:8b"


def validate_ollama_base_url(url: str) -> tuple[bool, str]:
    """Accepts only localhost/loopback or private LAN ranges for Ollama endpoint.

    Returns (is_ok, error_message). Empty message on success.
    """
    text = (url or "").strip()
    if not text:
        return False, "Адрес API не может быть пустым."
    try:
        parsed = urlparse(text)
    except ValueError:
        return False, "Не удалось разобрать адрес API."
    if parsed.scheme not in ("http", "https"):
        return False, "Адрес API должен начинаться с http:// или https://."
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "В адресе API не указан хост."
    if host in ("localhost", "ip6-localhost"):
        return True, ""
    try:
        addr = ip_address(host)
    except ValueError:
        return (
            False,
            "Разрешены только локальные адреса: localhost, 127.x, ::1 или частные LAN-сети.",
        )
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return True, ""
    return (
        False,
        "Ollama должен быть локальным. Публичные адреса заблокированы для защиты содержимого билетов.",
    )

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
    # Window mode is consumed by the Flet entry point; Qt ignores it but we
    # persist through the same settings.json so both apps stay in sync if a
    # user toggles later.
    window_mode: str = "fullscreen"   # "fullscreen" | "windowed"
    window_width: int = 1440
    window_height: int = 900


DEFAULT_OLLAMA_SETTINGS = OllamaSettings()
