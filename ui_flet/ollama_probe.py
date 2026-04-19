"""Quick TCP/HTTP probe for the local Ollama endpoint.

The purpose of this module is to answer a single question — "is Ollama
reachable right now?" — fast enough that the UI can branch on it at
startup without the user noticing. The canonical path
``OllamaService.ensure_server_ready`` waits up to 25 seconds before
giving up; combined with the downstream ``review_answer`` retry it can
take ~60s for a single evaluation to return when Ollama is not running.

The probe here is intentionally dumb: one ``GET /api/tags`` with a short
``timeout``. Any failure (ConnectionError, Timeout, HTTPError, DNS, etc.)
maps to ``False``. The caller decides what to do with a negative result
— typically skip the LLM branch in ``facade.evaluate_answer`` via the
``skip_llm`` flag.

This module deliberately avoids importing the heavier
``infrastructure.ollama`` package so it stays cheap to call at startup
and easy to mock in tests (``requests.get`` is the only external
dependency).
"""

from __future__ import annotations

try:
    import requests  # type: ignore[import-untyped]
except Exception:  # pragma: no cover — requests is a hard runtime dep
    requests = None  # type: ignore[assignment]


def probe_ollama_now(
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 1.5,
) -> bool:
    """Return True iff ``GET {base_url}/api/tags`` responds 2xx within ``timeout``.

    Never raises — any exception (connection refused, timeout, DNS error,
    missing ``requests`` module, malformed URL) returns ``False``.

    Parameters
    ----------
    base_url:
        Full URL of the Ollama HTTP endpoint (default ``http://127.0.0.1:11434``).
    timeout:
        Seconds to wait for TCP connect + response. Keep this short —
        the caller is on the UI thread or gating a UI redraw.
    """
    if requests is None:
        return False
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
    except Exception:
        return False
    try:
        status_code = int(getattr(response, "status_code", 0) or 0)
    except Exception:
        return False
    return 200 <= status_code < 300
