from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QPushButton

from ui.theme import current_colors


_SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">__BODY__</svg>"""

_ICON_BODIES = {
    "library": '<path d="M4 6.5c0-1.1.9-2 2-2h10.5c1.1 0 2 .9 2 2V18a1 1 0 0 1-1.4.9l-4.1-1.8-4.1 1.8A1 1 0 0 1 7.5 18V6.5"/><path d="M7.5 4.5v12.8"/>',
    "subjects": '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5h3l1.8 2H17.5A2.5 2.5 0 0 1 20 9.5v7A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z"/><path d="M4 10h16"/>',
    "sections": '<rect x="4" y="5" width="16" height="4" rx="1.5"/><rect x="4" y="10" width="16" height="4" rx="1.5"/><rect x="4" y="15" width="16" height="4" rx="1.5"/>',
    "tickets": '<path d="M6 5.5h12a1.5 1.5 0 0 1 1.5 1.5v2.2a2 2 0 0 0 0 3.6V15A1.5 1.5 0 0 1 18 16.5H6A1.5 1.5 0 0 1 4.5 15v-2.2a2 2 0 0 0 0-3.6V7A1.5 1.5 0 0 1 6 5.5Z"/><path d="M9 9.5h6M9 12h6"/>',
    "import": '<path d="M12 4.5v10"/><path d="m8 10.5 4 4 4-4"/><path d="M5 18.5h14"/>',
    "training": '<path d="M12 3.5 14.6 9l5.9.8-4.3 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.5 9.8 9.4 9z"/>',
    "statistics": '<path d="M5 18.5V10"/><path d="M10 18.5V6.5"/><path d="M15 18.5v-4"/><path d="M20 18.5V8.5"/><path d="M3.5 18.5h17"/>',
    "knowledge-map": '<circle cx="6" cy="7" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="17" r="2.5"/><path d="M8.2 8.4 10.3 14.8M15.8 7.5l-2.2 7.1M8.4 7.2h7.1"/>',
    "defense": '<path d="M12 4.5 18.2 7v4.8c0 4-2.5 6.5-6.2 7.7-3.7-1.2-6.2-3.7-6.2-7.7V7z"/><path d="m9.3 11.9 1.8 1.9 3.6-3.8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 4.5v2.2M12 17.3v2.2M4.5 12h2.2M17.3 12h2.2M6.7 6.7l1.5 1.5M15.8 15.8l1.5 1.5M17.3 6.7l-1.5 1.5M8.2 15.8l-1.5 1.5"/>',
    "refresh": '<path d="M20 11.5A7.5 7.5 0 1 1 17.4 6"/><path d="M20 5.5V11h-5.5"/>',
    "document": '<path d="M8 4.5h6l4 4V18A1.5 1.5 0 0 1 16.5 19.5h-9A1.5 1.5 0 0 1 6 18V6A1.5 1.5 0 0 1 7.5 4.5Z"/><path d="M14 4.5V9h4"/><path d="M9 13h6M9 16h4"/>',
    "queue": '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="5" cy="6.5" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="5" cy="17.5" r="1"/>',
    "spark": '<path d="m12 3.5 1.4 4.1 4.1 1.4-4.1 1.4L12 14.5l-1.4-4.1-4.1-1.4 4.1-1.4Z"/><path d="m18.5 14.5.8 2.3 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z"/><path d="m5.5 14.8.9 2.4 2.3.9-2.3.8-.9 2.3-.8-2.3-2.4-.8 2.4-.9Z"/>',
    "search": '<circle cx="11" cy="11" r="5.5"/><path d="m16 16 4 4"/>',
}

_VARIANT_TONES = {
    "primary": ("#FFFFFF", None),
    "secondary": ("text_secondary", None),
    "outline": ("text_secondary", None),
    "toolbar": ("text", None),
    "toolbar-ghost": ("text", None),
    "nav": ("text_secondary", "#FFFFFF"),
    "tab": ("text_secondary", "primary"),
    "settings-nav": ("text_secondary", "primary"),
}


def icon_names() -> tuple[str, ...]:
    return tuple(sorted(_ICON_BODIES))


def _resolve_color_token(token: str) -> str:
    colors = current_colors()
    if token in colors:
        return str(colors[token])
    return token


def _svg_markup(name: str, color_hex: str) -> str:
    if name not in _ICON_BODIES:
        raise KeyError(f"Unknown icon: {name}")
    color = QColor(color_hex).name()
    return _SVG_TEMPLATE.replace("__COLOR__", color).replace("__BODY__", _ICON_BODIES[name])


@lru_cache(maxsize=512)
def _render_svg(name: str, color_hex: str, size: int) -> QPixmap:
    markup = _svg_markup(name, color_hex)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon_pixmap(name: str, size: int = 20, tone: str = "text") -> QPixmap:
    color_hex = QColor(_resolve_color_token(tone)).name()
    return QPixmap(_render_svg(name, color_hex, max(12, size)))


def build_icon(
    name: str,
    *,
    size: int = 20,
    tone: str = "text",
    on_tone: str | None = None,
    active_tone: str | None = None,
    disabled_tone: str = "text_tertiary",
) -> QIcon:
    icon = QIcon()
    normal_tone = tone
    selected_tone = on_tone or tone
    active_color = active_tone or selected_tone
    icon.addPixmap(icon_pixmap(name, size, normal_tone), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(icon_pixmap(name, size, active_color), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(icon_pixmap(name, size, selected_tone), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(icon_pixmap(name, size, selected_tone), QIcon.Mode.Selected, QIcon.State.On)
    icon.addPixmap(icon_pixmap(name, size, disabled_tone), QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(icon_pixmap(name, size, disabled_tone), QIcon.Mode.Disabled, QIcon.State.On)
    return icon


def apply_button_icon(
    button: QPushButton,
    name: str,
    *,
    size: int = 18,
    tone: str | None = None,
    on_tone: str | None = None,
    disabled_tone: str = "text_tertiary",
) -> None:
    variant = str(button.property("variant") or "").strip()
    base_tone, variant_on_tone = _VARIANT_TONES.get(variant, ("text", None))
    button.setIcon(build_icon(name, size=size, tone=tone or base_tone, on_tone=on_tone or variant_on_tone, disabled_tone=disabled_tone))
    button.setIconSize(QSize(size, size))


class SvgIconLabel(QLabel):
    def __init__(self, name: str, *, size: int = 20, tone: str = "text", parent=None) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        self._tone = tone
        self.setFixedSize(size, size)
        self.refresh_theme()

    def set_icon(self, name: str, *, size: int | None = None, tone: str | None = None) -> None:
        self._name = name
        if size is not None and size != self._size:
            self._size = size
            self.setFixedSize(size, size)
        if tone is not None:
            self._tone = tone
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setPixmap(icon_pixmap(self._name, self._size, self._tone))
