# Knowledge Map & Exam Readiness

**Date:** 2026-04-16
**Scope:** Interactive knowledge graph + exam readiness score + visual polish
**Affected layers:** `application/`, `ui/components/`, `ui/views/`, `ui/main_window.py`

---

## Problem

Students see a flat list of tickets with no sense of how topics connect or how ready they are overall. Cross-ticket concept links exist in the database but are invisible to the user. There's no single "am I ready?" metric.

## Strategy

Two features delivered as one package:
1. **Knowledge Map** — interactive force-directed graph showing ticket relationships and mastery
2. **Readiness Score** — aggregate readiness percentage shown on library, map, and sidebar

Visual polish is a first-class requirement: animated layout, glow effects, gradients, smooth transitions. The new screens should feel premium and set the bar for future UI work.

---

## Part 1: Readiness Score

### Data Model

New dataclass in `application/ui_data.py`:

```python
@dataclass(slots=True)
class ReadinessScore:
    percent: int                    # 0-100
    tickets_total: int
    tickets_practiced: int
    weakest_area: str               # Title of weakest ticket or ""
```

### Calculation

New file `application/readiness.py` with `ReadinessService`:

```python
class ReadinessService:
    def calculate(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
    ) -> ReadinessScore:
```

**Formula:**
```
practiced_tickets = [t for t in tickets if t.ticket_id in mastery and mastery[t.ticket_id].confidence_score > 0]
average_mastery = mean(confidence_score for practiced tickets), or 0 if none
coverage = len(practiced_tickets) / len(tickets), or 0 if no tickets
readiness = average_mastery × coverage × 100
```

Coverage penalty ensures you can't be "ready" by mastering 3 of 30 tickets.

`weakest_area` = title of the ticket with the lowest non-zero confidence_score.

### Where Displayed

1. **Library view** — `DonutChart` with readiness percent in the right column stats area
2. **Knowledge Map view** — readiness in header bar
3. **Sidebar** — small text label below Ollama status: "Готовность: 67%"

### Facade Integration

In `AppFacade`, add `load_readiness_score()` that calls `ReadinessService.calculate()` with already-loaded tickets and mastery data. Called from `_refresh_lightweight_views`.

---

## Part 2: Knowledge Map — Interactive Graph

### New View

`KnowledgeMapView` — 10th screen in the app, added to sidebar between "Статистика" and "Подготовка к защите".

**Sidebar order:**
```
Библиотека | Предметы | Разделы | Билеты | Импорт документов
Тренировка | Статистика | Карта знаний | Подготовка к защите | Настройки
```

### Layout

Two-panel layout:
- **Left (70%):** `KnowledgeGraphWidget` — the interactive graph
- **Right (30%):** Detail panel — shows selected ticket info + "Тренировать" button

### Graph Data

**Nodes** = tickets from `load_ticket_maps()`:
- Position: computed by force-directed layout
- Color: mastery-based (see Visual Polish section)
- Size: proportional to `len(ticket.atoms)`, clamped to min 24px / max 56px diameter
- Label: 2-character abbreviation of ticket title (first letters of first 2 words)
- Tooltip: full title + mastery %

**Edges** = cross-ticket concept links from `ticket.cross_links_to_other_tickets`:
- Connect ticket_id to each related_ticket_id
- Label (on hover): concept_label
- Weight/thickness: number of shared concepts between the pair

### Force-Directed Layout

Fruchterman-Reingold algorithm, implemented in ~60 lines:

```
For each iteration (100 iterations):
    For each pair of nodes:
        repulsive_force = k² / distance  (push apart)
    For each edge:
        attractive_force = distance² / k  (pull together)
    Apply forces with cooling factor (decreasing step size)
```

`k = sqrt(area / num_nodes)` where area is the scene bounding rect.

Layout runs on view initialization. Animated (see Visual Polish).

### Interaction

- **Zoom:** mouse wheel, smooth animated via `QPropertyAnimation` on view transform
- **Pan:** click-drag on empty space (QGraphicsView built-in with `ScrollHandDrag`)
- **Drag nodes:** click-drag on a node repositions it, then re-runs partial layout for neighbors
- **Hover node:** tooltip with title + mastery %. Edges to/from this node brighten and thicken.
- **Click node:** select it, highlight in detail panel. Panel shows:
  - Ticket title
  - Mastery confidence_score as percentage
  - Atom count
  - Connected concepts (labels of edges)
  - "Тренировать" button → navigates to TrainingView with this ticket selected
- **Click empty space:** deselect

### Files

| File | Role |
|------|------|
| `application/readiness.py` | NEW: `ReadinessService` |
| `application/ui_data.py` | Add `ReadinessScore` dataclass |
| `application/facade.py` | Add `load_readiness_score()` method |
| `ui/components/knowledge_graph.py` | NEW: `KnowledgeGraphWidget`, `TicketNode`, `ConceptEdge`, force layout |
| `ui/views/knowledge_map_view.py` | NEW: `KnowledgeMapView` with graph + detail panel |
| `ui/components/sidebar.py` | Add "Карта знаний" nav item + readiness label |
| `ui/views/library_view.py` | Add readiness DonutChart |
| `ui/main_window.py` | Register KnowledgeMapView, wire navigation, pass data |

---

## Part 3: Visual Polish

All visual effects use built-in Qt classes. No external dependencies.

### Animated Force Layout

Layout doesn't compute instantly — it animates over ~1.5 seconds:
- `QTimer` fires every 16ms (~60fps)
- Each tick runs one iteration of the force algorithm
- Nodes move smoothly to their computed positions
- Cooling factor reduces movement each tick until stable
- After stabilization, timer stops

### Node Glow Effects

Each `TicketNode` gets a `QGraphicsDropShadowEffect`:
- Color matches mastery tier: green glow for covered, yellow for partial, red for weak, no glow for untouched
- Blur radius: 16px
- Offset: (0, 0) — centered glow, not a directional shadow

### Gradient Node Fill

Nodes use `QRadialGradient` instead of flat `QBrush`:
- Center: lighter version of mastery color
- Edge: darker version
- Creates a 3D sphere-like appearance

### Mastery Color Scale

| Mastery % | Node color | Glow color |
|-----------|-----------|------------|
| 0 (untouched) | `#B0BEC5` (gray) | none |
| 1-30% | `#EF5350` (red) | `#EF5350` |
| 31-60% | `#FFA726` (orange) | `#FFA726` |
| 61-80% | `#FFEE58` (yellow) | `#FFEE58` |
| 81-100% | `#66BB6A` (green) | `#66BB6A` |

Dark theme uses same hues but adjusted for dark background (slightly brighter, more saturated).

### Edge Highlighting on Hover

When hovering a node:
- All edges connected to that node: opacity 1.0, width 2.5px, color matches node's mastery color
- All other edges: opacity 0.15
- Effect applied/removed on `hoverEnterEvent` / `hoverLeaveEvent`
- Transition is instant (no animation needed — hover is fast feedback)

### Smooth Zoom

Mouse wheel zoom uses `QPropertyAnimation` on a custom `_zoom_level` property:
- Each wheel step targets +/- 15% zoom
- Animation duration: 200ms, `QEasingCurve.OutCubic`
- Prevents jarring discrete zoom steps

### Animated Readiness DonutChart

The existing `DonutChart` widget in `ui/components/common.py` gets an enhancement:
- New method `animate_to(percent: int)` that uses `QPropertyAnimation` to animate from current value to target over 800ms
- Easing: `QEasingCurve.OutCubic`
- Arc color: gradient from red (0%) through yellow (50%) to green (100%) based on current animated value

This applies everywhere DonutChart is used (library stats, knowledge map header).

### Rounded Corners and Shadows

New UI elements (graph container, detail panel, readiness card) use:
- `border-radius: 18px` (matching existing CardFrame pattern)
- `QGraphicsDropShadowEffect` with blur 20, offset (0, 4), color from theme palette

---

## Scope Boundaries

**In scope:**
- ReadinessService + ReadinessScore DTO
- KnowledgeMapView with interactive graph
- Force-directed layout with animation
- Visual polish (glow, gradients, animated zoom, animated donut)
- Readiness display on library, map, sidebar
- Navigation from graph node to training
- Dark/light theme support

**Out of scope:**
- Filtering graph by subject/section (future enhancement)
- Saving graph layout positions (recomputed each time)
- 3D graph or WebGL rendering
- Graph for defense DLC (separate integration)
- Readiness prediction over time (future analytics feature)

---

## Testing Strategy

- Unit tests for `ReadinessService.calculate()` — zero tickets, no practice, full mastery, partial coverage
- Unit tests for force layout — nodes don't overlap after stabilization, connected nodes closer than unconnected
- UI test for `KnowledgeMapView` — renders without crash, accepts data
- UI test for animated DonutChart — `animate_to()` starts animation
- Existing tests remain green — all changes additive
