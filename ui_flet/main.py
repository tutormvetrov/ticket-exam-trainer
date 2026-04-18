"""Entry point: python -m ui_flet.main.

Wires AppFacade to an ft.app and runs the three-route UI.

Startup choreography
--------------------
1. ``_configure_page`` sets static page chrome (title, fonts, min size).
2. The persisted ``window_mode`` from ``OllamaSettings`` decides whether the
   window opens fullscreen or in a sized window (defaults to fullscreen, which
   is what spec 3.5a asks for).
3. ``state.probe_ollama()`` fires a background probe of ``127.0.0.1:11434``
   right after the theme is applied — workspaces treat ``ollama_online=None``
   as offline so there's no window in which the UI can accidentally spin up
   a 60s LLM call.
4. Key bindings: ``Escape`` leaves fullscreen (drops back to the saved
   windowed size). A small floating action button at top-right of the page
   lets the user toggle fullscreen without opening Settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import flet as ft

# Reuse the same workspace/bootstrap logic as the Qt app so seed DB, settings,
# and migrations resolve identically.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.paths import get_workspace_root
from application.facade import AppFacade
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path

from ui_flet.state import AppState
from ui_flet.router import on_route_change
from ui_flet.theme.theme import apply_theme
from ui_flet.theme.fonts import font_map


def _build_facade() -> tuple[AppFacade, Path]:
    workspace_root = get_workspace_root()
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)
    return facade, database_path


def _on_resize(state: AppState):
    def _handler(_event: ft.WindowEvent) -> None:
        width = state.page.window.width or state.page.width or 1280
        if state.update_breakpoint(float(width)):
            state.page.update()
    return _handler


def _configure_page(page: ft.Page) -> None:
    page.title = "Тезис — подготовка к письменному госэкзамену"
    page.padding = 0
    page.spacing = 0
    page.fonts = font_map()
    page.window.min_width = 1024
    page.window.min_height = 700


def _apply_window_mode(page: ft.Page, mode: str, width: int, height: int) -> None:
    """Translate ``window_mode`` persistence into Flet window props."""
    if mode == "fullscreen":
        page.window.full_screen = True
    else:
        page.window.full_screen = False
        page.window.width = float(width)
        page.window.height = float(height)


def _install_keyboard_handler(state: AppState) -> None:
    """Esc leaves fullscreen → falls back to the persisted windowed size."""

    def _on_keyboard(event: ft.KeyboardEvent) -> None:
        key = getattr(event, "key", "") or ""
        if key == "Escape" and state.page.window.full_screen:
            settings = getattr(state.facade, "settings", None)
            width = int(getattr(settings, "window_width", 1440) or 1440)
            height = int(getattr(settings, "window_height", 900) or 900)
            _apply_window_mode(state.page, "windowed", width, height)
            # Persist the switch so re-launches match what the user sees.
            _persist_window_mode(state, "windowed")
            state.page.update()

    state.page.on_keyboard_event = _on_keyboard


def _persist_window_mode(state: AppState, mode: str) -> None:
    """Write the current mode back to settings.json (best-effort)."""
    try:
        from dataclasses import replace

        current = state.facade.settings
        if current.window_mode == mode:
            return
        state.facade.save_settings(replace(current, window_mode=mode))
    except Exception:
        # Never let persistence break the UI — the live page already reflects
        # the new mode.
        pass


def _build_fullscreen_toggle(state: AppState) -> ft.FloatingActionButton:
    """A tiny floating toggle for fullscreen / windowed.

    Kept in ``main.py`` rather than ``top_bar.py`` because the sibling agent
    owns TopBar and the task forbids editing it. The FAB sits at the top-right
    of the page (mini size, subtle) and flips the same state as the Settings
    segmented button.
    """

    def _icon_for_mode() -> str:
        return (
            ft.Icons.FULLSCREEN_EXIT
            if state.page.window.full_screen
            else ft.Icons.FULLSCREEN
        )

    fab = ft.FloatingActionButton(
        icon=_icon_for_mode(),
        mini=True,
        tooltip="Полноэкранный / оконный",
    )

    def _on_click(_evt: ft.ControlEvent) -> None:
        new_mode = "windowed" if state.page.window.full_screen else "fullscreen"
        settings = getattr(state.facade, "settings", None)
        width = int(getattr(settings, "window_width", 1440) or 1440)
        height = int(getattr(settings, "window_height", 900) or 900)
        _apply_window_mode(state.page, new_mode, width, height)
        _persist_window_mode(state, new_mode)
        fab.icon = _icon_for_mode()
        try:
            fab.update()
        except Exception:
            pass
        state.page.update()

    fab.on_click = _on_click
    return fab


def _main(page: ft.Page) -> None:
    _configure_page(page)
    facade, _ = _build_facade()
    state = AppState(page=page, facade=facade)

    settings = getattr(facade, "settings", None)
    saved_window_mode = getattr(settings, "window_mode", "fullscreen") or "fullscreen"
    saved_window_width = int(getattr(settings, "window_width", 1440) or 1440)
    saved_window_height = int(getattr(settings, "window_height", 900) or 900)
    _apply_window_mode(page, saved_window_mode, saved_window_width, saved_window_height)

    # Initial theme — read from settings (fallback: light)
    theme_name = getattr(settings, "theme_name", "light") if settings else "light"
    state.is_dark = theme_name == "dark"
    apply_theme(page, state.is_dark)

    # Kick the background Ollama probe immediately after theme is applied.
    # Workspaces guard themselves against ``ollama_online is None`` so it's
    # safe for the probe to resolve asynchronously — we just surface the
    # result via ``state.is_ollama_available()``.
    state.probe_ollama()

    # Re-apply theme on toggle
    def _on_theme_change() -> None:
        apply_theme(page, state.is_dark)
        page.update()
    state.on_theme_change(_on_theme_change)

    page.on_route_change = on_route_change(state)
    page.window.on_event = _on_resize(state)

    _install_keyboard_handler(state)

    # Floating FAB for fullscreen toggle. ``page.floating_action_button`` is
    # the Flet-native slot; placing it via ``page.overlay`` would stack it over
    # dialogs, which we don't want.
    page.floating_action_button = _build_fullscreen_toggle(state)
    page.floating_action_button_location = ft.FloatingActionButtonLocation.END_TOP

    # Initial width sync
    if page.width:
        state.update_breakpoint(float(page.width))

    page.go(page.route or "/tickets")


def main() -> None:
    ft.app(target=_main)


if __name__ == "__main__":
    main()
