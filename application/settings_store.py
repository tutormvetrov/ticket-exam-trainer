from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> OllamaSettings:
        if not self.path.exists():
            return OllamaSettings(
                base_url=DEFAULT_OLLAMA_SETTINGS.base_url,
                model=DEFAULT_OLLAMA_SETTINGS.model,
                models_path=DEFAULT_OLLAMA_SETTINGS.models_path,
                timeout_seconds=DEFAULT_OLLAMA_SETTINGS.timeout_seconds,
                rewrite_questions=DEFAULT_OLLAMA_SETTINGS.rewrite_questions,
                examiner_followups=DEFAULT_OLLAMA_SETTINGS.examiner_followups,
                rule_based_fallback=DEFAULT_OLLAMA_SETTINGS.rule_based_fallback,
                theme_name=DEFAULT_OLLAMA_SETTINGS.theme_name,
                startup_view=DEFAULT_OLLAMA_SETTINGS.startup_view,
                auto_check_ollama_on_start=DEFAULT_OLLAMA_SETTINGS.auto_check_ollama_on_start,
                show_dlc_teaser=DEFAULT_OLLAMA_SETTINGS.show_dlc_teaser,
                default_import_dir=DEFAULT_OLLAMA_SETTINGS.default_import_dir,
                preferred_import_format=DEFAULT_OLLAMA_SETTINGS.preferred_import_format,
                import_llm_assist=DEFAULT_OLLAMA_SETTINGS.import_llm_assist,
                default_training_mode=DEFAULT_OLLAMA_SETTINGS.default_training_mode,
                review_mode=DEFAULT_OLLAMA_SETTINGS.review_mode,
                training_queue_size=DEFAULT_OLLAMA_SETTINGS.training_queue_size,
            )

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return OllamaSettings(
            base_url=payload.get("base_url", DEFAULT_OLLAMA_SETTINGS.base_url),
            model=payload.get("model", DEFAULT_OLLAMA_SETTINGS.model),
            models_path=Path(payload.get("models_path", str(DEFAULT_OLLAMA_SETTINGS.models_path))),
            timeout_seconds=int(payload.get("timeout_seconds", DEFAULT_OLLAMA_SETTINGS.timeout_seconds)),
            rewrite_questions=bool(payload.get("rewrite_questions", DEFAULT_OLLAMA_SETTINGS.rewrite_questions)),
            examiner_followups=bool(payload.get("examiner_followups", DEFAULT_OLLAMA_SETTINGS.examiner_followups)),
            rule_based_fallback=bool(payload.get("rule_based_fallback", DEFAULT_OLLAMA_SETTINGS.rule_based_fallback)),
            theme_name=payload.get("theme_name", DEFAULT_OLLAMA_SETTINGS.theme_name),
            startup_view=payload.get("startup_view", DEFAULT_OLLAMA_SETTINGS.startup_view),
            auto_check_ollama_on_start=bool(payload.get("auto_check_ollama_on_start", DEFAULT_OLLAMA_SETTINGS.auto_check_ollama_on_start)),
            show_dlc_teaser=bool(payload.get("show_dlc_teaser", DEFAULT_OLLAMA_SETTINGS.show_dlc_teaser)),
            default_import_dir=Path(payload.get("default_import_dir", str(DEFAULT_OLLAMA_SETTINGS.default_import_dir))),
            preferred_import_format=payload.get("preferred_import_format", DEFAULT_OLLAMA_SETTINGS.preferred_import_format),
            import_llm_assist=bool(payload.get("import_llm_assist", DEFAULT_OLLAMA_SETTINGS.import_llm_assist)),
            default_training_mode=payload.get("default_training_mode", DEFAULT_OLLAMA_SETTINGS.default_training_mode),
            review_mode=payload.get("review_mode", DEFAULT_OLLAMA_SETTINGS.review_mode),
            training_queue_size=int(payload.get("training_queue_size", DEFAULT_OLLAMA_SETTINGS.training_queue_size)),
        )

    def save(self, settings: OllamaSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        payload["models_path"] = str(settings.models_path)
        payload["default_import_dir"] = str(settings.default_import_dir)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
