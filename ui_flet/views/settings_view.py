"""SettingsView — application settings with live theme/font/Ollama controls.

Four sections rendered as a scrollable Column:

- Тема: SegmentedButton (light/dark). Toggles ``state.is_dark``, notifies
  ``state.theme_listeners`` (which invokes ``apply_theme`` in main.py), and
  calls ``page.update()``. The preference is also persisted to settings
  (``theme_name``) so the app starts in the chosen mode next time.
- Шрифт: Dropdown for ``font_preset``. Flet cannot live-reload fonts
  without a page rebuild, so we persist the choice and surface an ephemeral
  snackbar instead of trying to hot-swap typography.
- Ollama: switch to enable/disable LLM review, model dropdown, probe
  button + status badge, and an install hint.
- О приложении: app name/version from ``app/build_info.py`` plus the seed
  DB path and a live ticket count.

The view keeps the Facade as the only state-mutating surface: every change
funnels through ``facade.save_settings(...)`` so the Qt app and Flet app
share the same ``settings.json``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import flet as ft

from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from ui_flet.components.ollama_status_badge import OllamaStatusBadge
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style


_FONT_PRESET_OPTIONS: list[tuple[str, str]] = [
    # (preset_key, human_label). Keys must round-trip through settings.json.
    ("compact", "Маленький"),
    ("georgia", "Средний"),
    ("large", "Большой"),
]

_OLLAMA_MODEL_OPTIONS: list[tuple[str, str, bool]] = [
    # (model_id, description, is_recommended)
    ("qwen3:0.6b", "qwen3:0.6b · быстро, слабое железо", False),
    ("qwen3:4b", "qwen3:4b · баланс скорости и качества", False),
    ("qwen3:8b", "qwen3:8b · рекомендуется", True),
]


def build_settings_view(state: AppState) -> ft.Control:
    p = palette(state.is_dark)

    # ---- badge (shared across sections) ----
    badge = OllamaStatusBadge(state, poll_interval_sec=15.0)
    badge_control = badge.build()

    # Mirror state-level probe completions into the badge so the two agree on
    # connectivity without waiting for the badge's own 15s poll interval.
    state.on_ollama_change(lambda _online: badge.probe_now())

    # ---- section builders ----
    theme_section = _build_theme_section(state, p)
    window_section = _build_window_section(state, p)
    font_section = _build_font_section(state, p)
    ollama_section = _build_ollama_section(state, p, badge, badge_control)
    about_section = _build_about_section(state, p)

    header = ft.Text(
        TEXT["settings.title"],
        style=text_style("h1", color=p["text_primary"]),
    )
    back_link = ft.TextButton(
        TEXT["nav.tickets"],
        icon=ft.Icons.ARROW_BACK,
        on_click=lambda _e: state.go("/tickets"),
    )

    return ft.Container(
        padding=SPACE["xl"],
        bgcolor=p["bg_base"],
        expand=True,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=SPACE["lg"],
            controls=[
                ft.Row([back_link]),
                header,
                theme_section,
                window_section,
                font_section,
                ollama_section,
                about_section,
            ],
        ),
    )


# ============================================================================
# Section: Theme
# ============================================================================

def _build_theme_section(state: AppState, p: dict[str, str]) -> ft.Control:
    def _handle_change(event: ft.ControlEvent) -> None:
        # ft.SegmentedButton.on_change emits a set-like of selected values.
        selected = event.control.selected or set()
        value = next(iter(selected)) if selected else ("dark" if state.is_dark else "light")
        new_is_dark = value == "dark"
        if new_is_dark == state.is_dark:
            return
        state.is_dark = new_is_dark
        _save_settings_patch(state, theme_name="dark" if new_is_dark else "light")
        for cb in list(state.theme_listeners):
            try:
                cb()
            except Exception:
                pass
        state.page.update()

    selected_value = "dark" if state.is_dark else "light"
    segmented = ft.SegmentedButton(
        segments=[
            ft.Segment(value="light", label=ft.Text(TEXT["settings.theme.light"])),
            ft.Segment(value="dark", label=ft.Text(TEXT["settings.theme.dark"])),
        ],
        selected={selected_value},
        allow_multiple_selection=False,
        allow_empty_selection=False,
        on_change=_handle_change,
    )
    return _section_card(
        p,
        title=TEXT["settings.theme"],
        children=[segmented],
    )


# ============================================================================
# Section: Window
# ============================================================================

def _build_window_section(state: AppState, p: dict[str, str]) -> ft.Control:
    """Fullscreen ↔ windowed toggle. Mirrors the state that ``main.py`` reads
    at launch, and applies the change live to the current page so the user
    sees the result without restarting.
    """
    settings = _current_settings(state)
    current_mode = (settings.window_mode or "fullscreen").lower()
    if current_mode not in ("fullscreen", "windowed"):
        current_mode = "fullscreen"

    def _handle_change(event: ft.ControlEvent) -> None:
        selected = event.control.selected or set()
        new_mode = next(iter(selected)) if selected else current_mode
        if new_mode not in ("fullscreen", "windowed"):
            return

        # Persist first so a crash after ``page.update`` still survives a
        # restart.
        _save_settings_patch(state, window_mode=new_mode)

        live_settings = _current_settings(state)
        width = int(getattr(live_settings, "window_width", 1440) or 1440)
        height = int(getattr(live_settings, "window_height", 900) or 900)

        if new_mode == "fullscreen":
            state.page.window.full_screen = True
        else:
            state.page.window.full_screen = False
            state.page.window.width = float(width)
            state.page.window.height = float(height)
        try:
            state.page.update()
        except Exception:
            pass

    segmented = ft.SegmentedButton(
        segments=[
            ft.Segment(value="fullscreen", label=ft.Text(TEXT["settings.window.fullscreen"])),
            ft.Segment(value="windowed", label=ft.Text(TEXT["settings.window.windowed"])),
        ],
        selected={current_mode},
        allow_multiple_selection=False,
        allow_empty_selection=False,
        on_change=_handle_change,
    )
    hint = ft.Text(
        TEXT["settings.window.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )
    return _section_card(
        p,
        title=TEXT["settings.window"],
        children=[segmented, hint],
    )


# ============================================================================
# Section: Font
# ============================================================================

def _build_font_section(state: AppState, p: dict[str, str]) -> ft.Control:
    current_preset = _current_settings(state).font_preset or DEFAULT_OLLAMA_SETTINGS.font_preset

    def _handle_change(event: ft.ControlEvent) -> None:
        new_preset = event.control.value
        if not new_preset or new_preset == _current_settings(state).font_preset:
            return
        _save_settings_patch(state, font_preset=new_preset)
        _show_snackbar(state, "Применится после перезапуска")

    dropdown = ft.Dropdown(
        value=current_preset,
        options=[
            ft.dropdown.Option(key=key, text=label)
            for key, label in _FONT_PRESET_OPTIONS
        ],
        on_change=_handle_change,
        width=320,
    )
    return _section_card(
        p,
        title=TEXT["settings.font_size"],
        children=[dropdown],
    )


# ============================================================================
# Section: Ollama
# ============================================================================

def _build_ollama_section(
    state: AppState,
    p: dict[str, str],
    badge: OllamaStatusBadge,
    badge_control: ft.Control,
) -> ft.Control:
    settings = _current_settings(state)

    # --- Enable switch ---
    # `OllamaSettings` doesn't expose a dedicated `ollama_enabled` flag; the
    # closest semantic match is `rule_based_fallback` (inverse) and the model
    # selection. We treat `rewrite_questions and examiner_followups` as the
    # de-facto "Ollama features enabled" composite so the toggle is honest.
    enable_switch = ft.Switch(
        label=TEXT["settings.ollama.enabled"],
        value=_is_ollama_enabled(settings),
        on_change=lambda e: _handle_ollama_toggle(state, e.control.value),
    )

    # --- Model dropdown with recommendation chip ---
    model_dropdown = ft.Dropdown(
        label=TEXT["settings.ollama.model"],
        value=settings.model,
        options=[
            ft.dropdown.Option(
                key=model_id,
                text=f"{label}{' ★ Рекомендовано' if recommended else ''}",
            )
            for model_id, label, recommended in _OLLAMA_MODEL_OPTIONS
        ],
        on_change=lambda e: _handle_model_change(state, e.control.value, badge),
        width=380,
    )

    # --- Test connection button + progress ring ---
    progress_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    test_button = ft.FilledTonalButton(
        TEXT["settings.ollama.test"],
        icon=ft.Icons.NETWORK_CHECK,
        on_click=lambda _e: _handle_test_connection(state, badge, progress_ring),
    )

    # --- Hint ---
    hint = ft.Text(
        TEXT["settings.ollama.install_hint"],
        style=text_style("caption", color=p["text_muted"]),
    )

    return _section_card(
        p,
        title=TEXT["settings.ollama.title"],
        children=[
            enable_switch,
            model_dropdown,
            ft.Row(
                spacing=SPACE["md"],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    test_button,
                    progress_ring,
                    ft.Text(TEXT["settings.ollama.status"], color=p["text_secondary"]),
                    badge_control,
                ],
            ),
            hint,
        ],
    )


def _is_ollama_enabled(settings: OllamaSettings) -> bool:
    # "Использовать Ollama для рецензий": exam-trainer treats Ollama as enabled
    # when at least one LLM-backed feature is on. We track this via
    # `rewrite_questions` (the canonical setting the Qt UI also toggles).
    return bool(settings.rewrite_questions or settings.examiner_followups)


def _handle_ollama_toggle(state: AppState, value: bool) -> None:
    _save_settings_patch(
        state,
        rewrite_questions=bool(value),
        examiner_followups=bool(value),
    )


def _handle_model_change(state: AppState, new_model: str, badge: OllamaStatusBadge) -> None:
    if not new_model:
        return
    _save_settings_patch(state, model=new_model)
    badge.set_model(new_model)
    badge.probe_now()


def _handle_test_connection(
    state: AppState,
    badge: OllamaStatusBadge,
    progress_ring: ft.ProgressRing,
) -> None:
    import threading

    progress_ring.visible = True
    try:
        progress_ring.update()
    except Exception:
        pass

    def _worker() -> None:
        ok = False
        error_text = ""
        try:
            service = state.facade.build_ollama_service(timeout_seconds=3.0)
            # Prefer the cheap tags probe — same path ``OllamaService.inspect``
            # uses first. Avoids kicking off a generation that could block
            # for tens of seconds on a cold model.
            response = service.client.get_tags()
            ok = bool(response.ok)
            if not ok:
                error_text = response.error or "Ollama не ответила"
        except Exception as exc:  # noqa: BLE001
            ok = False
            error_text = str(exc)

        progress_ring.visible = False
        try:
            progress_ring.update()
        except Exception:
            pass

        badge.probe_now()
        _show_snackbar(
            state,
            TEXT["settings.ollama.status.ok"] if ok else f"{TEXT['settings.ollama.status.offline']}: {error_text or '—'}",
        )

    threading.Thread(target=_worker, daemon=True).start()


# ============================================================================
# Section: About
# ============================================================================

def _build_about_section(state: AppState, p: dict[str, str]) -> ft.Control:
    version_label, seed_label, tickets_count = _collect_about_info(state)

    version_row = _about_row(p, TEXT["settings.version"], version_label)
    seed_row = _about_row(p, TEXT["settings.seed"], seed_label)
    tickets_row = _about_row(p, TEXT["tickets.ticket_number"], str(tickets_count))
    app_row = _about_row(p, TEXT["app_title"], TEXT["app_subtitle"])

    return _section_card(
        p,
        title=TEXT["settings.about"],
        children=[app_row, version_row, seed_row, tickets_row],
    )


def _collect_about_info(state: AppState) -> tuple[str, str, int]:
    version_label = _resolve_version_label(state)

    # Seed DB path — the Qt bootstrap puts it at workspace_root/exam_trainer.db.
    try:
        from infrastructure.db.connection import get_database_path

        workspace_root: Path = getattr(state.facade, "workspace_root", Path("."))
        seed_path = get_database_path(workspace_root)
        seed_label = str(seed_path)
    except Exception:
        seed_label = "—"

    # Ticket count — load_ticket_maps() is the canonical read path.
    try:
        tickets = state.facade.load_ticket_maps()
        tickets_count = len(tickets)
    except Exception:
        tickets_count = 0

    return version_label, seed_label, tickets_count


def _resolve_version_label(state: AppState) -> str:
    try:
        from app.build_info import get_runtime_build_info

        workspace_root: Path = getattr(state.facade, "workspace_root", None)
        info = get_runtime_build_info(workspace_root)
        return info.release_label
    except Exception:
        pass
    try:
        from app.meta import APP_VERSION

        return f"v{APP_VERSION}"
    except Exception:
        return "dev"


def _about_row(p: dict[str, str], label: str, value: str) -> ft.Control:
    return ft.Row(
        spacing=SPACE["md"],
        controls=[
            ft.Container(
                width=140,
                content=ft.Text(label, color=p["text_secondary"], size=13),
            ),
            ft.Text(value, color=p["text_primary"], size=13, selectable=True),
        ],
    )


# ============================================================================
# Helpers
# ============================================================================

def _section_card(
    p: dict[str, str],
    *,
    title: str,
    children: list[ft.Control],
) -> ft.Control:
    return ft.Container(
        padding=SPACE["lg"],
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["lg"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["md"],
            controls=[
                ft.Text(title, style=text_style("h3", color=p["text_primary"])),
                *children,
            ],
        ),
    )


def _current_settings(state: AppState) -> OllamaSettings:
    """Read the current OllamaSettings from the facade, with a safe fallback."""
    try:
        return state.facade.settings
    except Exception:
        return DEFAULT_OLLAMA_SETTINGS


def _save_settings_patch(state: AppState, **changes) -> None:
    """Apply a diff to the current settings and persist via the facade."""
    try:
        current = _current_settings(state)
        updated = replace(current, **changes)
        state.facade.save_settings(updated)
    except Exception:
        # Never let settings persistence crash the UI — log-less swallow is
        # acceptable here because the live controls already reflect intent.
        pass


def _show_snackbar(state: AppState, message: str) -> None:
    try:
        snack = ft.SnackBar(content=ft.Text(message))
        # Flet 0.27 prefers `page.open(snack)`; `show_snack_bar` is gone.
        opener = getattr(state.page, "open", None)
        if opener is not None:
            opener(snack)
        else:  # pragma: no cover — legacy path
            legacy = getattr(state.page, "show_snack_bar", None)
            if legacy is not None:
                legacy(snack)
        state.page.update()
    except Exception:
        pass
