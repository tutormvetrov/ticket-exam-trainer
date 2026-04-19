"""Font registration for Flet.

In dev we rely on Google Fonts URLs. For the packaged exe, drop TTFs into
ui_flet/theme/fonts/ — Flet will pick up the bundled files via ft.Page.fonts.

Flet 0.27 supports URL-based and file-based font registration through
`page.fonts = {family: path_or_url}`. We prefer bundled TTFs to avoid
network dependency on classmates' machines behind corporate firewalls.
"""

from __future__ import annotations

from pathlib import Path

FONTS_DIR = Path(__file__).parent / "fonts"

# Bundled TTF fallback — present only if scripts/download_fonts.ps1 was run.
BUNDLED_FONTS: dict[str, str] = {}
if FONTS_DIR.exists():
    for ttf in FONTS_DIR.glob("*.ttf"):
        # Flet expects family name matching the one used in TextStyle.font_family.
        # Filename convention: "<FamilyName>-Regular.ttf" or "<FamilyName>.ttf".
        family = ttf.stem.split("-")[0].replace("_", " ")
        BUNDLED_FONTS[family] = str(ttf.resolve())

# Google Fonts URLs as network fallback (only hit on first run if no bundle).
# Visual direction: Art Deco / Old Money / dandy / summer freshness.
# - Playfair Display — high-contrast Didot-style serif (Gatsby / Vogue look).
# - Cormorant Garamond — refined Garamond cousin for body & captions.
# - Lora — kept as cyrillic-safe fallback.
GOOGLE_FALLBACK: dict[str, str] = {
    "Playfair Display": "https://fonts.gstatic.com/s/playfairdisplay/v37/nuFvD-vYSZviVYUb_rj3ij__anPXJzDwcbmjWBN2PKdFvUDQZNLo_U2r.woff2",
    "Cormorant Garamond": "https://fonts.gstatic.com/s/cormorantgaramond/v16/co3bmX5slCNuHLi8bLeY9MK7whWMhyjQEHLuPQ.woff2",
    "Lora": "https://fonts.gstatic.com/s/lora/v35/0QI6MX1D_JOuGQbT0gvTJPa787weuyJGmKxemMeZ.woff2",
    "Golos Text": "https://fonts.gstatic.com/s/golostext/v4/q5uXsoe9Lv5t7Meb31EcOR9UdVTNs822plVRRQ.woff2",
    "JetBrains Mono": "https://fonts.gstatic.com/s/jetbrainsmono/v20/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKxjPVmUsaaDhw.woff2",
}


def font_map() -> dict[str, str]:
    """Return font family → URL/path mapping, preferring bundled TTFs."""
    out: dict[str, str] = {}
    out.update(GOOGLE_FALLBACK)  # base URLs
    out.update(BUNDLED_FONTS)    # bundled overrides (if any)
    return out
