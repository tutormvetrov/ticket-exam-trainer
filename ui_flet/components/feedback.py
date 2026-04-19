"""Единый helper для ненавязчивых snackbar-уведомлений.

Один вызов — `show_snackbar(state, "строка")`. Обёртка вокруг Flet
`Page.open(SnackBar(...))` с fallback'ом на legacy `show_snack_bar` и
молчаливым swallow исключений — UI не должен падать, если всплывашка
не смогла показаться.
"""

from __future__ import annotations

import logging

import flet as ft

from ui_flet.state import AppState


_LOG = logging.getLogger(__name__)


def show_snackbar(state: AppState, message: str) -> None:
    try:
        snack = ft.SnackBar(content=ft.Text(message))
        opener = getattr(state.page, "open", None)
        if opener is not None:
            opener(snack)
        else:  # pragma: no cover — legacy path
            legacy = getattr(state.page, "show_snack_bar", None)
            if legacy is not None:
                legacy(snack)
        state.page.update()
    except Exception:
        _LOG.exception("snackbar failed message=%s", message)
