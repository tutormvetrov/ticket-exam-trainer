"""Entry point: python -m ui_flet.main.

Wires AppFacade to an ft.app and runs the three-route UI.

Startup choreography
--------------------
1. ``_configure_page`` sets static page chrome (title, fonts, min size).
2. The persisted ``window_mode`` from ``OllamaSettings`` decides whether the
   window opens fullscreen or in a sized window (defaults to fullscreen, which
   is what spec 3.5a asks for).
3. ``state.probe_ollama()`` fires a background probe of ``127.0.0.1:11434``
   right after the theme is applied - workspaces treat ``ollama_online=None``
   as offline so there's no window in which the UI can accidentally spin up
   a 60s LLM call.
4. Key bindings: ``Escape`` leaves fullscreen (drops back to the saved
   windowed size). A small floating action button at top-right of the page
   lets the user toggle fullscreen without opening Settings.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

import flet as ft

# Reuse the same workspace/bootstrap logic as the Qt app so seed DB, settings,
# and migrations resolve identically.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.paths import get_workspace_root
from app.runtime_logging import setup_runtime_logging
from application.facade import AppFacade
from application.settings_store import SettingsStore
from application.user_profile import (
    COURSE_CATALOG,
    DEFAULT_EXAM_ID,
    ProfileStore,
    UserProfile,
)
from infrastructure.db import connect_initialized, get_database_path
from ui_flet.router import on_route_change
from ui_flet.state import AppState
from ui_flet.theme.fonts import font_map
from ui_flet.theme.theme import apply_theme

SEED_FILENAME = "state_exam_public_admin_demo.db"
RELEASE_EXAM_IDS = tuple(
    str(course.get("exam_id", "")).strip()
    for course in COURSE_CATALOG
    if str(course.get("exam_id", "")).strip()
)
_LOG = logging.getLogger(__name__)


def _seed_candidates(workspace_root: Path) -> list[Path]:
    """Paths where a bundled seed DB may live, in priority order.

    When running from source (``python -m ui_flet.main``) we look at the
    repo's ``data/`` and ``build/demo_seed/``. When running frozen through
    flet-pack / pyinstaller, ``sys._MEIPASS`` points at the temporary
    extraction directory that contains ``data/`` (per the --add-data flag
    in scripts/build_flet_exe.ps1). We also look next to the exe and in the
    workspace root for user-shipped copies.
    """
    paths: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(Path(meipass) / "data" / SEED_FILENAME)
        paths.append(Path(meipass) / SEED_FILENAME)
    paths.append(REPO_ROOT / "data" / SEED_FILENAME)
    paths.append(REPO_ROOT / "build" / "demo_seed" / SEED_FILENAME)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "data" / SEED_FILENAME)
        paths.append(exe_dir / SEED_FILENAME)
    paths.append(workspace_root / "data" / SEED_FILENAME)
    return paths


def _ticket_count(db_path: Path) -> int:
    """Return tickets count; 0 on any error (file missing, table missing, etc)."""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def _select_seed_candidate(workspace_root: Path) -> Path | None:
    for candidate in _seed_candidates(workspace_root):
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def _count_tickets_for_exam(connection: sqlite3.Connection, exam_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE exam_id = ?",
        (exam_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def _missing_release_exam_ids(connection: sqlite3.Connection) -> list[str]:
    return [
        exam_id
        for exam_id in RELEASE_EXAM_IDS
        if _count_tickets_for_exam(connection, exam_id) <= 0
    ]


def _shared_table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    main_cols = [
        row[1]
        for row in connection.execute(f"PRAGMA main.table_info({table_name})").fetchall()
    ]
    seed_cols = {
        row[1]
        for row in connection.execute(f"PRAGMA seed.table_info({table_name})").fetchall()
    }
    return [col for col in main_cols if col in seed_cols]


def _copy_seed_rows(
    connection: sqlite3.Connection,
    table_name: str,
    where_clause: str,
    params: tuple[object, ...],
) -> None:
    columns = _shared_table_columns(connection, table_name)
    if not columns:
        return
    insert_cols = ", ".join(columns)
    select_cols = ", ".join(f"seed.{table_name}.{col}" for col in columns)
    connection.execute(
        f"""
        INSERT OR REPLACE INTO main.{table_name} ({insert_cols})
        SELECT {select_cols}
        FROM seed.{table_name}
        WHERE {where_clause}
        """,
        params,
    )


def _merge_release_seed_content(database_path: Path, seed_path: Path) -> bool:
    if not RELEASE_EXAM_IDS:
        return False

    placeholders = ", ".join("?" for _ in RELEASE_EXAM_IDS)
    exam_params: tuple[object, ...] = tuple(RELEASE_EXAM_IDS)
    ticket_filter = (
        f"ticket_id IN (SELECT ticket_id FROM seed.tickets WHERE exam_id IN ({placeholders}))"
    )
    document_filter = (
        f"document_id IN (SELECT document_id FROM seed.source_documents WHERE exam_id IN ({placeholders}))"
    )
    concept_filter = (
        "concept_id IN ("
        f"SELECT DISTINCT concept_id FROM seed.ticket_concepts WHERE {ticket_filter}"
        ")"
    )

    connection = sqlite3.connect(str(database_path))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("ATTACH DATABASE ? AS seed", (str(seed_path),))
        missing_exam_ids = _missing_release_exam_ids(connection)
        if not missing_exam_ids:
            return False

        connection.execute("BEGIN")
        _copy_seed_rows(connection, "exams", f"exam_id IN ({placeholders})", exam_params)
        _copy_seed_rows(connection, "sections", f"exam_id IN ({placeholders})", exam_params)
        _copy_seed_rows(connection, "subjects", f"exam_id IN ({placeholders})", exam_params)
        _copy_seed_rows(connection, "source_documents", f"exam_id IN ({placeholders})", exam_params)
        _copy_seed_rows(connection, "content_chunks", document_filter, exam_params)
        _copy_seed_rows(connection, "tickets", f"exam_id IN ({placeholders})", exam_params)
        _copy_seed_rows(connection, "atoms", ticket_filter, exam_params)
        _copy_seed_rows(connection, "skills", ticket_filter, exam_params)
        _copy_seed_rows(connection, "exercise_templates", ticket_filter, exam_params)
        _copy_seed_rows(connection, "scoring_rubrics", ticket_filter, exam_params)
        _copy_seed_rows(connection, "examiner_prompts", ticket_filter, exam_params)
        _copy_seed_rows(connection, "cross_ticket_concepts", concept_filter, exam_params)
        _copy_seed_rows(connection, "ticket_concepts", ticket_filter, exam_params)
        _copy_seed_rows(connection, "ticket_answer_blocks", ticket_filter, exam_params)
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.execute("DETACH DATABASE seed")
        except Exception:
            pass
        try:
            connection.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        connection.close()


def _bootstrap_seed_if_empty(workspace_root: Path, database_path: Path) -> str:
    """Initialize or repair bundled release content in the workspace DB.

    Returns a short diagnostic string for logging:
    "seeded", "merged_release_content", "skipped_has_data", "no_source",
    or "failed". Never raises - bootstrap failure leaves the app in its current
    state and users may see an incomplete catalog.
    """
    candidate = _select_seed_candidate(workspace_root)
    if candidate is None:
        return "no_source"

    if _ticket_count(database_path) <= 0:
        try:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, database_path)
            return "seeded"
        except Exception:
            _LOG.exception(
                "Seed bootstrap copy failed source=%s target=%s",
                candidate,
                database_path,
            )
            return "failed"

    try:
        if _merge_release_seed_content(database_path, candidate):
            return "merged_release_content"
        return "skipped_has_data"
    except Exception:
        _LOG.exception(
            "Release-content merge failed source=%s target=%s",
            candidate,
            database_path,
        )
        return "failed"


def _pick_fallback_exam_id(connection: sqlite3.Connection) -> str | None:
    seen: set[str] = set()
    preferred_exam_ids = [DEFAULT_EXAM_ID, *RELEASE_EXAM_IDS]
    for exam_id in preferred_exam_ids:
        if exam_id in seen:
            continue
        seen.add(exam_id)
        if _count_tickets_for_exam(connection, exam_id) > 0:
            return exam_id

    rows = connection.execute(
        """
        SELECT exam_id, COUNT(*) AS tickets_count
        FROM tickets
        GROUP BY exam_id
        ORDER BY tickets_count DESC, exam_id ASC
        """
    ).fetchall()
    for row in rows:
        exam_id = str(row[0] or "").strip()
        if exam_id:
            return exam_id
    return None


def _ensure_profile_exam_compatibility(
    profile_store: ProfileStore,
    profile: UserProfile | None,
    connection: sqlite3.Connection,
) -> UserProfile | None:
    if profile is None:
        return None

    desired_exam_id = str(getattr(profile, "active_exam_id", "") or "").strip()
    if desired_exam_id and _count_tickets_for_exam(connection, desired_exam_id) > 0:
        return profile

    fallback_exam_id = _pick_fallback_exam_id(connection)
    if not fallback_exam_id:
        return profile

    repaired = replace(profile, active_exam_id=fallback_exam_id)
    if repaired.active_exam_id == desired_exam_id:
        return repaired

    try:
        profile_store.save(repaired)
    except Exception:
        _LOG.exception(
            "Profile exam repair could not be persisted from=%s to=%s",
            desired_exam_id,
            fallback_exam_id,
        )
    _LOG.warning(
        "Profile exam repaired from=%s to=%s",
        desired_exam_id or "<empty>",
        fallback_exam_id,
    )
    return repaired


def _build_facade(workspace_root: Path | None = None) -> tuple[AppFacade, Path]:
    workspace_root = workspace_root or get_workspace_root()
    database_path = get_database_path(workspace_root)
    seed_status = _bootstrap_seed_if_empty(workspace_root, database_path)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    facade = AppFacade(workspace_root, connection, settings_store)
    _LOG.info(
        "Facade built workspace=%s database=%s seed_status=%s",
        workspace_root,
        database_path,
        seed_status,
    )
    return facade, database_path


def _reset_state_to_cold_start(state: AppState, workspace_root: Path) -> None:
    _LOG.info("Cold reset requested workspace=%s", workspace_root)
    # Wipe on-disk state first. If this fails (e.g. a second running
    # instance holds a Windows lock on exam_trainer.db), surface the
    # failure rather than letting the caller show a silent "сброшено"
    # snackbar on top of leftover data.
    state.facade.reset_application_data()
    _LOG.info("Cold reset: disk wiped")

    facade, _ = _build_facade(workspace_root)
    state.facade = facade
    profile_store = ProfileStore(workspace_root / "app_data" / "profile.json")
    state.user_profile = _ensure_profile_exam_compatibility(
        profile_store,
        profile_store.load(),
        facade.connection,
    )
    state.selected_ticket_id = None
    state.selected_mode = "reading"
    state.day_closed_at = None
    state.ollama_online = None
    state.ticket_quality_cache = state.ticket_quality_cache.__class__()
    _LOG.info("Cold reset: state reset, profile=%s", state.user_profile is not None)

    try:
        state.ticket_quality_cache.prime(
            facade.load_ticket_maps(exam_id=state.active_exam_id)
        )
    except Exception:
        _LOG.exception("Skeleton-quality priming failed after cold reset")

    settings = getattr(facade, "settings", None)
    saved_window_mode = getattr(settings, "window_mode", "fullscreen") or "fullscreen"
    saved_window_width = int(getattr(settings, "window_width", 1440) or 1440)
    saved_window_height = int(getattr(settings, "window_height", 900) or 900)
    _apply_window_mode(state.page, saved_window_mode, saved_window_width, saved_window_height)

    state.is_dark = getattr(settings, "theme_name", "light") == "dark"
    from ui_flet.theme.tokens import set_active_family

    set_active_family(getattr(settings, "theme_family", "warm") or "warm")
    apply_theme(state.page, state.is_dark)
    state.probe_ollama()

    # Force navigation to onboarding. views.clear() alone doesn't redraw;
    # we bounce route to "/" first to invalidate the current view key, then
    # go to /onboarding so the router sees a real transition.
    state.page.views.clear()
    try:
        state.page.update()
    except Exception:
        _LOG.exception("page.update() after views.clear() failed")
    state.page.route = "/"
    state.page.go("/onboarding")
    _LOG.info("Cold reset: navigated to /onboarding")


def _on_resize(state: AppState):
    def _handler(_event: ft.WindowEvent) -> None:
        width = state.page.window.width or state.page.width or 1280
        if state.update_breakpoint(float(width)):
            state.page.update()

    return _handler


def _configure_page(page: ft.Page) -> None:
    page.title = "Тезис - подготовка к письменному госэкзамену"
    page.padding = 0
    page.spacing = 0
    page.fonts = font_map()
    page.window.min_width = 1024
    page.window.min_height = 700
    # Кастомная иконка окна (вместо стандартной Flet) — ар-деко brand-mark.
    icon_path = REPO_ROOT / "assets" / "logo" / "tezis-deco.ico"
    if icon_path.exists():
        try:
            page.window.icon = str(icon_path)
        except Exception:
            _LOG.exception("Failed to set window icon")


def _apply_window_mode(page: ft.Page, mode: str, width: int, height: int) -> None:
    """Translate ``window_mode`` persistence into Flet window props."""
    if mode == "fullscreen":
        page.window.full_screen = True
    else:
        page.window.full_screen = False
        page.window.width = float(width)
        page.window.height = float(height)


def _install_keyboard_handler(state: AppState) -> None:
    """Esc leaves fullscreen and falls back to the persisted windowed size."""

    def _on_keyboard(event: ft.KeyboardEvent) -> None:
        key = getattr(event, "key", "") or ""
        if key == "Escape" and state.page.window.full_screen:
            settings = getattr(state.facade, "settings", None)
            width = int(getattr(settings, "window_width", 1440) or 1440)
            height = int(getattr(settings, "window_height", 900) or 900)
            _apply_window_mode(state.page, "windowed", width, height)
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
        _LOG.exception("Window mode persistence failed mode=%s", mode)


def _build_fullscreen_toggle(state: AppState) -> ft.FloatingActionButton:
    """A tiny floating toggle for fullscreen / windowed."""

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
            _LOG.exception("Fullscreen FAB update failed")
        state.page.update()

    fab.on_click = _on_click
    return fab


def _build_startup_error_view(log_path: Path, exc: Exception) -> ft.View:
    return ft.View(
        route="/startup-error",
        padding=0,
        controls=[
            ft.Container(
                expand=True,
                padding=32,
                content=ft.Column(
                    [
                        ft.Text("Не удалось запустить приложение", size=24, weight=ft.FontWeight.W_600),
                        ft.Text(f"{type(exc).__name__}: {exc}", selectable=True, color=ft.Colors.RED_700),
                        ft.Text(f"Смотрите лог: {log_path}", selectable=True),
                    ],
                    spacing=12,
                ),
            )
        ],
    )


def _main(page: ft.Page) -> None:
    workspace_root = get_workspace_root()
    log_path = setup_runtime_logging(workspace_root, component="flet")
    _LOG.info("Flet startup workspace=%s frozen=%s", workspace_root, getattr(sys, "frozen", False))

    try:
        _configure_page(page)
        facade, _ = _build_facade(workspace_root)
        state = AppState(page=page, facade=facade)
        state.cold_reset_callback = lambda: _reset_state_to_cold_start(state, workspace_root)

        profile_store = ProfileStore(workspace_root / "app_data" / "profile.json")
        state.user_profile = _ensure_profile_exam_compatibility(
            profile_store,
            profile_store.load(),
            facade.connection,
        )
        _LOG.info(
            "Profile load result exists=%s name=%s",
            state.user_profile is not None,
            getattr(state.user_profile, "name", None),
        )

        try:
            state.ticket_quality_cache.prime(
                facade.load_ticket_maps(exam_id=state.active_exam_id)
            )
        except Exception:
            _LOG.exception("Skeleton-quality priming failed — markers will be cold-computed on demand")

        settings = getattr(facade, "settings", None)
        saved_window_mode = getattr(settings, "window_mode", "fullscreen") or "fullscreen"
        saved_window_width = int(getattr(settings, "window_width", 1440) or 1440)
        saved_window_height = int(getattr(settings, "window_height", 900) or 900)
        _apply_window_mode(page, saved_window_mode, saved_window_width, saved_window_height)

        theme_name = getattr(settings, "theme_name", "light") if settings else "light"
        state.is_dark = theme_name == "dark"

        from ui_flet.theme.tokens import set_active_family
        theme_family = getattr(settings, "theme_family", "warm") if settings else "warm"
        set_active_family(theme_family)

        apply_theme(page, state.is_dark)

        state.probe_ollama()

        def _on_theme_change() -> None:
            apply_theme(page, state.is_dark)
            state.refresh()

        state.on_theme_change(_on_theme_change)

        page.on_route_change = on_route_change(state)
        page.window.on_event = _on_resize(state)

        _install_keyboard_handler(state)

        page.floating_action_button = _build_fullscreen_toggle(state)
        page.floating_action_button_location = ft.FloatingActionButtonLocation.END_TOP

        if page.width:
            state.update_breakpoint(float(page.width))

        if state.user_profile is None:
            initial_route = "/onboarding"
        else:
            initial_route = page.route or "/dashboard"
        _LOG.info("Flet initial navigation route=%s breakpoint=%s", initial_route, state.breakpoint)
        page.go(initial_route)

        # Мягкое напоминание заниматься (если пользователь его включил
        # и сегодня ещё не делал ни одной попытки).
        try:
            from application.reminders import reminder_message, should_remind_now
            from ui_flet.components.feedback import show_snackbar
            if should_remind_now(state.user_profile, facade.connection):
                # Небольшая задержка, чтобы snackbar появился ПОСЛЕ
                # отрисовки стартового экрана, а не вместе с ним.
                import threading
                def _delayed_reminder() -> None:
                    try:
                        show_snackbar(state, reminder_message(state.user_profile))
                    except Exception:
                        _LOG.exception("Reminder snackbar failed")
                threading.Timer(1.2, _delayed_reminder).start()
        except Exception:
            _LOG.exception("Reminder trigger failed")
    except Exception as exc:
        _LOG.exception("Fatal Flet startup error")
        page.views.clear()
        page.views.append(_build_startup_error_view(log_path, exc))
        page.update()


def main() -> None:
    ft.app(target=_main)


if __name__ == "__main__":
    main()
