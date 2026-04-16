# UI/UX Cleanup: Remove Redundancy, Fix Broken Flows

**Date:** 2026-04-16
**Scope:** UI layer cleanup — remove misleading/redundant UI elements, fix broken UX flows
**Affected layers:** `ui/components/`, `ui/views/`, `ui/main_window.py`

---

## Problem

The UI has ~15 UX issues ranging from misleading elements (search bar that silently does nothing on 5/9 screens) to missing error handling (threads that fail silently). The core architecture and domain model are mature, but the user-facing experience has holes that erode trust.

## Strategy

Two categories of work:
1. **Remove** — elements that create false expectations and are cheaper to cut than to fix properly
2. **Fix** — genuine missing behavior that needs to be added

---

## Part A: Removals

### A1. Remove global search from TopBar

**What:** Delete the search input (`QLineEdit`), search icon, and `search_shell` frame from `ui/components/topbar.py`. Remove the `search_changed` signal and all `forward_search` wiring in `ui/main_window.py`. Remove `set_search_text` stubs from views where they are no-ops: `settings_view.py`, `statistics_view.py`, `import_view.py`, `defense_view.py`.

**Keep:** `set_search_text` methods in `library_view.py`, `subjects_view.py`, `sections_view.py`, `tickets_view.py` — these have real filtering logic. They become dead code after removing the TopBar search, but keep the methods as they will be wired to inline filters (A1a/A1b).

**Why:** Search works on 4/9 views. On the other 5 it silently swallows input. A global search bar that only sometimes works is worse than no search bar.

#### A1a. Add local filter to Training queue

The training view already has `set_search_text` with real filtering logic. Convert it to a local filter input embedded directly in the queue card header.

**Implementation:**
- Add a `QLineEdit` with placeholder "Фильтр по билетам..." inside the `queue_card`, below the title
- Wire its `textChanged` signal to the existing `set_search_text` logic
- Fix the existing search logic so it preserves the current ticket selection when filtering

#### A1b. Add inline search to content views that had working search

The library, subjects, sections, and tickets views all have working `set_search_text` methods that are currently wired to the TopBar. After removing the TopBar search, wire each view's existing method to a local `QLineEdit` embedded in the view header.

**Implementation per view:**
- Add a `QLineEdit` with placeholder "Поиск..." in the view's header area (near the title)
- Wire `textChanged` to the existing `set_search_text` method
- Minimal styling: match existing field patterns in the codebase

This ensures no regression — users retain search where it already worked.

### A2. Remove "Настройки Ollama" button from TopBar

**What:** Delete `ollama_button` and `ollama_clicked` signal from `ui/components/topbar.py`. Remove `topbar.ollama_clicked.connect(...)` from `ui/main_window.py`.

**Why:** Redundant. Settings gear button already exists in TopBar. Sidebar has "Настройки" nav item. Settings view has its own nav panel with "Ollama" section. The Ollama status is also displayed in the sidebar status card. Three paths to the same destination.

### A3. Remove theme toggle button from TopBar

**What:** Delete `theme_button`, `theme_clicked` signal, and `set_theme_label` method from `ui/components/topbar.py`. Remove `topbar.theme_clicked.connect(self.toggle_theme)` and `topbar.set_theme_label(...)` calls from `ui/main_window.py`.

**Why:** Theme is already configurable in Settings > General. Having a quick-toggle is convenient but adds visual clutter to the TopBar. User confirmed removal.

**Post-removal TopBar:** Only the `⚙` settings gear button remains. TopBar becomes a clean, minimal header with just the branding/settings gear. This is actually cleaner and more focused.

### A4. Remove "Все ->" label from statistics panel

**What:** Delete the `more = QLabel("Все →")` element from `ui/components/stats_panel.py` (around line 106-108).

**Why:** Looks like a clickable link but is a plain label. No handler. Misleads users into thinking there's a "view all sessions" screen.

### A5. Remove "Все предметы" combo from statistics panel

**What:** Delete `self.subject_combo` from `ui/components/stats_panel.py` (around lines 51-54). Remove it from the header layout.

**Why:** Contains exactly one item. No filtering logic connected. Visual noise pretending to be a filter.

### A6. Remove local pre-validation messages from Cloze/Matching/Plan

**What:** In `ui/components/training_workspaces.py`, remove the `result_body.setText("Локально...")` lines from:
- `ClozeWorkspace._submit` (line ~491)
- `MatchingWorkspace._submit` (line ~562)
- `PlanWorkspace._submit` (line ~680)

Replace with a "Проверяем ответ..." message that gets overwritten when LLM evaluation arrives.

**Keep:** The local counting logic itself (exact match counting) — it's used to build the answer text sent to `evaluate_requested.emit()`. Just stop showing the intermediate result to the user.

**Why:** Two verdicts confuse users. If local says "2/3 correct" and LLM says "65%" — which is truth? One source of truth is always better.

---

## Part B: Fixes

### B1. Add error handling for background threads

**What:** In `ui/main_window.py`, connect `failed` signals on `_import_thread`, `_defense_thread`, and `_defense_eval_thread` to handlers that:
1. Show a `QMessageBox.warning()` with the error text
2. Reset the UI to a non-pending state (re-enable buttons, hide spinners)
3. Update relevant status labels with the error

**Current state:** `_diagnostics_thread` already has `failed.connect(self._fail_diagnostics)` — this pattern exists, just not applied to other threads.

**Files:** `ui/main_window.py`

### B2. Add "unsaved changes" warning to Settings

**What:** In `ui/views/settings_view.py`:
1. Add a `_dirty` flag, initially `False`
2. Connect all form field change signals (`currentIndexChanged`, `value_changed`, `textChanged`, etc.) to set `_dirty = True`
3. Override `reset_form` and `save_settings` to set `_dirty = False`
4. Expose a `has_unsaved_changes() -> bool` method
5. In `ui/main_window.py`, before `switch_view` navigates away from settings: check `has_unsaved_changes()`. If true, show `QMessageBox.question("Несохранённые изменения", "В настройках есть несохранённые изменения. Сохранить перед выходом?", Save | Discard | Cancel)`

**Files:** `ui/views/settings_view.py`, `ui/main_window.py`

### B3. Add path validation in Settings before save

**What:** In `ui/views/settings_view.py`, in the `save_settings` method:
1. Check if `models_path_input.text()` points to an existing directory
2. Check if `default_import_dir` (if set) points to an existing directory
3. If validation fails — show inline warning label below the field, don't save, don't close

**Files:** `ui/views/settings_view.py`

### B4. Add loading states to Defense action buttons

**What:** In `ui/views/defense_view.py`:
1. When "Создать проект" is clicked: disable button, change text to "Создание..."
2. When "Импортировать материалы" is clicked: disable button, change text to "Импорт..."
3. When any gap/repair status button is clicked: disable button temporarily
4. Re-enable all buttons when the operation completes (success or failure)

**Implementation:** Add `_set_actions_busy(busy: bool)` method that toggles enabled state and button text.

**Files:** `ui/views/defense_view.py`

### B5. Fix theme refresh for training workspaces

**What:** Ensure all training workspaces properly update all inline styles when `refresh_theme()` is called.

Current state: `TrainingWorkspaceBase.refresh_theme()` updates header, empty_box, result_box. Subclass overrides update their specific elements. The issue is that some elements set styles in `__init__` or `_set_ticket` using `current_colors()` at construction time.

**Fix:** In each workspace's `refresh_theme()`, re-call `_set_ticket(self.current_ticket)` to rebuild all styled elements with current colors. Several workspaces already do this (e.g., `StateExamFullWorkspace.refresh_theme` calls `_set_ticket`). Verify all 7 workspaces follow this pattern and add it where missing.

**Files:** `ui/components/training_workspaces.py`

---

## Scope Boundaries

**In scope:**
- All removals (A1-A6) and fixes (B1-B5)
- Adjusting TopBar layout after removing 3 elements
- Training queue local filter (A1a)
- Inline search fields for content views (A1b)

**Out of scope (future work):**
- Statistics visualization improvements (charts, graphs beyond existing DonutChart)
- Defense DLC preview mode
- Import preview feature
- Mobile/web version

---

## Files Affected

| File | Changes |
|------|---------|
| `ui/components/topbar.py` | Remove search, ollama button, theme button. Only settings gear remains |
| `ui/main_window.py` | Remove `forward_search`, `toggle_theme` calls from topbar. Add thread error handlers. Add unsaved settings check on view switch |
| `ui/views/settings_view.py` | Add dirty flag, `has_unsaved_changes()`, path validation in `save_settings` |
| `ui/views/statistics_view.py` | Remove `set_search_text` stub |
| `ui/views/import_view.py` | Remove `set_search_text` stub |
| `ui/views/defense_view.py` | Add loading states to action buttons |
| `ui/views/library_view.py` | Add inline search field, wire to existing `set_search_text` |
| `ui/views/subjects_view.py` | Add inline search field, wire to existing `set_search_text` |
| `ui/views/sections_view.py` | Add inline search field, wire to existing `set_search_text` |
| `ui/views/tickets_view.py` | Add inline search field, wire to existing `set_search_text` |
| `ui/components/stats_panel.py` | Remove "Все →" label and subject combo |
| `ui/components/training_workspaces.py` | Remove local pre-validation messages, replace with "Проверяем...". Fix theme refresh |
| `ui/views/training_view.py` | Add local filter QLineEdit to queue card. Fix selection preservation on filter. Remove `set_search_text` (replace with local wiring) |
| `ui/components/sidebar.py` | No changes |

---

## Testing Strategy

- Run existing `pytest -q` suite — no domain/infra changes, tests should pass
- Run `scripts/ui_click_audit.py` to verify all navigation paths still work after TopBar simplification
- Manual verification: open each view, confirm no dead buttons or missing elements
- Verify theme toggle still works via Settings > General (the only remaining path)
