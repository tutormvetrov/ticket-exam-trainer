"""
Генератор HTML-отчёта для просмотра всех билетов Tezis.
Запуск: python scripts/review/generate_ticket_review.py
Результат: ticket_review.html в корне проекта — самодостаточный файл, открывается в браузере.
"""

import html
import io
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.ticket_reference import (
    BLOCK_LABELS,
    BLOCK_ORDER,
    iter_reference_segments,
    normalize_reference_text,
    truncate_reference_text,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"
OUT = REPO_ROOT / "ticket_review.html"

BLOCK_COLORS = {
    "intro": "#4A90D9",
    "theory": "#7B68EE",
    "practice": "#50C878",
    "skills": "#FFB347",
    "conclusion": "#87CEEB",
    "extra": "#DDA0DD",
}


def damage_score(blocks: dict) -> int:
    score = 0
    for content in blocks.values():
        c = (content or "").strip()
        if not c:
            score += 3
            continue
        if c[0].islower():
            score += 3
        if c[-1] not in ".!?»\"'…":
            score += 3
        if c[-1] == ",":
            score += 2
        if len(c) < 80:
            score += 2
    return score


def has_needs_review(blocks: dict) -> bool:
    return any("ТРЕБУЕТ ПРОВЕРКИ" in (v or "") for v in blocks.values())


def load_data():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    exams = {r["exam_id"]: r["title"] for r in conn.execute("SELECT exam_id, title FROM exams")}
    sections = {r["section_id"]: r["title"] for r in conn.execute("SELECT section_id, title FROM sections")}

    tickets = []
    for t in conn.execute(
        "SELECT ticket_id, exam_id, section_id, title, canonical_answer_summary "
        "FROM tickets ORDER BY exam_id, section_id, title"
    ):
        blocks_raw = conn.execute(
            "SELECT block_code, title, expected_content, is_missing "
            "FROM ticket_answer_blocks WHERE ticket_id=? ORDER BY rowid",
            (t["ticket_id"],),
        ).fetchall()

        blocks = {}
        block_titles = {}
        for b in blocks_raw:
            if not b["is_missing"]:
                blocks[b["block_code"]] = normalize_reference_text(b["expected_content"] or "")
                block_titles[b["block_code"]] = b["title"] or ""

        atoms = conn.execute(
            "SELECT label, text FROM atoms WHERE ticket_id=? ORDER BY weight DESC, rowid LIMIT 6",
            (t["ticket_id"],),
        ).fetchall()

        tickets.append(
            {
                "id": t["ticket_id"],
                "exam_id": t["exam_id"],
                "exam_title": exams.get(t["exam_id"], t["exam_id"]),
                "section": sections.get(t["section_id"], ""),
                "title": t["title"] or "",
                "summary": normalize_reference_text(t["canonical_answer_summary"] or ""),
                "blocks": blocks,
                "block_titles": block_titles,
                "atoms": [
                    (
                        truncate_reference_text(a["label"], limit=96),
                        normalize_reference_text(a["text"]),
                    )
                    for a in atoms
                ],
                "score": damage_score(blocks),
                "needs_review": has_needs_review(blocks),
            }
        )

    conn.close()
    return tickets, exams


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def render_block_content(content: str) -> str:
    """Render plain text as HTML paragraphs, preserving list items."""
    if not content:
        return "<em>—</em>"
    needs_review = "ТРЕБУЕТ ПРОВЕРКИ" in content
    parts: list[str] = []
    for segment in iter_reference_segments(content):
        if segment.kind == "list":
            items = "".join(f"<li>{esc(line)}</li>" for line in segment.lines)
            parts.append(f"<ul class='block-list'>{items}</ul>")
        else:
            parts.append(f"<p>{esc(segment.lines[0])}</p>")
    result = "\n".join(parts)
    if needs_review:
        result = '<div class="needs-review-flag">⚠ Требует проверки</div>' + result
    return result


def score_badge(score: int) -> str:
    if score == 0:
        return '<span class="badge badge-ok">✓ Чистый</span>'
    elif score <= 5:
        return f'<span class="badge badge-minor">⚡ {score}</span>'
    elif score <= 11:
        return f'<span class="badge badge-moderate">⚠ {score}</span>'
    else:
        return f'<span class="badge badge-critical">✗ {score}</span>'


def build_html(tickets, exams):
    gmu_tickets = [t for t in tickets if "gmu" in t["exam_id"]]
    ii_tickets = [t for t in tickets if "gmu" not in t["exam_id"]]

    total = len(tickets)
    clean = sum(1 for t in tickets if t["score"] == 0)
    flagged = sum(1 for t in tickets if t["needs_review"])
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Build ticket index for search
    ticket_index = [
        {
            "id": t["id"],
            "title": t["title"],
            "exam": "ГМУ" if "gmu" in t["exam_id"] else "ИИ",
            "score": t["score"],
            "needs_review": t["needs_review"],
        }
        for t in tickets
    ]

    def render_exam_section(exam_tickets: list, exam_label: str) -> str:
        parts = []
        # Group by section
        sections: dict[str, list] = {}
        for t in exam_tickets:
            sec = t["section"] or "Без раздела"
            sections.setdefault(sec, []).append(t)

        for sec_index, (sec_name, sec_tickets) in enumerate(sections.items(), start=1):
            sec_slug = re.sub(r"\W+", "_", sec_name)
            sec_id = f"{exam_label}_{sec_index}_{sec_slug}"
            parts.append(f"""
            <div class="section-group">
              <div class="section-header" onclick="toggleSection('{sec_id}')">
                <span class="section-arrow" id="arr_{sec_id}">▶</span>
                <span class="section-title">{esc(sec_name)}</span>
                <span class="section-count">{len(sec_tickets)} билетов</span>
              </div>
              <div class="section-body" id="sec_{sec_id}" style="display:none">
            """)

            for t in sec_tickets:
                tid = t["id"].replace("-", "_")
                parts.append(f"""
                <div class="ticket" id="t_{tid}"
                     data-title="{esc(t["title"].lower())}"
                     data-exam="{"гму" if "gmu" in t["exam_id"] else "ии"}"
                     data-score="{t["score"]}"
                     data-review="{"1" if t["needs_review"] else "0"}">
                  <div class="ticket-header" onclick="toggleTicket('{tid}')">
                    <span class="ticket-arrow" id="tarr_{tid}">▶</span>
                    <span class="ticket-title">{esc(t["title"])}</span>
                    <span class="ticket-badges">
                      {score_badge(t["score"])}
                      {'<span class="badge badge-review">⚠ Проверка</span>' if t["needs_review"] else ""}
                    </span>
                  </div>
                  <div class="ticket-body" id="tb_{tid}" style="display:none">
                    <div class="ticket-meta">
                      <span class="meta-id">{esc(t["id"])}</span>
                    </div>
                """)

                # Blocks
                for code in BLOCK_ORDER:
                    content = t["blocks"].get(code, "")
                    label = BLOCK_LABELS.get(code, code)
                    color = BLOCK_COLORS.get(code, "#999")
                    if not content:
                        continue
                    parts.append(f"""
                    <div class="block">
                      <div class="block-label" style="border-left-color:{color}">
                        {esc(label)}
                        <span class="block-len">{len(content)} симв.</span>
                      </div>
                      <div class="block-content">
                        {render_block_content(content)}
                      </div>
                    </div>
                    """)

                # Atoms
                if t["atoms"]:
                    atoms_html = "".join(
                        f'<div class="atom"><strong>{esc(label)}</strong><p>{esc(text)}</p></div>'
                        for label, text in t["atoms"]
                    )
                    parts.append(f"""
                    <div class="block">
                      <div class="block-label" style="border-left-color:#aaa">
                        Ключевые узлы
                        <span class="block-len">{len(t["atoms"])}</span>
                      </div>
                      <div class="block-content atoms-grid">
                        {atoms_html}
                      </div>
                    </div>
                    """)

                parts.append("</div></div>")  # ticket-body, ticket

            parts.append("</div></div>")  # section-body, section-group

        return "\n".join(parts)

    gmu_html = render_exam_section(gmu_tickets, "ГМУ")
    ii_html = render_exam_section(ii_tickets, "ИИ")

    index_json = json.dumps(ticket_index, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tezis — Просмотр билетов ({generated_at})</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f5f5f7; color: #1d1d1f; font-size: 14px; line-height: 1.6; }}

  /* ── Top bar ── */
  .topbar {{ background: #1d1d1f; color: #f5f5f7; padding: 12px 24px;
             display: flex; align-items: center; gap: 24px; position: sticky; top: 0; z-index: 100; }}
  .topbar h1 {{ font-size: 16px; font-weight: 600; white-space: nowrap; }}
  .topbar .stats {{ font-size: 12px; color: #aaa; white-space: nowrap; }}
  .topbar input {{ flex: 1; padding: 6px 12px; border-radius: 8px; border: none;
                   background: #333; color: #f5f5f7; font-size: 13px; outline: none; }}
  .topbar input::placeholder {{ color: #888; }}

  /* ── Filter bar ── */
  .filterbar {{ background: #fff; border-bottom: 1px solid #e5e5e7; padding: 8px 24px;
               display: flex; gap: 8px; align-items: center; flex-wrap: wrap; position: sticky; top: 44px; z-index: 99; }}
  .filter-btn {{ padding: 4px 12px; border-radius: 20px; border: 1px solid #d1d1d6;
                 background: #fff; cursor: pointer; font-size: 12px; transition: all .15s; }}
  .filter-btn:hover {{ background: #f0f0f5; }}
  .filter-btn.active {{ background: #1d1d1f; color: #fff; border-color: #1d1d1f; }}
  .filter-count {{ font-size: 12px; color: #666; margin-left: auto; }}

  /* ── Layout ── */
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}

  /* ── Exam tabs ── */
  .exam-tabs {{ display: flex; gap: 0; margin-bottom: 16px; border-radius: 10px; overflow: hidden;
               border: 1px solid #e5e5e7; }}
  .exam-tab {{ flex: 1; padding: 10px; text-align: center; cursor: pointer; background: #fff;
              font-weight: 500; font-size: 13px; transition: background .15s; border: none; }}
  .exam-tab:first-child {{ border-right: 1px solid #e5e5e7; }}
  .exam-tab.active {{ background: #1d1d1f; color: #fff; }}
  .exam-panel {{ display: none; }}
  .exam-panel.active {{ display: block; }}

  /* ── Section group ── */
  .section-group {{ background: #fff; border: 1px solid #e5e5e7; border-radius: 10px;
                   margin-bottom: 8px; overflow: hidden; }}
  .section-header {{ padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px;
                    background: #fafafa; transition: background .15s; user-select: none; }}
  .section-header:hover {{ background: #f0f0f5; }}
  .section-arrow {{ font-size: 10px; color: #666; width: 12px; transition: transform .15s; }}
  .section-title {{ font-weight: 600; flex: 1; }}
  .section-count {{ font-size: 11px; color: #888; }}
  .section-body {{ padding: 4px 0; }}

  /* ── Ticket ── */
  .ticket {{ border-top: 1px solid #f0f0f0; }}
  .ticket[style*="display:none"] {{ display: none !important; }}
  .ticket-header {{ padding: 10px 16px 10px 28px; cursor: pointer; display: flex;
                   align-items: center; gap: 8px; transition: background .15s; user-select: none; }}
  .ticket-header:hover {{ background: #f7f7f9; }}
  .ticket-arrow {{ font-size: 10px; color: #999; width: 12px; transition: transform .15s; }}
  .ticket-title {{ flex: 1; font-size: 13px; }}
  .ticket-badges {{ display: flex; gap: 4px; flex-shrink: 0; }}
  .ticket-body {{ padding: 12px 16px 16px 28px; background: #fafafa; }}
  .ticket-meta {{ font-size: 11px; color: #aaa; margin-bottom: 12px; font-family: monospace; }}

  /* ── Badges ── */
  .badge {{ font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }}
  .badge-ok {{ background: #d4edda; color: #155724; }}
  .badge-minor {{ background: #fff3cd; color: #856404; }}
  .badge-moderate {{ background: #fde8cc; color: #7d4e00; }}
  .badge-critical {{ background: #f8d7da; color: #721c24; }}
  .badge-review {{ background: #fff3cd; color: #856404; }}

  /* ── Blocks ── */
  .block {{ margin-bottom: 12px; }}
  .block-label {{ font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase;
                 letter-spacing: .5px; padding-left: 8px; border-left: 3px solid #ccc;
                 margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }}
  .block-len {{ font-size: 10px; color: #aaa; font-weight: 400; text-transform: none; }}
  .block-content {{ font-size: 13px; color: #333; line-height: 1.65; }}
  .block-content p {{ margin-bottom: 6px; }}
  .block-content p:last-child {{ margin-bottom: 0; }}
  .block-list {{ padding-left: 18px; }}
  .block-list li {{ margin-bottom: 3px; }}

  /* ── Atoms ── */
  .atoms-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 8px; }}
  .atom {{ background: #fff; border: 1px solid #e5e5e7; border-radius: 6px; padding: 8px 10px; }}
  .atom strong {{ font-size: 11px; color: #555; display: block; margin-bottom: 3px; }}
  .atom p {{ font-size: 12px; color: #444; margin: 0; }}

  /* ── Needs review flag ── */
  .needs-review-flag {{ background: #fff3cd; color: #856404; border-radius: 4px;
                        padding: 4px 8px; font-size: 11px; font-weight: 600; margin-bottom: 6px;
                        display: inline-block; }}

  /* ── Hidden by filter ── */
  .ticket.filtered-out {{ display: none !important; }}
  .section-group.all-hidden {{ display: none !important; }}
</style>
</head>
<body>

<div class="topbar">
  <h1>Tezis — Билеты</h1>
  <span class="stats">{total} билетов · {clean} чистых · {flagged} с флагом · {generated_at}</span>
  <input type="text" id="search" placeholder="Поиск по названию…" oninput="applyFilters()">
</div>

<div class="filterbar">
  <button class="filter-btn active" onclick="setFilter('all', this)">Все</button>
  <button class="filter-btn" onclick="setFilter('clean', this)">✓ Чистые</button>
  <button class="filter-btn" onclick="setFilter('damaged', this)">⚠ Повреждённые</button>
  <button class="filter-btn" onclick="setFilter('review', this)">⚠ ТРЕБУЕТ ПРОВЕРКИ</button>
  <button class="filter-btn" onclick="expandAll()">Развернуть всё</button>
  <button class="filter-btn" onclick="collapseAll()">Свернуть всё</button>
  <span class="filter-count" id="filter-count">{total} из {total}</span>
</div>

<div class="container">
  <div class="exam-tabs">
    <button class="exam-tab active" onclick="showExam('gmu', this)">ГМУ ({len(gmu_tickets)} билетов)</button>
    <button class="exam-tab" onclick="showExam('ii', this)">ИИ и Цифровизация ({len(ii_tickets)} билетов)</button>
  </div>

  <div class="exam-panel active" id="exam-gmu">
    {gmu_html}
  </div>
  <div class="exam-panel" id="exam-ii">
    {ii_html}
  </div>
</div>

<script>
const INDEX = {index_json};
let currentFilter = 'all';
let currentExam = 'gmu';

function showExam(exam, btn) {{
  currentExam = exam;
  document.querySelectorAll('.exam-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.exam-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('exam-' + exam).classList.add('active');
  applyFilters();
}}

function toggleSection(id) {{
  const body = document.getElementById('sec_' + id);
  const arr = document.getElementById('arr_' + id);
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arr.style.transform = open ? '' : 'rotate(90deg)';
}}

function toggleTicket(id) {{
  const body = document.getElementById('tb_' + id);
  const arr = document.getElementById('tarr_' + id);
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arr.style.transform = open ? '' : 'rotate(90deg)';
}}

function setFilter(filter, btn) {{
  currentFilter = filter;
  document.querySelectorAll('.filterbar .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  const panel = document.getElementById('exam-' + currentExam);
  let visible = 0;
  panel.querySelectorAll('.ticket').forEach(el => {{
    const title = el.dataset.title || '';
    const score = parseInt(el.dataset.score || '0');
    const review = el.dataset.review === '1';
    const matchSearch = !q || title.includes(q);
    const matchFilter =
      currentFilter === 'all' ? true :
      currentFilter === 'clean' ? score === 0 :
      currentFilter === 'damaged' ? score > 0 :
      currentFilter === 'review' ? review : true;
    if (matchSearch && matchFilter) {{
      el.classList.remove('filtered-out');
      visible++;
    }} else {{
      el.classList.add('filtered-out');
    }}
  }});
  // Hide empty sections
  panel.querySelectorAll('.section-group').forEach(sg => {{
    const anyVisible = sg.querySelectorAll('.ticket:not(.filtered-out)').length > 0;
    sg.classList.toggle('all-hidden', !anyVisible);
  }});
  document.getElementById('filter-count').textContent = visible + ' из ' + INDEX.length;
}}

function expandAll() {{
  const panel = document.getElementById('exam-' + currentExam);
  panel.querySelectorAll('.section-body').forEach(el => {{
    el.style.display = 'block';
  }});
  panel.querySelectorAll('.section-arrow').forEach(a => a.style.transform = 'rotate(90deg)');
}}

function collapseAll() {{
  const panel = document.getElementById('exam-' + currentExam);
  panel.querySelectorAll('.section-body').forEach(el => el.style.display = 'none');
  panel.querySelectorAll('.ticket-body').forEach(el => el.style.display = 'none');
  panel.querySelectorAll('.section-arrow, .ticket-arrow').forEach(a => a.style.transform = '');
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("Загрузка данных из базы...")
    tickets, exams = load_data()
    print(f"Загружено: {len(tickets)} билетов")
    print("Генерация HTML...")
    html_content = build_html(tickets, exams)
    OUT.write_text(html_content, encoding="utf-8")
    size_kb = OUT.stat().st_size // 1024
    clean = sum(1 for t in tickets if t["score"] == 0)
    flagged = sum(1 for t in tickets if t["needs_review"])
    print(f"Готово: {OUT} ({size_kb} КБ)")
    print(f"Чистых билетов: {clean}/{len(tickets)}")
    print(f"ТРЕБУЕТ ПРОВЕРКИ: {flagged}")
