"""GeminiService — обёртка над Google AI Studio (REST, без зависимости на google-genai).

Используем `requests` (уже в зависимостях). Это проще, чем тащить `google-genai`,
и не блокируется корпоративными прокси, которые иногда ломают gRPC-каналы.

Бесплатный tier (на 2026-04): Gemini 2.5 Flash — 250 RPD / 10 RPM, 1M контекст.
Ключ выдаётся за минуту в https://aistudio.google.com/.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

_LOG = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"

# Системный промпт «Спросить у эталона». Лаконичный, без воды,
# на русском, фокус на содержимом конкретного билета.
ASK_ETALON_SYSTEM = (
    "Ты — наставник магистранта при подготовке к МДЭ ГМУ. "
    "Отвечаешь экспертно, по существу, на русском языке. Опираешься на "
    "предоставленный эталонный материал по билету (тема, теория с НПА, "
    "практика с примерами, навыки, заключение, дополнения).\n\n"
    "Если вопрос вне темы билета — мягко скажи об этом и предложи открыть "
    "нужный билет. Если в эталоне нет точного ответа — скажи это честно, "
    "дай свою лучшую оценку с пометкой «по моему мнению».\n\n"
    "Ответ — короткий и плотный: 2-5 предложений. Никаких приветствий, "
    "преамбул или фраз вроде «надеюсь, помог»."
)


class GeminiError(Exception):
    """Любая ошибка вызова Gemini API."""


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str
    model: str = DEFAULT_MODEL


class GeminiService:
    """Тонкая обёртка над Gemini REST API. Stateless: ключ передаётся в init.

    Вызовы синхронные — для интерактивного чата это нормально (ответ < 5 сек).
    Streaming можно добавить позже через `:streamGenerateContent` endpoint.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, *, timeout: float = 30.0) -> None:
        key = (api_key or "").strip()
        if not key:
            # Fall back to standard Google env vars so users can keep the
            # secret out of settings.json. GOOGLE_API_KEY wins over
            # GEMINI_API_KEY — matches Google's own SDK precedence.
            key = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
        self.api_key = key
        self.model = (model or DEFAULT_MODEL).strip()
        self.timeout = timeout

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers for Gemini REST calls.

        The key lives in ``x-goog-api-key`` (official Google header) rather
        than in a ``?key=`` query param, which would leak into access logs,
        proxy logs and browser history.
        """
        return {"x-goog-api-key": self.api_key} if self.api_key else {}

    # ── Health ──────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def probe(self) -> tuple[bool, str]:
        """Быстрая проверка ключа: GET /models. Возвращает (ok, error_message)."""
        if not self.is_configured():
            return False, "API-ключ не задан"
        url = f"{API_BASE}/models"
        try:
            r = requests.get(url, headers=self._auth_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            return False, f"Сеть: {exc}"
        if r.status_code == 200:
            return True, ""
        # Парсим стандартную ошибку Google API.
        try:
            err = r.json().get("error", {}).get("message") or r.text[:200]
        except ValueError:
            err = r.text[:200]
        return False, f"HTTP {r.status_code}: {err}"

    # ── Generate ────────────────────────────────────────────────────────

    def ask(
        self,
        user_message: str,
        *,
        system_instruction: str = ASK_ETALON_SYSTEM,
        context: str = "",
        temperature: float = 0.5,
        max_output_tokens: int = 800,
    ) -> str:
        """Один вопрос — один ответ. Возвращает текст ответа.

        Контекст (если задан) встраивается в первое сообщение пользователя
        выше его вопроса. Это работает лучше, чем долгий system_instruction
        на больших объёмах эталона.
        """
        if not self.is_configured():
            raise GeminiError("API-ключ Gemini не задан в Настройках")

        url = f"{API_BASE}/models/{self.model}:generateContent"
        if context:
            full_user = (
                f"Эталон по билету:\n---\n{context.strip()}\n---\n\n"
                f"Вопрос магистранта: {user_message.strip()}"
            )
        else:
            full_user = user_message.strip()

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": full_user}]}],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_output_tokens),
            },
        }
        try:
            r = requests.post(
                url,
                headers=self._auth_headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GeminiError(f"Сеть: {exc}") from exc

        if r.status_code != 200:
            try:
                err = r.json().get("error", {}).get("message") or r.text[:200]
            except ValueError:
                err = r.text[:200]
            raise GeminiError(f"Gemini HTTP {r.status_code}: {err}")

        try:
            data = r.json()
        except ValueError as exc:
            raise GeminiError(f"Невалидный JSON ответа: {exc}") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            # Может быть safety-block — пробуем извлечь причину.
            block_reason = (data.get("promptFeedback") or {}).get("blockReason") or ""
            raise GeminiError(f"Пустой ответ модели (block_reason={block_reason or '—'})")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise GeminiError("Модель вернула пустой текст")
        return text


def ticket_context(ticket) -> str:
    """Построить контекст-блок из 6 секций билета для prompt'а."""
    if ticket is None:
        return ""
    lines: list[str] = [f"Тема билета: {ticket.title or '—'}"]
    summary = (getattr(ticket, "canonical_answer_summary", "") or "").strip()
    if summary:
        lines.append(f"\nКраткий ответ:\n{summary}")
    blocks = list(getattr(ticket, "answer_blocks", None) or [])
    if blocks:
        lines.append("\nЭталон по блокам:")
        for b in blocks:
            if getattr(b, "is_missing", False):
                continue
            content = (getattr(b, "expected_content", "") or "").strip()
            if not content:
                continue
            code_raw = getattr(b, "block_code", "")
            code = str(code_raw.value if hasattr(code_raw, "value") else code_raw).upper()
            title = getattr(b, "title", "") or code
            lines.append(f"\n[{code} — {title}]\n{content}")
    return "\n".join(lines)
