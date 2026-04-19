"""«Спросить у эталона» — чат-панель с AI-наставником на Gemini.

Открывается из Reading workspace кнопкой «Спросить». Контекст — текущий
билет (тема + summary + 6 блоков). Использует ``GeminiService`` через
ключ из settings.json. Если ключ не задан — ведёт в Настройки.

UI: модальный диалог с историей сообщений, полем ввода и кнопкой «Спросить».
Пользователь справа (accent_soft), ассистент слева (bg_elevated). Декор —
``decorative_divider`` под заголовком.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import flet as ft

from infrastructure.gemini import GeminiError, GeminiService
from infrastructure.gemini.service import ticket_context
from ui_flet.components.decorative import divider as decorative_divider
from ui_flet.i18n.ru import TEXT
from ui_flet.state import AppState
from ui_flet.theme.tokens import RADIUS, SPACE, palette, text_style

_LOG = logging.getLogger(__name__)


@dataclass
class _Message:
    role: str  # "user" | "assistant" | "error"
    text: str


def _bubble(p: dict, msg: _Message) -> ft.Control:
    is_user = msg.role == "user"
    is_error = msg.role == "error"
    bg = (
        p["accent_soft"] if is_user
        else (p["danger"] if is_error else p["bg_elevated"])
    )
    fg = (
        p["text_primary"] if is_user
        else (p["bg_surface"] if is_error else p["text_primary"])
    )
    bubble = ft.Container(
        content=ft.Text(msg.text, size=13, color=fg, selectable=True),
        padding=ft.padding.symmetric(horizontal=SPACE["md"], vertical=SPACE["sm"]),
        bgcolor=bg,
        border_radius=RADIUS["md"],
        border=ft.border.all(1, p["border_soft"]),
        width=520,
    )
    return ft.Row(
        [bubble],
        alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
    )


def _settings_from_state(state: AppState):
    try:
        return state.facade.settings
    except Exception:
        return None


def open_ask_etalon_dialog(state: AppState, ticket) -> None:
    """Открыть модальный чат «Спросить у эталона» для конкретного билета."""
    page = state.page
    p = palette(state.is_dark)

    settings = _settings_from_state(state)
    api_key = (getattr(settings, "gemini_api_key", "") or "").strip()
    model = (getattr(settings, "gemini_model", "gemini-2.5-flash") or "gemini-2.5-flash").strip()

    history: list[_Message] = []
    messages_col = ft.Column(spacing=SPACE["sm"], scroll=ft.ScrollMode.AUTO, expand=True)

    def _refresh_messages() -> None:
        messages_col.controls = [_bubble(p, m) for m in history]
        try:
            messages_col.update()
        except Exception:
            pass

    input_field = ft.TextField(
        label=TEXT["ask.input_label"],
        hint_text=TEXT["ask.input_hint"],
        autofocus=True,
        multiline=True,
        min_lines=1,
        max_lines=4,
        border_color=p["border_medium"],
        focused_border_color=p["accent"],
        dense=True,
        expand=True,
    )
    spinner = ft.ProgressRing(width=18, height=18, visible=False)
    send_btn = ft.FilledButton(
        text=TEXT["ask.send"],
        icon=ft.Icons.SEND_OUTLINED,
    )

    def _ask_async(question: str) -> None:
        svc = GeminiService(api_key=api_key, model=model)
        ctx = ticket_context(ticket)
        try:
            answer = svc.ask(question, context=ctx)
            history.append(_Message("assistant", answer))
        except GeminiError as exc:
            history.append(_Message("error", TEXT["ask.error"].format(err=str(exc))))
        except Exception as exc:
            _LOG.exception("Ask-etalon unexpected error")
            history.append(_Message("error", TEXT["ask.error"].format(err=str(exc))))
        finally:
            spinner.visible = False
            send_btn.disabled = False
            input_field.disabled = False
            try:
                spinner.update()
                send_btn.update()
                input_field.update()
            except Exception:
                pass
            _refresh_messages()

    def _on_send(_e=None) -> None:
        question = (input_field.value or "").strip()
        if not question:
            return
        if not api_key:
            history.append(_Message("error", TEXT["ask.no_key"]))
            _refresh_messages()
            return
        history.append(_Message("user", question))
        input_field.value = ""
        spinner.visible = True
        send_btn.disabled = True
        input_field.disabled = True
        try:
            spinner.update()
            send_btn.update()
            input_field.update()
        except Exception:
            pass
        _refresh_messages()
        threading.Thread(target=_ask_async, args=(question,), daemon=True).start()

    send_btn.on_click = _on_send
    input_field.on_submit = _on_send

    header = ft.Column(
        [
            ft.Text(
                TEXT["ask.title"],
                style=text_style("h2", color=p["text_primary"]),
            ),
            ft.Text(
                ticket.title or "",
                style=text_style("caption", color=p["text_muted"]),
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Container(
                content=decorative_divider(state, width=180),
                padding=ft.padding.only(top=SPACE["xs"]),
            ),
        ],
        spacing=SPACE["xs"],
        tight=True,
    )

    body = ft.Container(
        content=messages_col,
        padding=ft.padding.symmetric(vertical=SPACE["sm"]),
        bgcolor=p["bg_base"],
        border_radius=RADIUS["md"],
        height=320,
        width=600,
    )

    input_row = ft.Row(
        [input_field, spinner, send_btn],
        spacing=SPACE["sm"],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    if not api_key:
        history.append(_Message("error", TEXT["ask.no_key"]))

    def _go_settings(_e=None) -> None:
        dlg.open = False
        try:
            page.update()
        except Exception:
            pass
        state.go("/settings")

    dlg = ft.AlertDialog(
        modal=True,
        title=header,
        content=ft.Column(
            [body, input_row],
            spacing=SPACE["sm"],
            tight=True,
        ),
        actions=[
            ft.TextButton(TEXT["ask.open_settings"], on_click=_go_settings),
            ft.TextButton(TEXT["action.close"], on_click=lambda _e: _close()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _close() -> None:
        try:
            page.close(dlg)
        except Exception:
            pass

    # Flet 0.27+: use page.open/page.close instead of the old
    # page.dialog=…; dialog.open=True pattern, which silently no-ops.
    page.open(dlg)
    _refresh_messages()
