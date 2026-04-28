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

import logging
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

import flet as ft

from app.platform import is_macos
from application.pdf_export import generate_collection_pdf
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.user_profile import validate_exam_date, validate_reminder_time
from infrastructure.ollama.runtime import OllamaBootstrapStatus
from ui_flet.components.ollama_status_badge import OllamaStatusBadge
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


_FONT_PRESET_OPTIONS: list[tuple[str, str]] = [
    # (preset_key, human_label). Keys must round-trip through settings.json.
    ("compact", "Маленький"),
    ("georgia", "Средний"),
    ("large", "Большой"),
]

_RECOMMENDED_OLLAMA_MODELS: list[tuple[str, str, bool]] = [
    # (model_id, description, is_recommended)
    ("qwen3:0.6b", "быстро, для слабого железа", False),
    ("qwen3:4b", "баланс скорости и качества", False),
    ("qwen3:8b", "качество рецензии", True),
]

_OLLAMA_DOWNLOAD_URL_MAC = "https://docs.ollama.com/macos"


@dataclass(slots=True)
class OllamaSetupDescriptor:
    title: str
    body: str
    action_label: str = ""
    action_kind: str = ""
    action_icon: str = ft.Icons.INFO_OUTLINE
    meta: str = ""


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
    style_section = _build_style_section(state, p)
    prep_section = _build_preparation_section(state, p)
    window_section = _build_window_section(state, p)
    font_section = _build_font_section(state, p)
    pdf_section = _build_pdf_export_section(state, p)
    gemini_section = _build_gemini_section(state, p)
    ollama_section = _build_ollama_section(state, p, badge, badge_control)
    reset_section = _build_reset_section(state, p)
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
                style_section,
                prep_section,
                window_section,
                font_section,
                pdf_section,
                gemini_section,
                ollama_section,
                reset_section,
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
# Section: Style family (warm vs deco)
# ============================================================================

def _build_style_section(state: AppState, p: dict[str, str]) -> ft.Control:
    from ui_flet.theme.tokens import get_active_family, set_active_family

    def _handle_change(event: ft.ControlEvent) -> None:
        selected = event.control.selected or set()
        new_family = next(iter(selected)) if selected else get_active_family()
        if new_family not in ("warm", "deco"):
            return
        if new_family == get_active_family():
            return
        set_active_family(new_family)
        _save_settings_patch(state, theme_family=new_family)
        # Тригерим тот же путь, что переключение light/dark — apply_theme
        # перечитает палитру/типографику, state.refresh() переотрисует view.
        for cb in list(state.theme_listeners):
            try:
                cb()
            except Exception:
                pass
        state.page.update()

    current = get_active_family()
    segmented = ft.SegmentedButton(
        segments=[
            ft.Segment(value="warm", label=ft.Text(TEXT["settings.style.warm"])),
            ft.Segment(value="deco", label=ft.Text(TEXT["settings.style.deco"])),
        ],
        selected={current},
        allow_multiple_selection=False,
        allow_empty_selection=False,
        on_change=_handle_change,
    )
    hint = ft.Text(
        TEXT["settings.style.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )
    return _section_card(
        p,
        title=TEXT["settings.style"],
        children=[segmented, hint],
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
# Section: Preparation (exam date + soft reminders)
# ============================================================================

def _build_preparation_section(state: AppState, p: dict[str, str]) -> ft.Control:
    """Дата экзамена + мягкие напоминания (стиль Duolingo, но не агрессивно)."""
    profile = state.user_profile
    current_date = (profile.exam_date if profile and profile.exam_date else "") or ""
    current_enabled = bool(profile.reminder_enabled) if profile else False
    current_time = (profile.reminder_time if profile else "10:00") or "10:00"

    date_field = ft.TextField(
        label=TEXT["settings.prep.exam_date"],
        hint_text="ГГГГ-ММ-ДД",
        value=current_date,
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        dense=True,
        width=180,
    )
    date_status = ft.Text(
        "",
        style=text_style("caption", color=p["text_muted"]),
    )

    def _on_date_save(_e: ft.ControlEvent) -> None:
        raw = (date_field.value or "").strip()
        if not raw:
            _save_profile_patch(state, exam_date=None)
            date_status.value = TEXT["settings.prep.exam_date.cleared"]
        else:
            ok, message = validate_exam_date(raw)
            if not ok:
                date_status.value = message or TEXT["settings.prep.exam_date.invalid"]
                date_status.color = p["danger"]
                date_status.update()
                return
            _save_profile_patch(state, exam_date=raw)
            date_status.value = TEXT["settings.prep.exam_date.saved"]
        date_status.color = p["text_muted"]
        date_status.update()

    date_save_btn = ft.OutlinedButton(
        text=TEXT["settings.prep.save"],
        icon=ft.Icons.CHECK,
        on_click=_on_date_save,
    )

    reminder_switch = ft.Switch(
        label=TEXT["settings.prep.reminder_enable"],
        value=current_enabled,
    )
    reminder_time_field = ft.TextField(
        label=TEXT["settings.prep.reminder_time"],
        hint_text="ЧЧ:ММ",
        value=current_time,
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        dense=True,
        width=120,
        disabled=not current_enabled,
    )
    reminder_status = ft.Text(
        "",
        style=text_style("caption", color=p["text_muted"]),
    )

    def _on_reminder_change(_e: ft.ControlEvent) -> None:
        enabled = bool(reminder_switch.value)
        reminder_time_field.disabled = not enabled
        reminder_time_field.update()

    reminder_switch.on_change = _on_reminder_change

    def _on_reminder_save(_e: ft.ControlEvent) -> None:
        enabled = bool(reminder_switch.value)
        time_raw = (reminder_time_field.value or "10:00").strip() or "10:00"
        ok, message = validate_reminder_time(time_raw)
        if not ok:
            reminder_status.value = message or TEXT["settings.prep.reminder_time.invalid"]
            reminder_status.color = p["danger"]
            reminder_status.update()
            return
        _save_profile_patch(
            state,
            reminder_enabled=enabled,
            reminder_time=time_raw,
        )
        reminder_status.value = (
            TEXT["settings.prep.reminder.saved.on"]
            if enabled
            else TEXT["settings.prep.reminder.saved.off"]
        )
        reminder_status.color = p["text_muted"]
        reminder_status.update()

    reminder_save_btn = ft.OutlinedButton(
        text=TEXT["settings.prep.save"],
        icon=ft.Icons.CHECK,
        on_click=_on_reminder_save,
    )

    hint = ft.Text(
        TEXT["settings.prep.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )

    return _section_card(
        p,
        title=TEXT["settings.prep.title"],
        children=[
            ft.Row(
                [date_field, date_save_btn],
                spacing=SPACE["sm"],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            date_status,
            ft.Container(height=SPACE["xs"]),
            reminder_switch,
            ft.Row(
                [reminder_time_field, reminder_save_btn],
                spacing=SPACE["sm"],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            reminder_status,
            hint,
        ],
    )


# ============================================================================
# Section: PDF export
# ============================================================================

def _safe_filename(text: str, fallback: str = "export") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned[:80].strip()
    return cleaned or fallback


def _load_sections_map_for_pdf(state: AppState) -> dict[str, dict[str, str]]:
    """section_id → {title, lecturer}, читая напрямую из БД."""
    try:
        exam_id = state.active_exam_id
        if exam_id:
            rows = state.facade.connection.execute(
                """
                SELECT section_id, title, description
                FROM sections
                WHERE exam_id = ?
                ORDER BY order_index, section_id
                """,
                (exam_id,),
            ).fetchall()
        else:
            rows = state.facade.connection.execute(
                """
                SELECT section_id, title, description
                FROM sections
                ORDER BY order_index, section_id
                """
            ).fetchall()
    except Exception:
        return {}
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        desc = r["description"] or ""
        lecturer = ""
        for part in re.split(r"[•|;]", desc):
            part = part.strip()
            if part.lower().startswith(("преподаватель", "лектор")):
                lecturer = part.split(":", 1)[-1].strip()
                break
        out[r["section_id"]] = {"title": r["title"] or "", "lecturer": lecturer}
    return out


def _build_pdf_export_section(state: AppState, p: dict[str, str]) -> ft.Control:
    def _on_save(e: ft.FilePickerResultEvent) -> None:
        if not e.path:
            return
        out = Path(e.path)
        if out.suffix.lower() != ".pdf":
            out = out.with_suffix(".pdf")
        try:
            tickets = state.facade.load_ticket_maps(exam_id=state.active_exam_id)
            secs = _load_sections_map_for_pdf(state)
            generate_collection_pdf(tickets, out, sections_map=secs)
            _toast_settings(state, TEXT["pdf.saved"].format(path=str(out)))
        except Exception:
            _LOG.exception("Failed to export collection PDF")
            _toast_settings(state, TEXT["pdf.failed"], error=True)

    file_picker = ft.FilePicker(on_result=_on_save)
    state.page.overlay.append(file_picker)

    default_name = "Тезис — Карманный конспект.pdf"

    def _open_save_dialog(_e: ft.ControlEvent) -> None:
        _toast_settings(state, TEXT["pdf.generating"])
        file_picker.save_file(
            dialog_title=TEXT["pdf.dialog_title.collection"],
            file_name=default_name,
            allowed_extensions=["pdf"],
            initial_directory=str(Path.home() / "Downloads"),
        )

    button = ft.FilledButton(
        text=TEXT["pdf.action.collection"],
        icon=ft.Icons.PICTURE_AS_PDF,
        on_click=_open_save_dialog,
    )
    hint = ft.Text(
        TEXT["pdf.section.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )
    return _section_card(
        p,
        title=TEXT["pdf.section.title"],
        children=[button, hint],
    )


def _toast_settings(state: AppState, message: str, *, error: bool = False) -> None:
    p = palette(state.is_dark)
    state.page.snack_bar = ft.SnackBar(
        ft.Text(message, color=p["text_primary"]),
        bgcolor=p["danger"] if error else p["bg_elevated"],
        duration=4000,
    )
    state.page.snack_bar.open = True
    try:
        state.page.update()
    except Exception:
        pass


# ============================================================================
# Section: Gemini (Google AI Studio) — для «Спросить у эталона»
# ============================================================================

_GEMINI_MODEL_OPTIONS: list[tuple[str, str]] = [
    ("gemini-2.5-flash", "gemini-2.5-flash · 250 RPD бесплатно, лучшая RU-цена/качество"),
    ("gemini-2.5-pro",   "gemini-2.5-pro · 100 RPD, выше глубина рассуждений"),
]


def _looks_like_gemini_key(text: str) -> bool:
    candidate = (text or "").strip()
    return bool(candidate) and " " not in candidate and (candidate.startswith("AIza") or len(candidate) >= 32)


def _candidate_gemini_key_from_env() -> str:
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        candidate = (os.environ.get(env_name, "") or "").strip()
        if _looks_like_gemini_key(candidate):
            return candidate
    return ""


def _build_gemini_section(state: AppState, p: dict[str, str]) -> ft.Control:
    """API-ключ Google AI Studio с упрощённым сценарием настройки."""
    settings = _current_settings(state)
    stored_key = (getattr(settings, "gemini_api_key", "") or "").strip()
    env_key = _candidate_gemini_key_from_env()
    current_key = stored_key or env_key
    env_auto_filled = not stored_key and bool(env_key)
    current_model = getattr(settings, "gemini_model", "gemini-2.5-flash") or "gemini-2.5-flash"

    key_field = ft.TextField(
        label=TEXT["settings.gemini.api_key"],
        hint_text=TEXT["settings.gemini.api_key.hint"],
        value=current_key,
        password=True,
        can_reveal_password=True,
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        dense=True,
    )
    model_dropdown = ft.Dropdown(
        label=TEXT["settings.gemini.model"],
        value=current_model,
        options=[ft.dropdown.Option(key=k, text=desc) for k, desc in _GEMINI_MODEL_OPTIONS],
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        dense=True,
    )
    # Initial status: guide the user to the next click. If we auto-filled the
    # field from env, say so — otherwise leave blank so the three-step
    # instruction above takes the spotlight.
    initial_status = TEXT["settings.gemini.env_detected"] if env_auto_filled else ""
    initial_color = p["success"] if env_auto_filled else p["text_muted"]
    status = ft.Text(initial_status, style=text_style("caption", color=initial_color))

    def _set_status(message: str, *, color: str | None = None) -> None:
        status.value = message
        status.color = color or p["text_muted"]
        status.update()

    def _resolve_gemini_key() -> str:
        current_value = (key_field.value or "").strip()
        if _looks_like_gemini_key(current_value):
            return current_value

        env_key = _candidate_gemini_key_from_env()
        if env_key:
            key_field.value = env_key
            key_field.update()
            return env_key

        try:
            clipboard_value = (state.page.get_clipboard() or "").strip()
        except Exception:
            clipboard_value = ""
        if _looks_like_gemini_key(clipboard_value):
            key_field.value = clipboard_value
            key_field.update()
            return clipboard_value
        return ""

    def _on_open_portal(_e: ft.ControlEvent) -> None:
        try:
            state.page.launch_url("https://aistudio.google.com/app/apikey")
        except Exception:
            _LOG.exception("Failed to launch Google AI Studio URL")

    def _on_autofill(_e: ft.ControlEvent) -> None:
        key = _resolve_gemini_key()
        if not key:
            _set_status(TEXT["settings.gemini.autofill.empty"], color=p["danger"])
            return
        _set_status(TEXT["settings.gemini.autofill.done"])

    def _on_save(_e: ft.ControlEvent) -> None:
        new_key = _resolve_gemini_key()
        new_model = (model_dropdown.value or "gemini-2.5-flash").strip()
        if not new_key:
            _set_status(TEXT["settings.gemini.probe.no_key"], color=p["danger"])
            return
        _save_settings_patch(state, gemini_api_key=new_key, gemini_model=new_model)
        _set_status(TEXT["settings.gemini.saved"])

    def _on_probe(_e: ft.ControlEvent) -> None:
        from infrastructure.gemini import GeminiService

        new_key = _resolve_gemini_key()
        new_model = (model_dropdown.value or "gemini-2.5-flash").strip()
        if not new_key:
            _set_status(TEXT["settings.gemini.probe.no_key"], color=p["danger"])
            return
        _save_settings_patch(state, gemini_api_key=new_key, gemini_model=new_model)
        _set_status(TEXT["settings.gemini.probe.loading"])
        svc = GeminiService(api_key=new_key, model=new_model)
        ok, err = svc.probe()
        if ok:
            _set_status(TEXT["settings.gemini.setup.ok"], color=p["success"])
        else:
            _set_status(TEXT["settings.gemini.probe.fail"].format(err=err), color=p["danger"])

    # CTA emphasis depends on the current state:
    # - no key anywhere: "Получить ключ" is the primary action
    # - key in clipboard/env but not saved: "Вставить и проверить" is primary
    # - key already working: "Сохранить и проверить" is primary
    if not current_key:
        open_btn = ft.FilledButton(
            text=TEXT["settings.gemini.open"],
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=_on_open_portal,
        )
        autofill_btn = ft.OutlinedButton(
            text=TEXT["settings.gemini.autofill"],
            icon=ft.Icons.CONTENT_PASTE_GO,
            on_click=_on_autofill,
        )
        probe_btn = ft.OutlinedButton(
            text=TEXT["settings.gemini.setup"],
            icon=ft.Icons.CABLE,
            on_click=_on_probe,
        )
    else:
        open_btn = ft.OutlinedButton(
            text=TEXT["settings.gemini.open"],
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=_on_open_portal,
        )
        autofill_btn = ft.OutlinedButton(
            text=TEXT["settings.gemini.autofill"],
            icon=ft.Icons.CONTENT_PASTE_GO,
            on_click=_on_autofill,
        )
        probe_btn = ft.FilledButton(
            text=TEXT["settings.gemini.setup"],
            icon=ft.Icons.CABLE,
            on_click=_on_probe,
        )
    save_btn = ft.TextButton(
        text=TEXT["settings.gemini.save"],
        icon=ft.Icons.SAVE_OUTLINED,
        on_click=_on_save,
    )

    steps_line = ft.Text(
        TEXT["settings.gemini.steps"],
        style=text_style("caption", color=p["text_secondary"]),
    )
    hint = ft.Text(
        TEXT["settings.gemini.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )

    return _section_card(
        p,
        title=TEXT["settings.gemini.title"],
        children=[
            steps_line,
            key_field,
            model_dropdown,
            ft.Row([open_btn, autofill_btn, probe_btn], spacing=SPACE["sm"], wrap=True),
            ft.Row([save_btn], spacing=SPACE["sm"]),
            status,
            hint,
        ],
    )


def _build_ollama_section(
    state: AppState,
    p: dict[str, str],
    badge: OllamaStatusBadge,
    badge_control: ft.Control,
) -> ft.Control:
    settings = _current_settings(state)
    initial_status = _safe_inspect_ollama_bootstrap(state, settings.model)
    enable_switch = ft.Switch(
        label=TEXT["settings.ollama.enabled"],
        value=_is_ollama_enabled(settings),
        on_change=lambda e: _handle_ollama_toggle(state, e.control.value, badge),
    )
    model_dropdown = ft.Dropdown(
        label=TEXT["settings.ollama.model"],
        value=settings.model,
        options=_build_ollama_dropdown_options(
            initial_status.available_models if initial_status is not None else [],
            settings.model,
        ),
        width=380,
    )
    setup_title = ft.Text(
        TEXT["settings.ollama.setup.loading.title"],
        style=text_style("h3", color=p["text_primary"]),
    )
    setup_body = ft.Text(
        TEXT["settings.ollama.setup.loading.body"],
        style=text_style("body", color=p["text_secondary"]),
    )
    setup_meta = ft.Text(
        "",
        visible=False,
        style=text_style("caption", color=p["text_muted"]),
    )
    progress_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    primary_button = ft.FilledButton(visible=False)
    status_holder: dict[str, OllamaBootstrapStatus | None] = {"value": None}
    action_holder: dict[str, str] = {"value": ""}

    def _safe_page_update() -> None:
        try:
            state.page.update()
        except Exception:
            pass

    def _apply_setup_status(status: OllamaBootstrapStatus | None, *, busy: bool = False) -> None:
        status_holder["value"] = status
        descriptor = _describe_ollama_setup(status, model_dropdown.value or settings.model)
        model_dropdown.options = _build_ollama_dropdown_options(
            status.available_models if status is not None else [],
            model_dropdown.value or settings.model,
        )
        action_holder["value"] = descriptor.action_kind
        setup_title.value = descriptor.title
        setup_body.value = descriptor.body
        setup_meta.value = descriptor.meta
        setup_meta.visible = bool(descriptor.meta)
        primary_button.text = descriptor.action_label
        primary_button.icon = descriptor.action_icon
        primary_button.visible = bool(descriptor.action_kind)
        primary_button.disabled = busy or not bool(descriptor.action_kind)
        progress_ring.visible = busy
        _safe_page_update()

    def _run_setup_action(action_kind: str, *, announce: bool = False) -> None:
        import threading

        if action_kind == "download_mac":
            try:
                state.page.launch_url(_OLLAMA_DOWNLOAD_URL_MAC)
                _show_snackbar(state, TEXT["settings.ollama.download_opened"])
            except Exception:
                _LOG.exception("Failed to launch Ollama macOS URL")
                _show_snackbar(state, TEXT["settings.ollama.download_failed"])
            return

        if not action_kind:
            return

        preferred_model = (model_dropdown.value or settings.model or "").strip()
        _apply_setup_status(status_holder["value"], busy=True)

        def _worker() -> None:
            try:
                if action_kind == "pull_model":
                    status = state.facade.pull_ollama_model(preferred_model)
                elif action_kind == "ensure_ready":
                    status = state.facade.ensure_ollama_ready(preferred_model)
                else:
                    status = state.facade.inspect_ollama_bootstrap(preferred_model)
            except Exception:  # noqa: BLE001
                _LOG.exception("Ollama setup action failed action=%s", action_kind)
                status = OllamaBootstrapStatus(
                    state="error",
                    preferred_model=preferred_model,
                    error=TEXT["settings.ollama.setup.error.body"],
                )

            badge.set_model(preferred_model)
            badge.probe_now()
            state.probe_ollama()
            _apply_setup_status(status, busy=False)
            if announce:
                _show_snackbar(state, _ollama_probe_feedback(status, preferred_model))

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_setup_status() -> None:
        _run_setup_action("inspect", announce=False)

    primary_button.on_click = lambda _e: _run_setup_action(action_holder["value"], announce=action_holder["value"] != "inspect")
    model_dropdown.on_change = lambda e: _handle_model_change(
        state,
        e.control.value,
        badge,
        refresh_callback=_refresh_setup_status,
    )

    test_button = ft.FilledTonalButton(
        TEXT["settings.ollama.test"],
        icon=ft.Icons.NETWORK_CHECK,
        on_click=lambda _e: _run_setup_action("ensure_ready", announce=True),
    )
    setup_card = ft.Container(
        padding=SPACE["md"],
        bgcolor=p["bg_surface"],
        border_radius=RADIUS["md"],
        border=ft.border.all(1, p["border_soft"]),
        content=ft.Column(
            spacing=SPACE["sm"],
            controls=[
                setup_title,
                setup_body,
                setup_meta,
                ft.Row(
                    spacing=SPACE["sm"],
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[primary_button, progress_ring],
                ),
            ],
        ),
    )
    hint = ft.Text(
        TEXT["settings.ollama.install_hint"],
        style=text_style("caption", color=p["text_muted"]),
    )
    _apply_setup_status(initial_status, busy=False)
    if initial_status is None:
        _refresh_setup_status()

    return _section_card(
        p,
        title=TEXT["settings.ollama.title"],
        children=[
            enable_switch,
            model_dropdown,
            setup_card,
            ft.Row(
                spacing=SPACE["md"],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    test_button,
                    ft.Text(TEXT["settings.ollama.status"], color=p["text_secondary"]),
                    badge_control,
                ],
            ),
            hint,
        ],
    )


def _ollama_bootstrap_meta(status: OllamaBootstrapStatus) -> str:
    parts: list[str] = []
    if status.resolved_model:
        parts.append(TEXT["settings.ollama.meta.model"].format(model=status.resolved_model))
    elif status.preferred_model and status.state == "model_missing":
        parts.append(TEXT["settings.ollama.meta.target"].format(model=status.preferred_model))
    if status.models_path:
        parts.append(TEXT["settings.ollama.meta.path"].format(path=status.models_path))
    return " · ".join(parts)


def _describe_ollama_setup(
    status: OllamaBootstrapStatus | None,
    model_name: str,
    *,
    macos: bool | None = None,
) -> OllamaSetupDescriptor:
    is_macos_platform = is_macos() if macos is None else macos
    target_model = (model_name or getattr(status, "preferred_model", "") or "qwen3:8b").strip()
    if status is None:
        return OllamaSetupDescriptor(
            title=TEXT["settings.ollama.setup.loading.title"],
            body=TEXT["settings.ollama.setup.loading.body"],
        )
    meta = _ollama_bootstrap_meta(status)
    if status.state == "not_installed":
        return OllamaSetupDescriptor(
            title=TEXT["settings.ollama.setup.not_installed.title"],
            body=TEXT["settings.ollama.setup.not_installed.body"],
            action_label=TEXT["settings.ollama.download_mac"] if is_macos_platform else TEXT["settings.ollama.recheck"],
            action_kind="download_mac" if is_macos_platform else "inspect",
            action_icon=ft.Icons.DOWNLOAD,
            meta=meta,
        )
    if status.state == "installed_not_running":
        return OllamaSetupDescriptor(
            title=TEXT["settings.ollama.setup.installed_not_running.title"],
            body=TEXT["settings.ollama.setup.installed_not_running.body"],
            action_label=TEXT["settings.ollama.start"],
            action_kind="ensure_ready",
            action_icon=ft.Icons.PLAY_ARROW,
            meta=meta,
        )
    if status.state == "model_missing":
        return OllamaSetupDescriptor(
            title=TEXT["settings.ollama.setup.model_missing.title"],
            body=TEXT["settings.ollama.setup.model_missing.body"].format(model=target_model),
            action_label=TEXT["settings.ollama.pull_model"].format(model=target_model),
            action_kind="pull_model",
            action_icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
            meta=meta,
        )
    if status.state == "ready":
        body = TEXT["settings.ollama.setup.ready.body"]
        if status.resolved_model and status.preferred_model and status.resolved_model != status.preferred_model:
            body = TEXT["settings.ollama.setup.ready.fallback"].format(model=status.resolved_model)
        return OllamaSetupDescriptor(
            title=TEXT["settings.ollama.setup.ready.title"],
            body=body,
            action_label=TEXT["settings.ollama.recheck"],
            action_kind="inspect",
            action_icon=ft.Icons.REFRESH,
            meta=meta,
        )
    return OllamaSetupDescriptor(
        title=TEXT["settings.ollama.setup.error.title"],
        body=status.error or TEXT["settings.ollama.setup.error.body"],
        action_label=TEXT["settings.ollama.recheck"],
        action_kind="inspect",
        action_icon=ft.Icons.REFRESH,
        meta=meta,
    )


def _ollama_probe_feedback(status: OllamaBootstrapStatus, preferred_model: str) -> str:
    if status.state == "ready":
        return TEXT["settings.ollama.probe.ready"].format(model=status.resolved_model or preferred_model or "qwen3")
    if status.state == "model_missing":
        return TEXT["settings.ollama.probe.model_missing"].format(model=preferred_model or status.preferred_model or "qwen3:8b")
    if status.state == "installed_not_running":
        return TEXT["settings.ollama.probe.not_running"]
    if status.state == "not_installed":
        return TEXT["settings.ollama.probe.not_installed"]
    return status.error or TEXT["settings.ollama.probe.error"]


def _safe_inspect_ollama_bootstrap(state: AppState, preferred_model: str) -> OllamaBootstrapStatus | None:
    try:
        return state.facade.inspect_ollama_bootstrap(preferred_model)
    except Exception:
        _LOG.exception("Ollama bootstrap inspection failed preferred_model=%s", preferred_model)
        return None


def _build_ollama_dropdown_options(
    available_models: list[str],
    selected_model: str,
) -> list[ft.dropdown.Option]:
    option_specs = _collect_ollama_model_options(available_models, selected_model)
    return [
        ft.dropdown.Option(
            key=model_id,
            text=f"{label}{' ★ Рекомендовано' if recommended else ''}",
        )
        for model_id, label, recommended in option_specs
    ]


def _collect_ollama_model_options(
    available_models: list[str],
    selected_model: str,
) -> list[tuple[str, str, bool]]:
    selected = (selected_model or "").strip()
    options: list[tuple[str, str, bool]] = []
    seen: set[str] = set()

    def _append(model_id: str, label: str, recommended: bool) -> None:
        normalized = model_id.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        options.append((normalized, label, recommended))

    for model_name in available_models:
        normalized = str(model_name or "").strip()
        if not normalized:
            continue
        recommended_meta = next(
            (item for item in _RECOMMENDED_OLLAMA_MODELS if item[0] == normalized),
            None,
        )
        if recommended_meta is not None:
            _, description, recommended = recommended_meta
            _append(normalized, f"{normalized} · установлена локально · {description}", recommended)
        else:
            _append(normalized, f"{normalized} · установлена локально", False)

    for model_id, description, recommended in _RECOMMENDED_OLLAMA_MODELS:
        _append(model_id, f"{model_id} · {description}", recommended)

    if selected and selected not in seen:
        _append(selected, f"{selected} · сохранена в настройках", False)

    return options


def _is_ollama_enabled(settings: OllamaSettings) -> bool:
    return bool(getattr(settings, "ollama_enabled", True))


def _handle_ollama_toggle(
    state: AppState,
    value: bool,
    badge: OllamaStatusBadge,
) -> None:
    _save_settings_patch(
        state,
        ollama_enabled=bool(value),
    )
    badge.probe_now()
    state.probe_ollama()


def _handle_model_change(
    state: AppState,
    new_model: str,
    badge: OllamaStatusBadge,
    *,
    refresh_callback=None,
) -> None:
    if not new_model:
        return
    _save_settings_patch(state, model=new_model)
    badge.set_model(new_model)
    badge.probe_now()
    state.probe_ollama()
    if refresh_callback is not None:
        try:
            refresh_callback()
        except Exception:
            pass

def _build_reset_section(state: AppState, p: dict[str, str]) -> ft.Control:
    # The dialog instance is kept on this closure so close/confirm handlers
    # reach the exact same control that was opened. Flet 0.27 dropped the
    # old `page.dialog = ...; dialog.open = True` pattern — use page.open/
    # page.close now.
    dialog_holder: dict[str, ft.AlertDialog | None] = {"dlg": None}

    def _close_dialog(_e: ft.ControlEvent | None = None) -> None:
        dlg = dialog_holder["dlg"]
        if dlg is None:
            return
        try:
            state.page.close(dlg)
        except Exception:
            _LOG.exception("Failed to close reset dialog")
        finally:
            dialog_holder["dlg"] = None

    def _confirm_reset(_e: ft.ControlEvent) -> None:
        _close_dialog()
        try:
            state.reset_to_cold_start()
            _show_snackbar(state, TEXT["settings.reset.done"])
        except Exception as exc:
            _LOG.exception("Cold reset failed")
            # Put the real error message into the toast — a blanket
            # "failed" line hides file-lock or permission issues from
            # the user and makes the button look broken.
            detail = f"{type(exc).__name__}: {exc}"
            _toast_settings(
                state,
                f"{TEXT['settings.reset.failed']} — {detail}",
                error=True,
            )

    def _open_dialog(_e: ft.ControlEvent) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(TEXT["settings.reset.confirm.title"]),
            content=ft.Text(TEXT["settings.reset.confirm.body"]),
            actions=[
                ft.TextButton(TEXT["action.close"], on_click=_close_dialog),
                ft.FilledButton(
                    text=TEXT["action.reset"],
                    icon=ft.Icons.DELETE_FOREVER,
                    on_click=_confirm_reset,
                    style=ft.ButtonStyle(
                        bgcolor=p["danger"],
                        color=p["bg_surface"],
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_holder["dlg"] = dialog
        state.page.open(dialog)

    button = ft.FilledTonalButton(
        text=TEXT["settings.reset.action"],
        icon=ft.Icons.DELETE_FOREVER,
        on_click=_open_dialog,
    )
    hint = ft.Text(
        TEXT["settings.reset.hint"],
        style=text_style("caption", color=p["text_muted"]),
    )
    return _section_card(
        p,
        title=TEXT["settings.reset.title"],
        children=[button, hint],
    )


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
        tickets = state.facade.load_ticket_maps(exam_id=state.active_exam_id)
        tickets_count = len(tickets)
    except Exception:
        tickets_count = 0

    return version_label, seed_label, tickets_count


def _resolve_version_label(state: AppState) -> str:
    try:
        from app.build_info import get_runtime_build_info

        info = get_runtime_build_info()
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


def _save_profile_patch(state: AppState, **changes) -> None:
    """Apply a diff to the current UserProfile and persist via ProfileStore."""
    from dataclasses import replace as _replace
    from pathlib import Path as _Path

    from application.user_profile import ProfileStore

    profile = state.user_profile
    if profile is None:
        return
    try:
        updated = _replace(profile, **changes)
        workspace_root = _Path(getattr(state.facade, "workspace_root", _Path(".")))
        store = ProfileStore(workspace_root / "app_data" / "profile.json")
        store.save(updated)
        state.user_profile = updated
    except Exception:
        _LOG.exception("Profile save failed")


def _show_snackbar(state: AppState, message: str) -> None:
    # Тонкая обёртка, оставлена как имя-фасад для локальных callsite'ов.
    from ui_flet.components.feedback import show_snackbar
    try:
        show_snackbar(state, message)
        return
    except Exception:
        pass
