"""OllamaStatusBadge — compact pill showing live Ollama connectivity status.

Design goal: a small pill (icon + text) that reflects whether the local
Ollama endpoint responds. Green when the endpoint answers within a short
budget, muted/warning when offline. The badge also shows which model is
currently configured (truncated for short names like ``qwen3:8b``).

Probe strategy:

- Background ``threading.Thread`` runs ``service.client.get_tags()`` (which
  hits ``/api/tags`` with the short ``inspect_timeout_seconds`` of 3s).
- No sync probes on the UI thread — the badge builds instantly in the
  ``unknown`` state and flips to ``ok`` / ``offline`` when the probe
  resolves. ``page.update()`` is invoked safely from the worker via the
  Flet page bound to the badge controls.
- Auto-polling: a daemon thread re-probes every ``poll_interval_sec``. A
  manual ``probe_now()`` is exposed so the Settings "Проверить соединение"
  button can force an immediate check.

The badge never throws — any exception maps to the ``offline`` state so
the UI stays usable even when ``requests`` or the runtime raise.
"""

from __future__ import annotations

import threading
from typing import Callable, Literal

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.theme.tokens import RADIUS, SPACE, palette

Status = Literal["unknown", "ok", "offline", "error"]


class OllamaStatusBadge:
    """Small live-status pill for Ollama connectivity.

    Usage::

        badge = OllamaStatusBadge(state, poll_interval_sec=15)
        control = badge.build()  # attach this to the layout
        ...
        badge.probe_now()        # on "Test connection" button click
        badge.dispose()          # when view unmounts (optional)
    """

    def __init__(
        self,
        state,
        poll_interval_sec: float = 15.0,
        on_change: Callable[[Status], None] | None = None,
    ) -> None:
        self._state = state
        self._poll_interval_sec = max(3.0, float(poll_interval_sec))
        self._on_change = on_change
        self._status: Status = "unknown"
        self._latency_ms: int | None = None
        self._model_name: str = self._current_model()
        self._container: ft.Container | None = None
        self._icon: ft.Icon | None = None
        self._label: ft.Text | None = None
        self._dot: ft.Container | None = None
        self._stop_event = threading.Event()
        self._probe_lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None

    # ---------------- public API ----------------

    @property
    def status(self) -> Status:
        return self._status

    def build(self) -> ft.Control:
        p = palette(self._state.is_dark)
        self._dot = ft.Container(
            width=8,
            height=8,
            border_radius=RADIUS["pill"],
            bgcolor=p["text_muted"],
        )
        self._icon = ft.Icon(name=ft.Icons.CIRCLE_OUTLINED, size=14, color=p["text_muted"])
        self._label = ft.Text(
            self._build_label_text(),
            size=12,
            color=p["text_secondary"],
            weight=ft.FontWeight.W_500,
        )
        self._container = ft.Container(
            padding=ft.padding.symmetric(vertical=SPACE["xs"], horizontal=SPACE["sm"]),
            border_radius=RADIUS["pill"],
            bgcolor=p["bg_elevated"],
            border=ft.border.all(1, p["border_soft"]),
            content=ft.Row(
                spacing=SPACE["xs"],
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[self._dot, self._label],
            ),
            on_click=lambda _e: self.probe_now(),
            tooltip=TEXT["settings.ollama.test"],
        )
        self._apply_visuals()
        self._start_polling()
        return self._container

    def probe_now(self) -> None:
        """Trigger an immediate probe in a background thread (non-blocking)."""
        threading.Thread(target=self._probe_once, daemon=True).start()

    def set_model(self, model_name: str) -> None:
        """Reflect a newly-selected model in the badge label."""
        self._model_name = (model_name or "").strip() or self._current_model()
        if self._label is not None:
            self._label.value = self._build_label_text()
            self._safe_update()

    def dispose(self) -> None:
        self._stop_event.set()

    # ---------------- internals ----------------

    def _current_model(self) -> str:
        try:
            return getattr(self._state.facade.settings, "model", "") or ""
        except Exception:
            return ""

    def _start_polling(self) -> None:
        if self._poll_thread is not None and self._poll_thread.is_alive():
            return

        def _runner() -> None:
            # Kick an immediate probe so "unknown" resolves quickly.
            self._probe_once()
            while not self._stop_event.wait(self._poll_interval_sec):
                self._probe_once()

        self._poll_thread = threading.Thread(target=_runner, daemon=True)
        self._poll_thread.start()

    def _probe_once(self) -> None:
        # Guard against overlapping probes (e.g., interval fires while a
        # manual probe is still in flight).
        if not self._probe_lock.acquire(blocking=False):
            return
        try:
            new_status: Status = "offline"
            latency_ms: int | None = None
            try:
                service = self._state.facade.build_ollama_service()
                response = service.client.get_tags()
                latency_ms = response.latency_ms
                if response.ok:
                    new_status = "ok"
                else:
                    new_status = "offline"
            except Exception:
                new_status = "error"

            self._model_name = self._current_model()
            changed = new_status != self._status
            self._status = new_status
            self._latency_ms = latency_ms

            if self._container is not None:
                self._apply_visuals()
                self._safe_update()

            if changed and self._on_change is not None:
                try:
                    self._on_change(new_status)
                except Exception:
                    pass
        finally:
            self._probe_lock.release()

    def _apply_visuals(self) -> None:
        if self._container is None or self._label is None or self._dot is None:
            return
        p = palette(self._state.is_dark)

        if self._status == "ok":
            dot_color = p["success"]
            border_color = p["success"]
            text_color = p["text_primary"]
        elif self._status == "offline":
            dot_color = p["warning"]
            border_color = p["border_medium"]
            text_color = p["text_secondary"]
        elif self._status == "error":
            dot_color = p["danger"]
            border_color = p["danger"]
            text_color = p["text_secondary"]
        else:  # unknown
            dot_color = p["text_muted"]
            border_color = p["border_soft"]
            text_color = p["text_muted"]

        self._dot.bgcolor = dot_color
        self._container.border = ft.border.all(1, border_color)
        self._container.bgcolor = p["bg_elevated"]
        self._label.color = text_color
        self._label.value = self._build_label_text()

    def _build_label_text(self) -> str:
        model = self._model_name or self._current_model()
        if self._status == "ok":
            head = TEXT["ollama.ok"]
        elif self._status in ("offline", "error"):
            head = TEXT["ollama.offline"]
        else:
            head = TEXT["settings.ollama.status"].rstrip(":")
        if model:
            return f"{head} · {model}"
        return head

    def _safe_update(self) -> None:
        if self._container is None:
            return
        try:
            # `page` may be None if the control hasn't been attached yet.
            page = getattr(self._container, "page", None)
            if page is not None:
                self._container.update()
        except Exception:
            # Control was removed from the page (view switch) — nothing to do.
            pass
