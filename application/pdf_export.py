"""PDF-экспорт билетов («Карманный конспект»).

Визуальное направление: Ар-деко + денди + олд мани + летняя свежесть.
- ivory cream фон (#FBF6E9) — летняя бумага,
- forest green accent (#1F4F47) — Old Money classics (Brooks Brothers / Ralph Lauren),
- antique brass border (#B8A36D) — аристократическая тёплая позолота,
- deep ink (#1F2A2A) — текст почти чёрный с тёплым отливом,
- три-ромбовая лигатура `◇ ◇ ◇` — ар-деко орнамент (трюк Gatsby-эпохи),
- двойные тонкие линии в шапке/футере, геометричные углы на обложке,
- типографика: Engravers MT для капителей (denuded ар-деко font),
  Cambria для основного текста (классическая олд-мани читаемость).

Шрифты — системные TTF из ``C:\\Windows\\Fonts``, с фолбэком на Helvetica.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from domain.knowledge import TicketKnowledgeMap

_LOG = logging.getLogger(__name__)

# Соответствие методички МДЭ: единый порядок и подписи блоков.
_BLOCK_ORDER = ("intro", "theory", "practice", "skills", "conclusion", "extra")
_BLOCK_LABELS = {
    "intro":      "Введение",
    "theory":     "Теоретическая часть",
    "practice":   "Практическая часть",
    "skills":     "Навыки",
    "conclusion": "Заключение",
    "extra":      "Дополнительные элементы",
}

# Палитра — Ар-деко / Old Money / летняя свежесть.
_C_BG = colors.HexColor("#FBF6E9")        # ivory cream — летняя бумага
_C_TEXT = colors.HexColor("#1F2A2A")      # deep ink с тёплым отливом
_C_MUTED = colors.HexColor("#5A6566")     # slate
_C_ACCENT = colors.HexColor("#1F4F47")    # deep forest green — Old Money classic
_C_BORDER = colors.HexColor("#B8A36D")    # antique brass
_C_BORDER_SOFT = colors.HexColor("#E5DCB8")  # aged paper

_FONT_REGULAR = "Body"        # Cambria — олд-мани читаемость
_FONT_BOLD = "Body-Bold"      # Cambria Bold
_FONT_ITALIC = "Body-Italic"  # Cambria Italic
_FONT_HEAD = "Head-Engr"      # Engravers MT — настоящий ар-деко font


def _register_fonts() -> None:
    """Регистрирует серифный/санс комплект из системных TTF.

    Идемпотентно: повторный вызов — no-op.
    """
    if _FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = {
        _FONT_REGULAR: ["cambria.ttc", "BOOKOS.TTF", "georgia.ttf", "times.ttf"],
        _FONT_BOLD:    ["cambriab.ttf", "BOOKOSB.TTF", "georgiab.ttf", "timesbd.ttf"],
        _FONT_ITALIC:  ["cambriai.ttf", "BOOKOSI.TTF", "georgiai.ttf", "timesi.ttf"],
        # HEAD: нужен шрифт с поддержкой кириллицы. Engravers MT (ENGR.TTF) был бы
        # эталоном ар-деко, но он only-Latin. Для русских заголовков
        # ставим Cambria Bold + разрядку букв — близкий ар-деко эффект.
        _FONT_HEAD:    ["cambriab.ttf", "georgiab.ttf", "timesbd.ttf"],
    }
    for alias, files in candidates.items():
        for fname in files:
            full = fonts_dir / fname
            if full.exists():
                pdfmetrics.registerFont(TTFont(alias, str(full)))
                break
        else:
            _LOG.warning("PDF export: fallback to Helvetica for %s — Cyrillic may break", alias)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    return {
        "ticket_number": ParagraphStyle(
            "ticket_number", parent=base,
            fontName=_FONT_HEAD, fontSize=11, textColor=_C_ACCENT,
            spaceAfter=2 * mm, alignment=TA_LEFT,
        ),
        "title": ParagraphStyle(
            "title", parent=base,
            fontName=_FONT_BOLD, fontSize=20, leading=24, textColor=_C_TEXT,
            spaceAfter=4 * mm,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base,
            fontName=_FONT_ITALIC, fontSize=10, textColor=_C_MUTED,
            spaceAfter=2 * mm,
        ),
        "block_label": ParagraphStyle(
            "block_label", parent=base,
            fontName=_FONT_HEAD, fontSize=10, textColor=_C_ACCENT,
            spaceBefore=4 * mm, spaceAfter=1 * mm,
            leading=12,
        ),
        "block_title": ParagraphStyle(
            "block_title", parent=base,
            fontName=_FONT_BOLD, fontSize=14, textColor=_C_TEXT,
            spaceAfter=2 * mm, leading=17,
        ),
        "block_body": ParagraphStyle(
            "block_body", parent=base,
            fontName=_FONT_REGULAR, fontSize=11, textColor=_C_TEXT,
            spaceAfter=3 * mm, leading=15, alignment=TA_JUSTIFY,
        ),
        "summary": ParagraphStyle(
            "summary", parent=base,
            fontName=_FONT_ITALIC, fontSize=11, textColor=_C_MUTED,
            spaceAfter=4 * mm, leading=14, alignment=TA_JUSTIFY,
            leftIndent=4 * mm, rightIndent=4 * mm,
        ),
        "ornament": ParagraphStyle(
            "ornament", parent=base,
            fontName=_FONT_REGULAR, fontSize=10, textColor=_C_BORDER,
            alignment=TA_CENTER, spaceBefore=2 * mm, spaceAfter=4 * mm,
        ),
        "section_title": ParagraphStyle(
            "section_title", parent=base,
            fontName=_FONT_HEAD, fontSize=10, textColor=_C_ACCENT,
            alignment=TA_CENTER, spaceBefore=2 * mm,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base,
            fontName=_FONT_REGULAR, fontSize=8, textColor=_C_MUTED,
            alignment=TA_CENTER,
        ),
    }


def _ornament(label: str | None = None) -> Paragraph:
    """Ар-деко разделитель: тонкая линия + три ромба ◇ ◇ ◇ (классика 1920-х)."""
    s = _styles()["ornament"]
    if label:
        return Paragraph(f"────  ◇ {label} ◇  ────", s)
    return Paragraph("──────  ◇  ◇  ◇  ──────", s)


def _spaced(text: str) -> str:
    """Разрядка букв через узкие шпации — даёт ощущение капителей."""
    return "\u2009".join(text)


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    """Параграф с safe-escape для XML, переносы строк → <br/>."""
    safe = (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(safe, style)


def _ticket_blocks_by_code(ticket: TicketKnowledgeMap) -> dict[str, object]:
    out: dict[str, object] = {}
    for block in ticket.answer_blocks or []:
        raw = getattr(block, "block_code", "")
        code = str(raw.value if hasattr(raw, "value") else raw).lower().split(".")[-1]
        out[code] = block
    return out


def _render_one_ticket(
    ticket: TicketKnowledgeMap,
    idx: int | None,
    total: int | None,
    *,
    section_title: str | None = None,
    lecturer: str | None = None,
) -> list:
    """Возвращает flowables для одного билета (без PageBreak в конце)."""
    s = _styles()
    flow: list = []

    number_label = _extract_position(ticket.ticket_id) or str(idx or "?")
    flow.append(_para(_spaced(f"БИЛЕТ № {number_label}"), s["ticket_number"]))
    flow.append(_para(ticket.title or "—", s["title"]))

    meta_bits = [b for b in (section_title, lecturer) if b]
    if meta_bits:
        flow.append(_para(" · ".join(meta_bits), s["meta"]))

    flow.append(_ornament())

    if ticket.canonical_answer_summary:
        flow.append(_para(ticket.canonical_answer_summary, s["summary"]))
        flow.append(_ornament())

    blocks_by_code = _ticket_blocks_by_code(ticket)
    for code in _BLOCK_ORDER:
        block = blocks_by_code.get(code)
        if block is None:
            continue
        if getattr(block, "is_missing", False):
            continue
        content = (block.expected_content or "").strip()
        if not content:
            continue
        label = _BLOCK_LABELS.get(code, code).upper()
        title = block.title or _BLOCK_LABELS.get(code, code)
        flow.append(_para(_spaced(label), s["block_label"]))
        if title and title.lower() != _BLOCK_LABELS.get(code, "").lower():
            flow.append(_para(title, s["block_title"]))
        flow.append(_para(content, s["block_body"]))

    return flow


def _extract_position(ticket_id: str | None) -> str | None:
    """Из ticket_id вида ``tkt-002-...`` достаёт ``2``."""
    if not ticket_id:
        return None
    parts = ticket_id.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return str(int(parts[1]))
    return None


def _make_doc(out_path: Path, ticket_count: int) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Тезис — карманный конспект" if ticket_count > 1 else "Тезис — билет",
        author="Тезис · подготовка к МДЭ ГМУ",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0,
    )

    stamp = datetime.now().strftime("%d.%m.%Y")

    def _draw_corner(canvas, x: float, y: float, sx: int, sy: int) -> None:
        """Ар-деко угол: три параллельные линии + микро-ромб (геометрия Gatsby-эпохи)."""
        size = 8 * mm
        canvas.setStrokeColor(_C_BORDER)
        canvas.setLineWidth(0.5)
        # Три параллельные горизонтальные линии возрастающей длины.
        for k, length in enumerate((size, size * 0.7, size * 0.4)):
            offset = k * 1.0 * mm
            canvas.line(x, y + sy * offset, x + sx * length, y + sy * offset)
        # Три параллельные вертикальные линии возрастающей длины.
        for k, length in enumerate((size, size * 0.7, size * 0.4)):
            offset = k * 1.0 * mm
            canvas.line(x + sx * offset, y, x + sx * offset, y + sy * length)
        # Микро-ромб в углу — точка-якорь.
        cx, cy = x + sx * 4.5 * mm, y + sy * 4.5 * mm
        d = 0.7 * mm
        canvas.setFillColor(_C_BORDER)
        p = canvas.beginPath()
        p.moveTo(cx, cy + d)
        p.lineTo(cx + d, cy)
        p.lineTo(cx, cy - d)
        p.lineTo(cx - d, cy)
        p.close()
        canvas.drawPath(p, stroke=0, fill=1)

    def _on_page(canvas, _doc):
        canvas.saveState()
        # Тонкая двойная линия сверху.
        canvas.setStrokeColor(_C_BORDER)
        canvas.setLineWidth(0.4)
        y_top = A4[1] - 12 * mm
        canvas.line(20 * mm, y_top, A4[0] - 20 * mm, y_top)
        canvas.line(20 * mm, y_top - 1.2 * mm, A4[0] - 20 * mm, y_top - 1.2 * mm)
        # Тонкая двойная линия снизу.
        y_bot = 12 * mm
        canvas.line(20 * mm, y_bot + 4 * mm, A4[0] - 20 * mm, y_bot + 4 * mm)
        canvas.line(20 * mm, y_bot + 5.2 * mm, A4[0] - 20 * mm, y_bot + 5.2 * mm)
        # Footer — без декора, просто текст.
        canvas.setFont(_FONT_REGULAR, 8)
        canvas.setFillColor(_C_MUTED)
        canvas.drawCentredString(
            A4[0] / 2, y_bot,
            f"Тезис · подготовка к МДЭ ГМУ · {stamp} · стр. {_doc.page}",
        )
        # Декоративные уголки только на 1-й странице (обложка/титул).
        if _doc.page == 1:
            margin = 12 * mm
            _draw_corner(canvas, margin, A4[1] - margin, +1, -1)            # верх-лево
            _draw_corner(canvas, A4[0] - margin, A4[1] - margin, -1, -1)    # верх-право
            _draw_corner(canvas, margin, margin, +1, +1)                    # низ-лево
            _draw_corner(canvas, A4[0] - margin, margin, -1, +1)            # низ-право
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_on_page)])
    return doc


def generate_ticket_pdf(
    ticket: TicketKnowledgeMap,
    out_path: Path,
    *,
    section_title: str | None = None,
    lecturer: str | None = None,
) -> Path:
    """Один билет → один PDF (1-2 страницы)."""
    _register_fonts()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = _make_doc(out_path, ticket_count=1)
    flow = _render_one_ticket(
        ticket, idx=None, total=None,
        section_title=section_title, lecturer=lecturer,
    )
    doc.build(flow)
    _LOG.info("PDF written: %s (%d bytes)", out_path, out_path.stat().st_size)
    return out_path


def generate_collection_pdf(
    tickets: Iterable[TicketKnowledgeMap],
    out_path: Path,
    *,
    sections_map: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Сборник всех билетов с разделителями по разделам.

    ``sections_map`` — опциональный словарь section_id → {title, lecturer},
    как формирует ``ui_flet/views/tickets_view._load_sections_map``.
    """
    _register_fonts()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tickets = list(tickets)
    sections_map = sections_map or {}
    doc = _make_doc(out_path, ticket_count=len(tickets))

    s = _styles()
    flow: list = []

    # Обложка.
    flow.append(Spacer(1, 55 * mm))
    flow.append(_para(_spaced("ТЕЗИС"), ParagraphStyle(
        "cover_brand", fontName=_FONT_HEAD, fontSize=14, textColor=_C_ACCENT,
        alignment=TA_CENTER, spaceAfter=8 * mm,
    )))
    flow.append(_ornament())
    flow.append(_para("Карманный конспект", ParagraphStyle(
        "cover_title", fontName=_FONT_BOLD, fontSize=30, leading=38,
        textColor=_C_TEXT, alignment=TA_CENTER, spaceAfter=10 * mm,
    )))
    flow.append(_para(
        f"{len(tickets)} билетов МДЭ ГМУ",
        ParagraphStyle(
            "cover_sub", fontName=_FONT_ITALIC, fontSize=12, leading=16,
            textColor=_C_MUTED, alignment=TA_CENTER, spaceAfter=20 * mm,
        ),
    ))
    flow.append(_ornament())
    flow.append(_para(
        datetime.now().strftime("%d.%m.%Y"),
        ParagraphStyle("cover_date", fontName=_FONT_REGULAR, fontSize=10,
                       textColor=_C_MUTED, alignment=TA_CENTER),
    ))
    flow.append(PageBreak())

    # Билеты.
    seen_section: str | None = None
    for i, ticket in enumerate(tickets, start=1):
        meta = sections_map.get(ticket.section_id, {})
        section_title = meta.get("title") or ""
        lecturer = meta.get("lecturer") or ""
        if section_title and section_title != seen_section:
            flow.append(_para(_spaced(section_title.upper()), s["section_title"]))
            flow.append(_ornament())
            seen_section = section_title
        flow.extend(_render_one_ticket(
            ticket, idx=i, total=len(tickets),
            section_title=section_title, lecturer=lecturer,
        ))
        if i < len(tickets):
            flow.append(PageBreak())

    doc.build(flow)
    _LOG.info("Collection PDF written: %s (%d bytes, %d tickets)",
              out_path, out_path.stat().st_size, len(tickets))
    return out_path
