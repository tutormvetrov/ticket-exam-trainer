from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import requests


@dataclass(slots=True)
class OllamaResponse:
    ok: bool
    status_code: int
    payload: dict[str, Any]
    latency_ms: int | None
    error: str = ""


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float | None = 2.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_tags(self) -> OllamaResponse:
        return self._request("GET", "/api/tags")

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
        return self._request("POST", "/api/generate", payload=payload)

    def _request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> OllamaResponse:
        started = perf_counter()
        try:
            response = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=self.timeout_seconds,
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
