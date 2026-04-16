# UI/UX Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove 6 misleading/redundant UI elements and fix 5 broken UX flows in the PySide6 desktop app.

**Architecture:** All changes are in the `ui/` layer. No domain or infrastructure changes. The TopBar is stripped down to a single settings gear button. Inline search fields replace the removed global search. Settings gets dirty-tracking and path validation. Defense view gets loading states. Training workspaces get consistent theme refresh.

**Tech Stack:** Python 3.12+, PySide6, pytest

**Spec:** `docs/superpowers/specs/2026-04-16-ui-ux-cleanup-design.md`

---

### Task 1: Strip TopBar down to settings gear only (A1 + A2 + A3)

Remove global search, Ollama button, and theme toggle from TopBar. Remove all wiring in MainWindow.

**Files:**
- Modify: `ui/components/topbar.py` (full rewrite — file is 89 lines)
- Modify: `ui/main_window.py:114-119` (topbar wiring), `195-215` (switch_view/forward_search), `485-498` (toggle_theme), `539-556` (persist_settings references)
- Modify: `ui/views/settings_view.py:1395-1396` (remove `set_search_text` stub)
- Modify: `ui/views/statistics_view.py:153-154` (remove `set_search_text` stub)
- Modify: `ui/views/import_view.py:531-532` (remove `set_search_text` stub)
- Test: `tests/test_ui_handlers.py` (existing tests must still pass)

- [ ] **Step 1: Rewrite `ui/components/topbar.py`**

Replace the entire TopBar with a minimal version that only has the settings gear button:

```python
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QLabel, QPushButton, QWidget

from ui.theme import current_colors


class TopBar(QWidget):
    settings_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.layout_root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.layout_root.setContentsMargins(28, 16, 28, 16)
        self.layout_root.setSpacing(12)

        self.layout_root.addStretch(1)

        self.settings_button = QPushButton("⚙  Настройки")
        self.settings_button.setObjectName("topbar-settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setProperty("variant", "toolbar")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        self.layout_root.addWidget(self.settings_button)

    def refresh_theme(self) -> None:
        pass
```

- [ ] **Step 2: Update MainWindow topbar wiring**

In `ui/main_window.py`, remove all references to deleted signals:

Remove these lines (around line 115-118):
```python
# DELETE these lines:
self.topbar.settings_clicked.connect(lambda: self.open_settings_section("general"))
self.topbar.ollama_clicked.connect(lambda: self.open_settings_section("ollama"))
self.topbar.theme_clicked.connect(self.toggle_theme)
self.topbar.search_changed.connect(self.forward_search)
```

Replace with:
```python
self.topbar.settings_clicked.connect(lambda: self.open_settings_section("general"))
```

- [ ] **Step 3: Remove `forward_search` method from MainWindow**

Delete the `forward_search` method (around lines 212-215):
```python
# DELETE this entire method:
def forward_search(self, text: str) -> None:
    current = self.views.get(self.current_key)
    if hasattr(current, "set_search_text"):
        current.set_search_text(text)
```

- [ ] **Step 4: Remove `forward_search` call from `switch_view`**

In `switch_view` method (around line 205), delete:
```python
# DELETE this line:
self.forward_search(self.topbar.search_input.text())
```

- [ ] **Step 5: Remove `toggle_theme` method from MainWindow**

Delete the `toggle_theme` method (around lines 485-498):
```python
# DELETE this entire method:
def toggle_theme(self) -> None:
    self.palette_name = "dark" if self.palette_name == "light" else "light"
    settings = self.facade.settings
    settings.theme_name = self.palette_name
    self.palette_colors = set_app_theme(
        self.app,
        self.palette_name,
        settings.font_preset,
        settings.font_size,
    )
    self.topbar.set_theme_label(self.palette_name)
    self._refresh_theme_widgets()
    self.refresh_all_views()
    self.facade.save_settings(settings)
```

- [ ] **Step 6: Remove `topbar.set_theme_label` calls from MainWindow**

In `persist_settings` method (around line 551), delete:
```python
# DELETE this line:
self.topbar.set_theme_label(self.palette_name)
```

Also delete the same call in `__init__` (around line 180):
```python
# DELETE this line:
self.topbar.set_theme_label(self.palette_name)
```

- [ ] **Step 7: Remove `set_search_text` stubs from three views**

In `ui/views/settings_view.py`, delete lines 1395-1396:
```python
# DELETE:
def set_search_text(self, text: str) -> None:
    return
```

In `ui/views/statistics_view.py`, delete lines 153-154:
```python
# DELETE:
def set_search_text(self, text: str) -> None:
    return
```

In `ui/views/import_view.py`, delete lines 531-532:
```python
# DELETE:
def set_search_text(self, text: str) -> None:
    return
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: all existing tests pass. UI tests that reference `topbar.search_input` or `topbar.ollama_button` or `topbar.theme_button` will fail — fix them by removing those references.

- [ ] **Step 9: Commit**

```bash
git add ui/components/topbar.py ui/main_window.py ui/views/settings_view.py ui/views/statistics_view.py ui/views/import_view.py
git commit -m "refactor(ui): strip TopBar to settings gear only

Remove global search (broken on 5/9 views), Ollama button (redundant
with sidebar+settings nav), and theme toggle (available in Settings).
Remove set_search_text stubs from settings/statistics/import views."
```

---

### Task 2: Add inline search to content views (A1b)

Add a `QLineEdit` search field to the header of library, subjects, sections, and tickets views — wired to their existing `set_search_text` methods.

**Files:**
- Modify: `ui/views/library_view.py:40-47` (header area)
- Modify: `ui/views/subjects_view.py:20-24` (header area)
- Modify: `ui/views/sections_view.py:20-29` (header area)
- Modify: `ui/views/tickets_view.py` (header area)

- [ ] **Step 1: Add search field to `library_view.py`**

In `LibraryView.__init__`, after the existing header layout with title and import button, add a search field. Find the header block (around line 40-47):

```python
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)

        title = QLabel("Библиотека документов")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)
```

Add after `header.addStretch(1)` and before the import button:

```python
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
        header.addWidget(self.search_input)
```

Add `QLineEdit` to the imports at top of file:
```python
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
```

- [ ] **Step 2: Add search field to `subjects_view.py`**

In `SubjectsView.__init__`, after the title label (around line 24), add:

```python
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        title = QLabel("Предметы")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
        header.addWidget(self.search_input)
        layout.addLayout(header)
```

This replaces the existing standalone title label. Remove the old:
```python
# DELETE these two lines:
        title = QLabel("Предметы")
        title.setProperty("role", "hero")
        layout.addWidget(title)
```

Add `QLineEdit` to the imports:
```python
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QVBoxLayout, QWidget
```

- [ ] **Step 3: Add search field to `sections_view.py`**

In `SectionsView.__init__`, the header already has an `QHBoxLayout` with title and combo (around line 20-29). Add the search field between the stretch and the combo. Change:

```python
        header = QHBoxLayout()
        title = QLabel("Разделы")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)
        self.combo = QComboBox()
```

To:

```python
        header = QHBoxLayout()
        title = QLabel("Разделы")
        title.setProperty("role", "hero")
        header.addWidget(title)
        header.addStretch(1)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
        header.addWidget(self.search_input)
        self.combo = QComboBox()
```

Add `QLineEdit` to the imports:
```python
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget
```

- [ ] **Step 4: Add search field to `tickets_view.py`**

In `TicketsView.__init__`, find the header section and add the search field in the same pattern. Add `QLineEdit` to imports and add:

```python
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setProperty("role", "search-plain")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.set_search_text)
```

Add it to the view's header layout, before the stretch or at the end of the header row.

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/views/library_view.py ui/views/subjects_view.py ui/views/sections_view.py ui/views/tickets_view.py
git commit -m "feat(ui): add inline search fields to content views

Replace removed global TopBar search with per-view search inputs in
library, subjects, sections, and tickets views. Each field is wired
to the existing set_search_text method."
```

---

### Task 3: Add local filter to Training queue (A1a)

Embed a filter input in the training queue card and fix selection preservation.

**Files:**
- Modify: `ui/views/training_view.py:94-108` (queue card construction), `244-254` (set_search_text)

- [ ] **Step 1: Add filter QLineEdit to queue card**

In `TrainingView.__init__`, after `self.queue_title` is added to `queue_layout` (around line 102), add:

```python
        self.queue_filter = QLineEdit()
        self.queue_filter.setPlaceholderText("Фильтр по билетам...")
        self.queue_filter.setProperty("role", "search-plain")
        self.queue_filter.setFixedHeight(36)
        self.queue_filter.textChanged.connect(self._apply_queue_filter)
        queue_layout.addWidget(self.queue_filter)
```

Add `QLineEdit` to the imports at top of file:
```python
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QHBoxLayout, QLineEdit, QStackedWidget, QVBoxLayout, QWidget
```

- [ ] **Step 2: Replace `set_search_text` with `_apply_queue_filter`**

Delete the existing `set_search_text` method (around lines 244-254) and replace with:

```python
    def _apply_queue_filter(self, text: str) -> None:
        query = text.strip().lower()
        saved_selection = self.selected_ticket_id
        if not query:
            self._rebuild_queue()
        else:
            filtered = [item for item in self.snapshot.queue_items if query in item.ticket_title.lower()]
            current = self.snapshot
            self.snapshot = TrainingSnapshot(queue_items=filtered, tickets=current.tickets)
            self._rebuild_queue()
            self.snapshot = current
        if saved_selection in self.queue_buttons:
            self.queue_buttons[saved_selection].set_selected(True)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ui/views/training_view.py
git commit -m "feat(ui): add local filter to training queue card

Embed a search field directly in the adaptive queue card. Replaces
the old global search routing. Preserves ticket selection on filter."
```

---

### Task 4: Remove fake stats elements (A4 + A5)

Remove the non-functional "Все ->" label and "Все предметы" combo from statistics panel.

**Files:**
- Modify: `ui/components/stats_panel.py:51-54` (subject_combo), `106-108` (more label)

- [ ] **Step 1: Remove subject combo from header**

In `ui/components/stats_panel.py`, in `__init__`, remove the subject combo (around lines 51-54):

```python
# DELETE these lines:
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(["Все предметы"])
        self.subject_combo.setMaximumWidth(132 if compact else 152)
        self.header_layout.addWidget(self.subject_combo)
```

Remove `QComboBox` from imports if no longer used:
```python
from PySide6.QtWidgets import QBoxLayout, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
```

- [ ] **Step 2: Remove "Все ->" label from recent sessions header**

In `__init__`, remove the "Все →" label (around lines 106-108):

```python
# DELETE these lines:
        more = QLabel("Все →")
        more.setStyleSheet(f"color: {current_colors()['primary']}; font-size: 13px; font-weight: 600;")
        recent_header.addWidget(more)
```

- [ ] **Step 3: Remove responsive combo logic**

In `resizeEvent`, delete the combo width adjustment (around lines 155-161):

```python
# DELETE this block inside resizeEvent:
        if self.compact:
            narrow = self.width() < 300
            direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
            if self.header_layout.direction() != direction:
                self.header_layout.setDirection(direction)
                self.subject_combo.setMaximumWidth(16777215 if narrow else 132)
```

Replace with a pass or remove the override entirely if nothing else remains:
```python
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/components/stats_panel.py
git commit -m "fix(ui): remove fake filter and link from statistics panel

Remove 'Все предметы' combo (one item, no logic) and 'Все →' label
(looks clickable but is plain text). Both misled users."
```

---

### Task 5: Replace local pre-validation messages (A6)

Replace confusing dual-verdict messages in Cloze, Matching, and Plan workspaces.

**Files:**
- Modify: `ui/components/training_workspaces.py:491`, `562`, `680`

- [ ] **Step 1: Fix ClozeWorkspace._submit**

In `ui/components/training_workspaces.py`, in `ClozeWorkspace._submit` (around line 491), change:

```python
        self.result_body.setText(f"Локально заполнено правильно: {exact} из {len(self.prompts)}.")
```

To:

```python
        self.result_body.setText("Проверяем ответ...")
```

- [ ] **Step 2: Fix MatchingWorkspace._submit**

In `MatchingWorkspace._submit` (around line 562), change:

```python
        self.result_body.setText(f"Локально совпало пар: {correct} из {len(self.controls)}.")
```

To:

```python
        self.result_body.setText("Проверяем ответ...")
```

- [ ] **Step 3: Fix PlanWorkspace._submit**

In `PlanWorkspace._submit` (around line 680), change:

```python
        self.result_body.setText(f"Локально на месте: {exact} из {len(self.correct_order)} тезисов.")
```

To:

```python
        self.result_body.setText("Проверяем ответ...")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/components/training_workspaces.py
git commit -m "fix(ui): remove confusing local pre-validation in training modes

Replace 'Локально совпало X из Y' messages with 'Проверяем ответ...'
in Cloze, Matching, and Plan workspaces. Users now see one verdict
(from LLM evaluation) instead of two potentially conflicting ones."
```

---

### Task 6: Fix theme refresh for training workspaces (B5)

Ensure all 7 workspaces re-apply styles on theme change.

**Files:**
- Modify: `ui/components/training_workspaces.py` (refresh_theme methods in each workspace)

- [ ] **Step 1: Audit current refresh_theme implementations**

Current state of `refresh_theme()` overrides:
- `ReadingWorkspace.refresh_theme` — calls `super()` + updates `answer_box` style. Does NOT re-call `_set_ticket`. **Needs fix.**
- `ActiveRecallWorkspace.refresh_theme` — calls `super()` + updates `prompt_box` and `answer_box`. Does NOT re-call `_set_ticket`. **Needs fix.**
- `ClozeWorkspace` — no `refresh_theme` override. **Needs fix** — cloze grid labels have inline styles from `_set_ticket`.
- `MatchingWorkspace` — no `refresh_theme` override. **Needs fix** — term labels have inline styles.
- `PlanWorkspace.refresh_theme` — calls `super()` + `_render_blocks()`. **OK** (rebuilds styled content).
- `MiniExamWorkspace.refresh_theme` — calls `super()` + updates `timer_badge`. Does NOT re-call `_set_ticket`. **Needs fix.**
- `StateExamFullWorkspace.refresh_theme` — calls `super()` + `_set_ticket(self.current_ticket)`. **OK.**

- [ ] **Step 2: Fix ReadingWorkspace.refresh_theme**

Change the existing `refresh_theme` in `ReadingWorkspace` (around line 309):

```python
    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.answer_box.setStyleSheet(
            f"QFrame#ReadingAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 3: Fix ActiveRecallWorkspace.refresh_theme**

Change the existing `refresh_theme` in `ActiveRecallWorkspace` (around line 419):

```python
    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.prompt_box.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {current_colors()['text']};")
        self.answer_box.setStyleSheet(
            f"QFrame#RecallAnswerBox {{ background: {current_colors()['card_soft']}; border: 1px solid {current_colors()['border']}; border-radius: 16px; }}"
        )
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 4: Add refresh_theme to ClozeWorkspace**

After `_set_ticket` in `ClozeWorkspace` (around line 515), add:

```python
    def refresh_theme(self) -> None:
        super().refresh_theme()
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 5: Add refresh_theme to MatchingWorkspace**

After `_set_ticket` in `MatchingWorkspace` (around line 597), add:

```python
    def refresh_theme(self) -> None:
        super().refresh_theme()
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 6: Fix MiniExamWorkspace.refresh_theme**

Change the existing `refresh_theme` in `MiniExamWorkspace` (around line 801):

```python
    def refresh_theme(self) -> None:
        super().refresh_theme()
        self.timer_badge.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {current_colors()['danger']};")
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add ui/components/training_workspaces.py
git commit -m "fix(ui): ensure all training workspaces refresh on theme change

Add refresh_theme overrides to ClozeWorkspace and MatchingWorkspace.
Fix ReadingWorkspace, ActiveRecallWorkspace, and MiniExamWorkspace
to re-call _set_ticket so all inline styles update with new colors."
```

---

### Task 7: Add error handling for background threads (B1)

Connect `failed` signals to error handlers on import, defense, and eval threads.

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: Verify existing error handling**

Check what already exists. Looking at the code:
- `_import_thread`: already has `failed.connect(self._fail_import)` at line 256. **Already handled.**
- `_defense_thread`: already has `failed.connect(self._fail_defense_import)` at line 353. **Already handled.**
- `_defense_eval_thread`: already has `failed.connect(self._fail_defense_evaluation)` at line 394. **Already handled.**
- `_diagnostics_thread`: already has `failed.connect(self._handle_diagnostics_failure)` at line 517. **Already handled.**
- `_update_thread`: already has `failed.connect(self._fail_update_check)` at line 706. **Already handled.**

All threads already have `failed` signal connections. The original audit was wrong about missing error handling — the connections exist. However, `_fail_import` (line 473) does reset UI state properly, and `_fail_defense_import` (line 373) shows result + message box.

**This task is a false alarm.** Verify and move on.

- [ ] **Step 2: Verify `_fail_import` resets UI state**

Read `_fail_import` (line 473-478):
```python
    def _fail_import(self, error_text: str) -> None:
        if self._is_closing:
            return
        self.views["import"].set_last_result(ImportExecutionResult(ok=False, error=error_text))
        self.switch_view("import")
        QMessageBox.critical(self, "Импорт", error_text)
```

`set_last_result` internally calls `self._import_pending = False` and `self._set_actions_enabled(True)`. **This is correct.**

- [ ] **Step 3: Commit (skip if no changes)**

No code changes needed. All threads already have error handlers. Move on.

---

### Task 8: Add unsaved changes warning to Settings (B2)

Track dirty state in settings and prompt before navigating away.

**Files:**
- Modify: `ui/views/settings_view.py` (add dirty tracking)
- Modify: `ui/main_window.py:195-206` (switch_view)

- [ ] **Step 1: Add dirty flag and tracking to SettingsView**

In `ui/views/settings_view.py`, add `_dirty` flag in `__init__` (after line 100, near `self._last_diagnostics`):

```python
        self._dirty = False
```

Add a method to mark dirty:

```python
    def _mark_dirty(self, *_args) -> None:
        self._dirty = True
```

Add a public accessor:

```python
    def has_unsaved_changes(self) -> bool:
        return self._dirty
```

- [ ] **Step 2: Connect form field signals to dirty tracker**

At the end of `__init__`, after `self.reset_form()` (around line 175), add:

```python
        self._connect_dirty_tracking()
```

Add the method:

```python
    def _connect_dirty_tracking(self) -> None:
        self.theme_combo.currentIndexChanged.connect(self._mark_dirty)
        self.startup_view_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_preset_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_size_stepper.value_changed.connect(self._mark_dirty)
        self.auto_check_card.toggle.toggled.connect(self._mark_dirty)
        self.update_check_card.toggle.toggled.connect(self._mark_dirty)
        self.dlc_card.toggle.toggled.connect(self._mark_dirty)
        self.default_import_dir_input.textChanged.connect(self._mark_dirty)
        self.import_format_combo.currentIndexChanged.connect(self._mark_dirty)
        self.import_llm_card.toggle.toggled.connect(self._mark_dirty)
        self.training_mode_combo.currentIndexChanged.connect(self._mark_dirty)
        self.review_mode_combo.currentIndexChanged.connect(self._mark_dirty)
        self.queue_size_combo.currentIndexChanged.connect(self._mark_dirty)
        self.url_input.textChanged.connect(self._mark_dirty)
        self.model_combo.currentTextChanged.connect(self._mark_dirty)
        self.models_path_input.textChanged.connect(self._mark_dirty)
        self.timeout_stepper.value_changed.connect(self._mark_dirty)
        self.rewrite_card.toggle.toggled.connect(self._mark_dirty)
        self.followups_card.toggle.toggled.connect(self._mark_dirty)
        self.fallback_card.toggle.toggled.connect(self._mark_dirty)
```

- [ ] **Step 3: Reset dirty flag on save and reset**

In `save_settings` method (around line 1108), add at the very end (after the QMessageBox):

```python
        self._dirty = False
```

In `reset_form` method (around line 1135), add at the very end:

```python
        self._dirty = False
```

- [ ] **Step 4: Add unsaved changes check to MainWindow.switch_view**

In `ui/main_window.py`, modify `switch_view` (around line 195):

```python
    def switch_view(self, key: str) -> None:
        if key not in self.views:
            return
        if self.current_key == "settings" and key != "settings":
            settings_view = self.views["settings"]
            if settings_view.has_unsaved_changes():
                answer = QMessageBox.question(
                    self,
                    "Несохранённые изменения",
                    "В настройках есть несохранённые изменения. Сохранить перед выходом?",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save,
                )
                if answer == QMessageBox.StandardButton.Save:
                    settings_view.save_settings()
                elif answer == QMessageBox.StandardButton.Cancel:
                    return
                else:
                    settings_view.reset_form()
        if key == "defense":
            self.refresh_defense_view(self.views["defense"].current_project_id or None)
        self.current_key = key
        self.sidebar.set_current(key)
        self.stack.setCurrentWidget(self.stack_pages[key])
        if key in {"tickets", "training"}:
            QTimer.singleShot(0, self._refresh_heavy_views)
        self._apply_interface_text_overrides()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/views/settings_view.py ui/main_window.py
git commit -m "feat(ui): warn about unsaved changes in settings

Track dirty state across all settings form fields. Prompt user with
Save/Discard/Cancel when navigating away from settings with changes."
```

---

### Task 9: Add path validation in Settings before save (B3)

Validate directory paths before accepting settings save.

**Files:**
- Modify: `ui/views/settings_view.py:1108-1133` (save_settings method)

- [ ] **Step 1: Add validation to `save_settings`**

In `ui/views/settings_view.py`, at the beginning of `save_settings` (line 1108), add validation before the `OllamaSettings(...)` constructor:

```python
    def save_settings(self) -> None:
        models_path_text = self.models_path_input.text().strip()
        if models_path_text and not Path(models_path_text).is_dir():
            QMessageBox.warning(
                self,
                "Настройки",
                f"Папка с моделями не найдена:\n{models_path_text}\n\nУкажите существующую папку или оставьте поле пустым.",
            )
            return

        import_dir_text = self.default_import_dir_input.text().strip()
        if import_dir_text and not Path(import_dir_text).is_dir():
            QMessageBox.warning(
                self,
                "Настройки",
                f"Папка импорта не найдена:\n{import_dir_text}\n\nУкажите существующую папку или оставьте поле пустым.",
            )
            return

        self.settings = OllamaSettings(
```

The rest of the method stays the same. The `self._dirty = False` line added in Task 8 remains at the end.

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/views/settings_view.py
git commit -m "fix(ui): validate directory paths before saving settings

Check that models_path and default_import_dir exist before accepting
save. Show warning dialog with the invalid path if validation fails."
```

---

### Task 10: Add loading states to Defense action buttons (B4)

Disable buttons and show "busy" text during async operations.

**Files:**
- Modify: `ui/views/defense_view.py`

- [ ] **Step 1: Add `_set_create_busy` method**

In `ui/views/defense_view.py`, add a method near `_emit_create_project` (around line 859):

```python
    def _set_create_busy(self, busy: bool) -> None:
        self.create_button.setEnabled(not busy)
        self.create_button.setText("Создание..." if busy else "Создать проект защиты")
```

- [ ] **Step 2: Call busy state from `_emit_create_project`**

Modify `_emit_create_project` (around line 859):

```python
    def _emit_create_project(self) -> None:
        self._set_create_busy(True)
        payload = {
            "title": self.project_title_input.text().strip(),
            "degree": "магистр",
```

(rest stays the same)

- [ ] **Step 3: Add `_set_import_busy` method**

```python
    def _set_import_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.import_button.setText("Импорт..." if busy else "Импортировать материалы")
```

- [ ] **Step 4: Call busy state from `_emit_import`**

Modify `_emit_import` (around line 871):

```python
    def _emit_import(self) -> None:
        if self.current_project_id:
            self._set_import_busy(True)
            self.import_requested.emit(self.current_project_id)
```

- [ ] **Step 5: Reset busy state on processing complete/fail**

In `show_processing_result` (which is called on success/failure), add at the beginning:

```python
    def show_processing_result(self, result) -> None:
        self._processing = False
        self._set_import_busy(False)
```

(rest stays the same)

- [ ] **Step 6: Reset create busy in MainWindow after create_defense_project**

In `ui/main_window.py`, modify `create_defense_project` (around line 317):

```python
    def create_defense_project(self, payload: dict[str, str]) -> None:
        if not payload.get("title"):
            self.views["defense"]._set_create_busy(False)
            QMessageBox.warning(self, "Платный модуль", "Укажите тему работы для проекта защиты.")
            return
        try:
            project = self.facade.create_defense_project(payload)
        except Exception as exc:  # noqa: BLE001
            self.views["defense"]._set_create_busy(False)
            QMessageBox.critical(self, "Платный модуль", str(exc))
            return
        self.views["defense"]._set_create_busy(False)
        self.refresh_defense_view(project.project_id)
        self.switch_view("defense")
```

- [ ] **Step 7: Disable gap/repair buttons temporarily on click**

In `_emit_gap_status` (around line 957), add:

```python
    def _emit_gap_status(self, status: str) -> None:
        finding_id = str(self.gap_pick_combo.currentData() or "")
        if self.current_project_id and finding_id:
            self._set_gap_buttons_enabled(False)
            self.gap_status_requested.emit(self.current_project_id, finding_id, status)
```

In `_emit_repair_status` (around line 962), add:

```python
    def _emit_repair_status(self, status: str) -> None:
        task_id = str(self.repair_pick_combo.currentData() or "")
        if self.current_project_id and task_id:
            self._set_repair_buttons_enabled(False)
            self.repair_task_status_requested.emit(self.current_project_id, task_id, status)
```

The `_set_gap_buttons_enabled` and `_set_repair_buttons_enabled` methods likely already exist (the codebase references them). If not, add:

```python
    def _set_gap_buttons_enabled(self, enabled: bool) -> None:
        self.gap_accept_button.setEnabled(enabled)
        self.gap_resolve_button.setEnabled(enabled)
        self.gap_ignore_button.setEnabled(enabled)

    def _set_repair_buttons_enabled(self, enabled: bool) -> None:
        self.repair_done_button.setEnabled(enabled)
        self.repair_dismiss_button.setEnabled(enabled)
```

Buttons get re-enabled when `refresh_defense_view` is called (which triggers `set_snapshot` → `_render_active_project` → re-renders gap/repair panels with fresh data and re-enabled buttons).

- [ ] **Step 8: Run tests**

Run: `pytest tests/ -q --timeout=30 2>&1 | head -40`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add ui/views/defense_view.py ui/main_window.py
git commit -m "feat(ui): add loading states to defense action buttons

Disable and show busy text on Create/Import buttons during async
operations. Disable gap/repair action buttons during status updates.
All buttons re-enable when the operation completes or fails."
```

---

### Task 11: Final verification

Run full test suite and verify the app launches correctly.

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -q --timeout=60 2>&1 | tail -20`

Expected: all tests PASS

- [ ] **Step 2: Smoke-test the app launches**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "import sys; from PySide6.QtWidgets import QApplication; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('MainWindow import OK')"`

Expected: `MainWindow import OK`

- [ ] **Step 3: Final commit (if any fixups needed)**

If any test failures were discovered and fixed, commit the fixes.
