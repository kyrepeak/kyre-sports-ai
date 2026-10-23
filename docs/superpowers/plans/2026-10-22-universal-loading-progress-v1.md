# Universal Loading Progress V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add truthful universal 0–100 stage progress to the existing loading takeover without regressing navigation or sports-page ownership.

**Architecture:** Add a forward-only Page Experience V3 presentation successor that upgrades the existing client overlay and provides determinate server fallback markup. Add Runtime V4 that emits progress only at real milestones while retaining Runtime V3 stale-generation/one-render guards. Activate through a thin terminal successor over the current navigation-speed repair terminal.

**Tech Stack:** Python, Streamlit, HTML/CSS/JavaScript, pytest, Runless V2.

**Spec:** `docs/superpowers/specs/2026-10-22-universal-loading-progress-v1.md`

## Global Constraints
- Percent stages are exactly 0, 15, 35, 70, 90, 100.
- No timer-driven fake percentage progression.
- Same-tab/latest-tap/no-prefetch behavior must remain intact.
- NBA PRA, CFB Top Picks V19, and NFL rushing route ownership must remain intact.
- No model/data/provider semantics may change.

## Review Focus
- Rapid second tap must prevent stale first-route progress/commit.
- Local controls must not trigger the universal progress takeover.
- Controller-mount failure must retain server determinate progress.
- Percentage/status text must be clamped/escaped.
- 100% must occur only after a current-generation renderer commit.

---

### Task 1: Progress presentation contract
**Files:** Create `universal_page_experience_v3.py`; Test `tests/test_universal_loading_progress_v1.py`.
**Interfaces:** Produces `page_experience_controller_markup_v3`, `page_experience_progress_markup`, and `page_experience_progress_update_markup`.
- [ ] Write static regression tests for percent UI, determinate track, 0% reset, clamping, and no fake timer.
- [ ] Run focused tests and confirm RED because V3 does not exist.
- [ ] Implement the minimal V3 presentation successor over V2.
- [ ] Run focused tests GREEN.

### Task 2: Stage-gated runtime
**Files:** Create `universal_page_experience_runtime_v4.py`; Test `tests/test_universal_loading_progress_v1.py`.
**Interfaces:** Consumes V3 progress helpers; produces `render_page_experience_app_v4(core)`.
- [ ] Pin stage ordering around route resolution, load, render, and commit.
- [ ] Preserve `can_commit`, `commit_if_current`, one renderer call, and no prefetch.
- [ ] Run focused tests GREEN.

### Task 3: Terminal activation and regression preservation
**Files:** Create `streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1.py`; later modify `app.py` under exact authorized thaw; Test `tests/test_universal_loading_progress_terminal_v1.py`.
**Interfaces:** Consumes the current navigation-speed repair terminal and Runtime V4.
- [ ] Delegate `resolve_destination` and bootstrap timing to the current repair terminal so NBA PRA/CFB/NFL route fixes remain inherited.
- [ ] Obtain exact-head `app.py` thaw only after competing entrypoint lease is gone.
- [ ] Activate the new terminal in `app.py`.
- [ ] Run new tests plus prior universal navigation, NBA PRA, CFB Top Picks, and NFL rushing regressions.
- [ ] Obtain exact-head Runless proof, merge one PR, verify merged deployments, ledger closeout, and freeze.
