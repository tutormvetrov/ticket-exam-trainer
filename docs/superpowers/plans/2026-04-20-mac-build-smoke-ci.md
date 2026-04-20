# Mac Build Smoke CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually-triggered GitHub Actions workflow that verifies the macOS `.app` build succeeds on `macos-latest`, so releases can be pre-checked before tagging.

**Architecture:** One new workflow file `.github/workflows/mac-build-smoke.yml` with `workflow_dispatch` trigger only. Steps mirror the proven `build-macos` job in `release.yml` but skip artifact packaging/upload. Final check validates `dist/Tezis.app` exists.

**Tech Stack:** GitHub Actions, `macos-latest` runner, Python 3.12, `pip`, `flet pack` (via `scripts/build_mac_app.sh`), `pyinstaller`.

**Spec:** [`docs/superpowers/specs/2026-04-20-mac-build-smoke-ci-design.md`](../specs/2026-04-20-mac-build-smoke-ci-design.md)

---

## Task 1: Create the Mac build smoke workflow file

**Files:**
- Create: `.github/workflows/mac-build-smoke.yml`

- [ ] **Step 1: Re-read the proven macOS job in `release.yml`**

Run: inspect lines 67-108 of `.github/workflows/release.yml` — the `build-macos` job. We copy its build-related steps (checkout, setup-python, install deps, seed check, build) and drop the package+upload steps (lines 96-114).

- [ ] **Step 2: Create the new workflow file**

Create `.github/workflows/mac-build-smoke.yml` with this exact content:

```yaml
name: Mac build smoke

# Ручной smoke macOS-сборки перед тегом релиза. Собирает Tezis.app
# на macos-latest и падает, если что-то сломано. Артефакты не загружает —
# полная сборка + публикация живут в release.yml на тег v*.

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: mac-build-smoke-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    name: build Tezis.app (macos-latest)
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v6

      - name: Setup Python 3.12
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install Python deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Ensure bundled seed exists
        run: |
          if [ ! -f "data/state_exam_public_admin_demo.db" ]; then
            echo "Seed DB missing — build_mac_app.sh needs it as --add-data"
            exit 1
          fi

      - name: Build macOS app
        run: |
          chmod +x scripts/build_mac_app.sh
          ./scripts/build_mac_app.sh python3 data/state_exam_public_admin_demo.db

      - name: Verify Tezis.app bundle exists
        run: |
          if [ ! -d "dist/Tezis.app" ]; then
            echo "dist/Tezis.app missing after build"
            exit 1
          fi
          echo "Bundle OK: dist/Tezis.app"
```

- [ ] **Step 3: Validate YAML syntax locally**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/mac-build-smoke.yml', encoding='utf-8')); print('YAML OK')"
```
Expected output: `YAML OK` on stdout, exit code 0.

If PyYAML is missing, install with `pip install pyyaml` first.

- [ ] **Step 4: Sanity-check that triggers/runner/steps are what we designed**

Run:
```bash
grep -E "^(on:|  workflow_dispatch:|    runs-on:|      - name:)" .github/workflows/mac-build-smoke.yml
```
Expected (order matters):
```
on:
  workflow_dispatch:
    runs-on: macos-latest
      - name: Setup Python 3.12
      - name: Install Python deps
      - name: Ensure bundled seed exists
      - name: Build macOS app
      - name: Verify Tezis.app bundle exists
```
If anything is off, fix the file before committing.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/mac-build-smoke.yml
git commit -m "ci(mac-smoke): add workflow_dispatch-only Mac build verification

Mirrors the build-macos job from release.yml but skips packaging/upload.
Lets the developer manually verify macos-latest build succeeds before
pushing a release tag, catching Mac-specific breakage outside of release
path."
```

---

## Task 2: Update release-readiness memory to reference the new workflow

**Files:**
- Modify: `C:/Users/tutor/.claude/projects/D--Coding-projects/memory/feedback_release_macos.md`

The existing memory says "verify Mac launch" without a concrete mechanism. Now that the workflow exists, we give it a name.

- [ ] **Step 1: Read the current memory file**

Run: `cat "C:/Users/tutor/.claude/projects/D--Coding-projects/memory/feedback_release_macos.md"` and confirm it contains the frontmatter and the rule body with `**Why:**` and `**How to apply:**` sections.

- [ ] **Step 2: Rewrite the "How to apply" line to reference the workflow**

Replace the existing "How to apply" block with:

```markdown
**How to apply:** Before any commit to main that may ship, any `git push` to main, or any release tag (`v*`), confirm the user has run the `Mac build smoke` workflow on GitHub Actions (`.github/workflows/mac-build-smoke.yml`, `workflow_dispatch` trigger) on the target branch and that it finished green. Remind the user of this explicitly if they are about to tag or push to main. Do not silently assume Windows green == Mac green. If the workflow hasn't been run or is red, pause and flag it — the memory exists specifically to prevent shipping an unverified Mac build.
```

Keep the `**Why:**` line unchanged.

- [ ] **Step 3: Verify the memory file is still valid**

Check that the file still has:
- YAML frontmatter with `name`, `description`, `type: feedback`
- The top-line rule
- A `**Why:**` line
- The new `**How to apply:**` block

No commit needed — memory lives outside git.

---

## Task 3: Manual acceptance test (user-driven)

The real verification requires the workflow to be on `main` on GitHub. This task captures the procedure for the user — no automation.

**Files:** none

- [ ] **Step 1: Push the new commits to `origin/main`**

The user runs:
```bash
cd "D:/Coding projects/ticket-exam-trainer"
git push origin main
```

This publishes both the spec commit (`ae71b2f`) and the Task 1 workflow commit.

- [ ] **Step 2: Trigger the workflow from GitHub UI**

The user:
1. Opens GitHub repo → **Actions** tab
2. In the left sidebar, clicks **Mac build smoke**
3. Clicks **Run workflow** (top right), leaves branch as `main`, clicks green **Run workflow** button
4. Waits ~10-15 minutes for the job to finish

- [ ] **Step 3: Interpret result**

- **Green ✓** — macOS build works on current `main`. Release-ready from a build perspective.
- **Red ✗** — click into the failing step, read the log. Most likely failure modes:
  - `Install Python deps` — a package fails to install on macOS (rare but possible for pinned wheels)
  - `Build macOS app` — `flet pack` or `build_mac_app.sh` failing, most common real failure
  - `Verify Tezis.app bundle exists` — the build silently didn't produce the bundle
  Fix the underlying cause in a new commit, push, re-run workflow.

- [ ] **Step 4: (Optional) Negative test**

To prove the workflow actually catches breakage, the user can temporarily break `scripts/build_mac_app.sh` (e.g., add `exit 1` on line 2), push, re-run workflow, confirm it fails at the `Build macOS app` step, then revert. This is a one-time confidence-building step, not part of the regular release loop.

---

## Self-Review (performed before finalizing plan)

**Spec coverage check:**
- Spec §2 Decisions: all four rows covered. Trigger = `workflow_dispatch` ✓ (Task 1 Step 2). Runner = `macos-latest` ✓ (Task 1 Step 2). Depth α = build + verify bundle, no runtime ✓ (Task 1 Step 2 has no launch step). No artifact upload ✓ (Task 1 Step 2 has no upload-artifact step). No pytest matrix change ✓ (not in any task).
- Spec §3.1 Workflow pseudocode: all 6 bullets map 1:1 to YAML steps in Task 1 Step 2.
- Spec §3.2 "What NOT": no automation triggers, no binary run, no artifacts, no notifications, no OS matrix — none present in plan ✓.
- Spec §4 Applied workflow: procedure documented in Task 3 Steps 2-3.
- Spec §5 Testing: negative test covered in Task 3 Step 4.
- Spec §6 Risks: user awareness handled via Task 2 memory update (forgot-to-run risk) and Task 3 Step 3 (interpretation guidance).

**Placeholder scan:** no TBD/TODO/fill-in-later in any task. All code blocks are complete. All commands are exact.

**Type/name consistency:** workflow name `Mac build smoke` is consistent between Task 1 (YAML `name:`), Task 2 memory ("`Mac build smoke` workflow"), and Task 3 ("clicks **Mac build smoke**").

No gaps found.
