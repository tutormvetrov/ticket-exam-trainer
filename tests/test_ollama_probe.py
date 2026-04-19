"""Fast-fail probe for the local Ollama endpoint.

These tests verify that ``probe_ollama_now`` returns a verdict in well under
two seconds when the endpoint is unreachable — i.e. the whole point of the
probe, which exists to avoid a 60s wait inside ``OllamaService`` during
``evaluate_answer`` when Ollama isn't running.

The tests are CI-safe: they mock ``requests.get`` so they never actually
touch the network.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from ui_flet import ollama_probe
from ui_flet.ollama_probe import probe_ollama_now


def test_probe_returns_false_on_connection_refused_quickly() -> None:
    """Simulates ``requests.get`` raising ConnectionError immediately.

    The probe should return False in well under two seconds — the point of
    the probe is to avoid the 60s wait inside ``OllamaService.ensure_server_ready``.
    """
    # Emulate the common case: Ollama not running → TCP connect refused.
    import requests

    def _raise(*_args, **_kwargs):
        raise requests.ConnectionError("connection refused")

    started = time.monotonic()
    with patch.object(ollama_probe.requests, "get", side_effect=_raise):
        result = probe_ollama_now("http://127.0.0.1:11434", timeout=1.0)
    elapsed = time.monotonic() - started

    assert result is False
    assert elapsed < 2.0, f"probe took too long: {elapsed:.2f}s"


def test_probe_returns_false_on_timeout() -> None:
    """Timeout exceptions must also map to False, never bubble up."""
    import requests

    def _raise(*_args, **_kwargs):
        raise requests.Timeout("timeout")

    with patch.object(ollama_probe.requests, "get", side_effect=_raise):
        assert probe_ollama_now("http://127.0.0.1:11434", timeout=0.5) is False


def test_probe_returns_true_on_200() -> None:
    """Happy path — a 200 response hands back True."""

    class _Resp:
        status_code = 200

    with patch.object(ollama_probe.requests, "get", return_value=_Resp()):
        assert probe_ollama_now("http://127.0.0.1:11434", timeout=1.0) is True


def test_probe_returns_false_on_5xx() -> None:
    """Non-2xx responses are offline from the UI's perspective."""

    class _Resp:
        status_code = 503

    with patch.object(ollama_probe.requests, "get", return_value=_Resp()):
        assert probe_ollama_now("http://127.0.0.1:11434", timeout=1.0) is False


def test_probe_never_raises_on_generic_exception() -> None:
    """Any surprise exception from the transport layer maps to False."""
    with patch.object(ollama_probe.requests, "get", side_effect=RuntimeError("boom")):
        assert probe_ollama_now("http://127.0.0.1:11434", timeout=1.0) is False


def test_state_probe_updates_flag_and_notifies_listeners() -> None:
    """AppState.probe_ollama drives ``ollama_online`` and fires listeners."""
    from types import SimpleNamespace

    from ui_flet.state import AppState

    class _Page:
        def __init__(self) -> None:
            self.route = "/"

        def go(self, route: str) -> None:
            self.route = route

        def update(self) -> None:
            pass

    facade = SimpleNamespace(settings=SimpleNamespace(base_url="http://127.0.0.1:11434"))
    state = AppState(page=_Page(), facade=facade)

    hits: list[bool | None] = []
    state.on_ollama_change(lambda v: hits.append(v))

    # Force the probe worker to return False synchronously by patching the
    # underlying probe_ollama_now symbol the AppState imports.
    with patch("ui_flet.ollama_probe.probe_ollama_now", return_value=False):
        state.probe_ollama(timeout=0.1)
        # The worker thread is daemon — give it up to 2s to finish.
        for _ in range(200):
            if state.ollama_online is not None:
                break
            time.sleep(0.01)

    assert state.ollama_online is False
    assert state.is_ollama_available() is False
    assert hits == [False]


def test_is_ollama_available_is_safe_default_when_not_probed() -> None:
    from types import SimpleNamespace

    from ui_flet.state import AppState

    class _Page:
        route = "/"

        def go(self, route: str) -> None:
            self.route = route

        def update(self) -> None:
            pass

    state = AppState(page=_Page(), facade=SimpleNamespace())
    assert state.ollama_online is None
    assert state.is_ollama_available() is False
