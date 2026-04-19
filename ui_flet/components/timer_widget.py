"""TimerWidget — reusable count-up / count-down timer.

Uses threading.Timer for the tick loop (Flet 0.27 — page.run_task is
available too, but a threading ticker is friction-free for a plain
seconds counter). On every tick we mutate `self._seconds`, update the
label, and call `page.update()`.

Public API:
    TimerWidget(page, mode="count_up", initial_seconds=0, on_finish=None)
    .start() / .pause() / .reset()
    .build() -> ft.Control               # the control to mount

Count-down finishes automatically at 0; caller can pass `on_finish`.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import flet as ft

from ui_flet.i18n.ru import TEXT
from ui_flet.theme.tokens import RADIUS, SPACE, palette


def _format_mmss(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


class TimerWidget:
    def __init__(
        self,
        page: ft.Page,
        *,
        is_dark: bool,
        mode: str = "count_up",   # "count_up" | "count_down"
        initial_seconds: int = 0,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        if mode not in ("count_up", "count_down"):
            raise ValueError(f"TimerWidget: unknown mode {mode!r}")
        self.page = page
        self.is_dark = is_dark
        self.mode = mode
        self.initial_seconds = int(initial_seconds)
        self._seconds = int(initial_seconds)
        self._running = False
        self._ticker: threading.Timer | None = None
        self._on_finish = on_finish

        self._label = ft.Text(
            _format_mmss(self._seconds),
            size=22,
            weight=ft.FontWeight.W_600,
        )
        self._toggle_btn = ft.FilledTonalButton(
            text=TEXT["timer.start"],
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_toggle,
        )
        self._reset_btn = ft.OutlinedButton(
            text=TEXT["action.retry"],
            icon=ft.Icons.RESTART_ALT,
            on_click=lambda _: self.reset(),
        )
        self._control = self._build()

    # ---- public API ----

    @property
    def control(self) -> ft.Control:
        return self._control

    def build(self) -> ft.Control:
        return self._control

    def seconds_elapsed(self) -> int:
        """Return seconds elapsed since start (monotonic-ish).

        For count-up: returns the current counter.
        For count-down: returns initial_seconds - current counter.
        """
        if self.mode == "count_up":
            return int(self._seconds)
        return max(0, int(self.initial_seconds - self._seconds))

    def seconds_remaining(self) -> int:
        if self.mode == "count_down":
            return max(0, int(self._seconds))
        return 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._update_toggle_label()
        self._schedule_tick()
        self._safe_update()

    def pause(self) -> None:
        self._running = False
        self._cancel_tick()
        self._update_toggle_label()
        self._safe_update()

    def reset(self, *, new_initial_seconds: int | None = None) -> None:
        self._running = False
        self._cancel_tick()
        if new_initial_seconds is not None:
            self.initial_seconds = int(new_initial_seconds)
        self._seconds = int(self.initial_seconds)
        self._label.value = _format_mmss(self._seconds)
        self._update_toggle_label()
        self._safe_update()

    def set_initial(self, new_initial_seconds: int) -> None:
        """Replace the initial (and current) value without starting."""
        self.reset(new_initial_seconds=new_initial_seconds)

    def dispose(self) -> None:
        self._running = False
        self._cancel_tick()

    # ---- internal ----

    def _build(self) -> ft.Control:
        p = palette(self.is_dark)
        return ft.Container(
            padding=SPACE["md"],
            bgcolor=p["bg_elevated"],
            border_radius=RADIUS["md"],
            border=ft.border.all(1, p["border_soft"]),
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TIMER, color=p["accent"], size=18),
                            ft.Text(TEXT["timer.elapsed"], size=13, color=p["text_secondary"]),
                            self._label,
                        ],
                        spacing=SPACE["sm"],
                    ),
                    ft.Row(
                        controls=[self._toggle_btn, self._reset_btn],
                        spacing=SPACE["sm"],
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    def _schedule_tick(self) -> None:
        if not self._running:
            return
        self._cancel_tick()
        ticker = threading.Timer(1.0, self._on_tick)
        ticker.daemon = True
        self._ticker = ticker
        ticker.start()

    def _cancel_tick(self) -> None:
        if self._ticker is not None:
            try:
                self._ticker.cancel()
            except Exception:
                pass
            self._ticker = None

    def _on_tick(self) -> None:
        if not self._running:
            return
        if self.mode == "count_up":
            self._seconds += 1
        else:
            self._seconds = max(0, self._seconds - 1)

        self._label.value = _format_mmss(self._seconds)
        self._safe_update()

        if self.mode == "count_down" and self._seconds == 0:
            self._running = False
            self._update_toggle_label()
            self._safe_update()
            if self._on_finish:
                try:
                    self._on_finish()
                except Exception:
                    pass
            return
        self._schedule_tick()

    def _update_toggle_label(self) -> None:
        if self._running:
            self._toggle_btn.text = TEXT["timer.pause"]
            self._toggle_btn.icon = ft.Icons.PAUSE
        else:
            self._toggle_btn.text = TEXT["timer.start"]
            self._toggle_btn.icon = ft.Icons.PLAY_ARROW

    def _on_toggle(self, _evt) -> None:
        if self._running:
            self.pause()
        else:
            self.start()

    def _safe_update(self) -> None:
        try:
            self._label.update()
            self._toggle_btn.update()
        except Exception:
            pass
        try:
            self.page.update()
        except Exception:
            pass
