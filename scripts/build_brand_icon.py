"""Сгенерировать ар-деко brand-иконку «Тезис».

Стиль: forest green фон / antique brass рамка / ivory литера «Т» /
три ромба ар-деко орнаментом снизу. Подходит к семейству тем `deco`.

Запуск:
    python scripts/build_brand_icon.py
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "logo"
ASSETS.mkdir(parents=True, exist_ok=True)

# Палитра deco (повторяет ui_flet/theme/tokens.py — _DECO_LIGHT/DARK).
GREEN = (31, 79, 71)            # forest green — основной фон
GREEN_DARK = (17, 50, 44)       # для тени
IVORY = (244, 236, 211)         # литера и орнамент
BRASS = (184, 163, 109)         # antique brass — рамка
BRASS_LIGHT = (226, 209, 156)   # светлая позолота — внутренняя линия
INK = (31, 42, 42)              # тонкая внешняя обводка

W = H = 1024  # большой исходник, потом скейлим


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Bold serif с поддержкой кириллицы (для буквы «Т»)."""
    candidates = [
        r"C:\Windows\Fonts\georgiab.ttf",
        r"C:\Windows\Fonts\cambriab.ttf",
        r"C:\Windows\Fonts\timesbd.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def render_icon(out_size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Внешний круг — глубокий зелёный.
    pad = 32
    d.ellipse((pad, pad, W - pad, H - pad), fill=GREEN)

    # Тонкая внешняя обводка цвета ink (для контраста на любом фоне).
    d.ellipse((pad, pad, W - pad, H - pad), outline=INK, width=4)

    # Двойная антик-золотая рамка (ар-деко двойная линия).
    d.ellipse((pad + 28, pad + 28, W - pad - 28, H - pad - 28), outline=BRASS, width=5)
    d.ellipse((pad + 44, pad + 44, W - pad - 44, H - pad - 44), outline=BRASS_LIGHT, width=2)

    # Литера «Т» — крупно, по центру, цвета ivory.
    font = _font(560)
    text = "Т"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2 - bbox[0]
    ty = (H - th) // 2 - bbox[1] - 30  # сдвиг вверх — место для орнамента
    d.text((tx, ty), text, font=font, fill=IVORY)

    # Три ромба под литерой — классический ар-деко орнамент.
    diamond_y = H - pad - 130
    for i, dx in enumerate((-90, 0, 90)):
        cx = W // 2 + dx
        size = 14 if i == 1 else 10
        d.polygon(
            [(cx, diamond_y - size), (cx + size, diamond_y),
             (cx, diamond_y + size), (cx - size, diamond_y)],
            fill=BRASS_LIGHT,
            outline=BRASS,
        )

    # Тонкие декоративные горизонтальные линии-«колонны» по бокам литеры.
    line_y = H // 2 + 30
    d.line((pad + 100, line_y, pad + 220, line_y), fill=BRASS, width=3)
    d.line((W - pad - 220, line_y, W - pad - 100, line_y), fill=BRASS, width=3)
    # Параллельные тонкие.
    d.line((pad + 130, line_y + 18, pad + 200, line_y + 18), fill=BRASS_LIGHT, width=2)
    d.line((W - pad - 200, line_y + 18, W - pad - 130, line_y + 18), fill=BRASS_LIGHT, width=2)

    return img.resize((out_size, out_size), Image.LANCZOS)


def main() -> None:
    # Главный PNG.
    png_main = render_icon(256)
    png_main.save(ASSETS / "tezis-deco.png")
    # Лого крупного формата для onboarding/about.
    render_icon(512).save(ASSETS / "tezis-deco-512.png")
    # ICO для Windows (несколько размеров в одном файле).
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base = render_icon(256)
    base.save(ASSETS / "tezis-deco.ico", format="ICO", sizes=sizes)
    print(f"Wrote: {ASSETS / 'tezis-deco.png'}")
    print(f"Wrote: {ASSETS / 'tezis-deco-512.png'}")
    print(f"Wrote: {ASSETS / 'tezis-deco.ico'}")


if __name__ == "__main__":
    main()
