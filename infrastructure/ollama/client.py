from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import requests


DEFAULT_INSPECT_TIMEOUT_SECONDS = 3.0
DEFAULT_GENERATION_TIMEOUT_SECONDS = 60.0


@dataclass(slots=True)
class OllamaResponse:
    ok: bool
    status_code: int
    payload: dict[str, Any]
    latency_ms: int | None
    error: str = ""


class OllamaClient:
    """HTTP-клиент для локального Ollama.

    Таймауты разделены:
    - `inspect_timeout_seconds` используется для быстрых проверок (tags, ping);
      короткий, чтобы UI не зависал на stale endpoint.
    - `generation_timeout_seconds` используется для `/api/generate`; должен
      быть достаточно большим для моделей вроде qwen3:8b на слабом железе.

    Параметр `timeout_seconds` оставлен для обратной совместимости: если
    указан, он трактуется как `generation_timeout_seconds`, а inspect берёт
    короткий дефолт.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float | None = None,
        *,
        inspect_timeout_seconds: float | None = None,
        generation_timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if generation_timeout_seconds is None:
            generation_timeout_seconds = (
                timeout_seconds if timeout_seconds is not None else DEFAULT_GENERATION_TIMEOUT_SECONDS
            )
        if inspect_timeout_seconds is None:
            inspect_timeout_seconds = DEFAULT_INSPECT_TIMEOUT_SECONDS
        self.inspect_timeout_seconds = inspect_timeout_seconds
        self.generation_timeout_seconds = generation_timeout_seconds
        # Совместимость: внешний код мог читать `client.timeout_seconds`.
        self.timeout_seconds = generation_timeout_seconds

    def get_tags(self) -> OllamaResponse:
        return self._request("GET", "/api/tags", timeout=self.inspect_timeout_seconds)

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: str = "",
        format_name: str | None = None,
        temperature: float = 0.2,
    ) -> OllamaResponse:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if format_name:
            payload["format"] = format_name
        return self._request("POST", "/api/generate", payload=payload, timeout=self.generation_timeout_seconds)

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> OllamaResponse:
        started = perf_counter()
        try:
            response = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            return OllamaResponse(False, 0, {}, None, str(exc))

        latency_ms = int((perf_counter() - started) * 1000)
        try:
            parsed_payload = response.json()
        except ValueError:
            parsed_payload = {}

        return OllamaResponse(
            ok=response.ok,
            status_code=response.status_code,
            payload=parsed_payload,
            latency_ms=latency_ms,
            error="" if response.ok else response.text,
        )
