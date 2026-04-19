"""Декоративные элементы: разделители, орнаменты, угловые акценты.

Каждый компонент рендерится по-разному в зависимости от активного семейства:
- **warm** — итальянско-средиземноморский язык: керамические точки-azulejo,
  scallop-edges, тёплые охровые акценты.
- **deco** — графический ар-деко: ступенчатые линии, sunburst-веера, ромбы,
  симметричные геометрические композиции.

Композиция через ``ft.Container`` и ``ft.Stack`` — без Canvas/SVG, чтобы
не тащить дополнительные зависимости и работало на всех платформах Flet.
"""

from __future__ import annotations

import math

import flet as ft

from ui_flet.theme.tokens import SPACE, get_active_family, palette

# ── Базовые примитивы ──────────────────────────────────────────────────

def _dot(color: str, size: int = 6) -> ft.Control:
    """Маленькая круглая точка — азулехо/керамика для warm."""
    return ft.Container(
        width=size, height=size,
        bgcolor=color,
        border_radius=size,
    )


def _diamond(color: str, size: int = 8, outline: str | None = None) -> ft.Control:
    """Ромб — повёрнутый на 45° квадрат."""
    return ft.Container(
        width=size, height=size,
        bgcolor=color,
        rotate=ft.transform.Rotate(math.pi / 4),
        border=ft.border.all(1, outline) if outline else None,
    )


def _line(color: str, width: int = 60, height: int = 1) -> ft.Control:
    return ft.Container(width=width, height=height, bgcolor=color)


def _ray(color: str, length: int, angle: float, thickness: int = 1) -> ft.Control:
    """Луч-линия под углом — кирпичик для sunburst."""
    return ft.Container(
        width=length, height=thickness,
        bgcolor=color,
        rotate=ft.transform.Rotate(angle, alignment=ft.alignment.center_left),
    )


# ── Разделители ────────────────────────────────────────────────────────

def divider(state, *, width: int = 220) -> ft.Control:
    """Декоративный горизонтальный разделитель в стиле активного семейства.

    warm — линия + три керамические точки (азулехо).
    deco — двойная тонкая линия + три ромба между.
    """
    p = palette(state.is_dark)
    family = get_active_family()
    ornament = p.get("ornament", p["border_medium"])
    soft = p["border_soft"]

    if family == "deco":
        # Двойная линия с тремя ромбами по центру.
        diamonds = ft.Row(
            [_diamond(ornament, size=6), _diamond(ornament, size=8), _diamond(ornament, size=6)],
            spacing=SPACE["sm"],
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        side = ft.Column(
            [_line(ornament, width=width // 3, height=1),
             ft.Container(height=2),
             _line(soft, width=width // 3, height=1)],
            spacing=0, tight=True,
        )
        return ft.Row(
            [side, ft.Container(width=SPACE["sm"]), diamonds, ft.Container(width=SPACE["sm"]), side],
            tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    # warm: одна линия + 3 круглых точки в центре.
    dots = ft.Row(
        [_dot(ornament, 4), _dot(ornament, 6), _dot(ornament, 4)],
        spacing=SPACE["sm"],
        tight=True,
    )
    return ft.Row(
        [_line(ornament, width=width // 3, height=1),
         ft.Container(width=SPACE["sm"]),
         dots,
         ft.Container(width=SPACE["sm"]),
         _line(ornament, width=width // 3, height=1)],
        tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )


def thin_top_border(state) -> ft.Control:
    """Двойная тонкая линия (для deco — двойная, для warm — с азулехо-точками).
    Используется как нижняя граница TopBar для подчёркнутого вкуса.
    """
    p = palette(state.is_dark)
    family = get_active_family()
    ornament = p.get("ornament", p["border_medium"])
    soft = p["border_soft"]

    if family == "deco":
        return ft.Column(
            [_line(ornament, width=4000, height=1),
             ft.Container(height=2),
             _line(soft, width=4000, height=1)],
            spacing=0, tight=True,
        )
    # warm — одна линия + равномерно расставленные керамические dots снизу.
    return ft.Stack(
        [
            ft.Container(height=1, bgcolor=ornament),
            ft.Row(
                [_dot(ornament, 4) for _ in range(40)],
                spacing=24,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        height=8,
    )


# ── Sunburst-веер (только deco) ─────────────────────────────────────────

def sunburst_badge(state, *, size: int = 36) -> ft.Control:
    """Маленький декоративный sunburst-веер — ар-деко медальон.

    На warm возвращает аналог — концентрические точки (azulejo-розетка).
    """
    p = palette(state.is_dark)
    family = get_active_family()
    ornament = p.get("ornament", p["border_medium"])

    if family == "deco":
        rays = []
        ray_len = size // 2 - 3
        for i in range(7):
            angle = -math.pi / 2 + (math.pi / 6) * (i - 3)
            rays.append(
                ft.Container(
                    content=_ray(ornament, ray_len, angle, thickness=1),
                    alignment=ft.alignment.bottom_center,
                    width=size, height=size,
                )
            )
        # Полу-круглая «земля» внизу.
        base = ft.Container(
            width=size, height=size // 2,
            bgcolor=p["accent_soft"],
            border_radius=ft.border_radius.only(top_left=size, top_right=size),
            alignment=ft.alignment.bottom_center,
        )
        return ft.Stack([base, *rays], width=size, height=size)

    # warm — мини-розетка: точка в центре + 4 точки вокруг.
    return ft.Stack(
        [
            ft.Container(
                content=_dot(ornament, 6),
                alignment=ft.alignment.center,
                width=size, height=size,
            ),
            ft.Container(content=_dot(ornament, 3), alignment=ft.alignment.top_center, width=size, height=size),
            ft.Container(content=_dot(ornament, 3), alignment=ft.alignment.bottom_center, width=size, height=size),
            ft.Container(content=_dot(ornament, 3), alignment=ft.alignment.center_left, width=size, height=size),
            ft.Container(content=_dot(ornament, 3), alignment=ft.alignment.center_right, width=size, height=size),
        ],
        width=size, height=size,
    )


# ── Карточные углы ─────────────────────────────────────────────────────

def card_corner(state, *, size: int = 14) -> ft.Control:
    """Маленький угловой орнамент для верхнего-правого угла карточки.

    deco — три параллельные ступенчатые линии (Chrysler Building).
    warm — маленький ромбик + точка.
    """
    p = palette(state.is_dark)
    family = get_active_family()
    ornament = p.get("ornament", p["border_medium"])

    if family == "deco":
        return ft.Column(
            [
                _line(ornament, width=size, height=1),
                ft.Container(height=2),
                _line(ornament, width=int(size * 0.7), height=1),
                ft.Container(height=2),
                _line(ornament, width=int(size * 0.4), height=1),
            ],
            spacing=0,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.END,
        )
    return ft.Row(
        [_dot(ornament, 3), ft.Container(width=3), _diamond(ornament, size=6)],
        spacing=0, tight=True,
    )
