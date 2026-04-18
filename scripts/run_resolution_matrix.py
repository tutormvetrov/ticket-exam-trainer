"""Snapshot smoke across the 5 target resolution classes (spec Part 3.3).

Builds every view at every breakpoint against the real seed DB and asserts
no exceptions. Flet doesn't ship a true offscreen renderer, but building the
control tree reliably surfaces layout logic errors (wrong expand values,
missing columns, None-dereferences) — catching the same class of bugs a
visual snapshot would, without the GUI toolkit running.

Run manually before each release:
    python scripts/run_resolution_matrix.py

Exit code 0 = all build; non-zero = first failure printed with traceback.
"""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

if (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# 5 canonical widths matching the spec's Part 3.3 matrix.
TARGET_WIDTHS: list[tuple[str, int, int]] = [
    ("laptop_small",    1366, 768),
    ("laptop_standard", 1440, 900),
    ("laptop_hd",       1920, 1080),
    ("desktop_wide",    2560, 1440),
    ("4k",              3840, 2160),
]


class _MockPage:
    def __init__(self, width: int, height: int):
        self.route = "/tickets"
        self.width = width
        self.height = height
        self.theme_mode = None
        self.theme = None
        self.dark_theme = None
        self.bgcolor = None
        self.views: list = []
        self.window = SimpleNamespace(
            width=width, height=height,
            min_width=1024, min_height=700,
            full_screen=False,
        )

    def update(self): pass
    def go(self, route): self.route = route


def _build_facade():
    from app.paths import get_workspace_root
    from application.facade import AppFacade
    from application.settings_store import SettingsStore
    from infrastructure.db import connect_initialized, get_database_path

    workspace_root = get_workspace_root()
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    return AppFacade(workspace_root, connection, settings_store)


def _smoke_one(name: str, width: int, height: int, facade) -> list[str]:
    from ui_flet.state import AppState
    from ui_flet.views.tickets_view import build_tickets_view
    from ui_flet.views.training_view import build_training_view
    from ui_flet.views.settings_view import build_settings_view

    errors: list[str] = []
    page = _MockPage(width, height)
    state = AppState(page=page, facade=facade)
    state.update_breakpoint(float(width))

    try:
        build_tickets_view(state)
    except Exception:
        errors.append(f"[{name} {width}x{height}] tickets_view:\n{traceback.format_exc()}")

    try:
        build_settings_view(state)
    except Exception:
        errors.append(f"[{name} {width}x{height}] settings_view:\n{traceback.format_exc()}")

    # Take the first ticket and build the training view in all 6 modes.
    try:
        first = next(iter(facade.load_ticket_maps()))
    except Exception as exc:  # pragma: no cover — requires seed DB
        errors.append(f"[{name}] could not load tickets: {exc}")
        return errors

    for mode in ("reading", "plan", "cloze", "active-recall", "state-exam-full", "review"):
        try:
            build_training_view(state, ticket_id=first.ticket_id, mode_key=mode)
        except Exception:
            errors.append(f"[{name} {width}x{height}] training_view[{mode}]:\n{traceback.format_exc()}")

    return errors


def main() -> int:
    try:
        facade = _build_facade()
    except Exception as exc:
        print(f"ERROR: could not build facade (is seed DB installed?): {exc}", file=sys.stderr)
        return 2

    total_errors: list[str] = []
    for name, width, height in TARGET_WIDTHS:
        errors = _smoke_one(name, width, height, facade)
        status = "OK " if not errors else "FAIL"
        print(f"  {status}  {name:16} {width}x{height}")
        total_errors.extend(errors)

    print()
    if total_errors:
        print(f"! {len(total_errors)} failures:", file=sys.stderr)
        for err in total_errors:
            print(err, file=sys.stderr)
        return 1

    print(f"+ all {len(TARGET_WIDTHS)} resolutions build cleanly on real seed DB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
