"""Run ui_flet in browser mode for screenshot automation.

Launches the same _main target as ui_flet.main but via AppView.WEB_BROWSER on
a fixed port so an external tool can navigate and capture views.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import flet as ft

from ui_flet.main import _main

if __name__ == "__main__":
    ft.app(target=_main, view=ft.AppView.WEB_BROWSER, port=8551)
