"""Entry point: python -m ui_flet.main.

Wires AppFacade to an ft.app and runs the three-route UI.
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
    page.window.width = 1440
    page.window.height = 900
    page.window.min_width = 1024
    page.window.min_height = 700


def _main(page: ft.Page) -> None:
    _configure_page(page)
    facade, _ = _build_facade()
    state = AppState(page=page, facade=facade)

    # Initial theme — read from settings (fallback: light)
    settings = getattr(facade, "settings", None)
    theme_name = getattr(settings, "theme_name", "light") if settings else "light"
    state.is_dark = theme_name == "dark"
    apply_theme(page, state.is_dark)

    # Re-apply theme on toggle
    def _on_theme_change() -> None:
        apply_theme(page, state.is_dark)
        page.update()
    state.on_theme_change(_on_theme_change)

    page.on_route_change = on_route_change(state)
    page.window.on_event = _on_resize(state)

    # Initial width sync
    if page.width:
        state.update_breakpoint(float(page.width))

    page.go(page.route or "/tickets")


def main() -> None:
    ft.app(target=_main)


if __name__ == "__main__":
    main()
