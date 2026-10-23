# Universal Streamlit Navigation + Speed V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep internal Streamlit navigation in one tab, make the latest rapid tap authoritative, and remove avoidable universal navigation overhead.

**Architecture:** Add a forward-only Universal Page Experience V2 browser/controller successor over frozen V1, then activate it through one terminal runtime overlay. Preserve Runtime V5 generation/scope stale-write guards and all sports/model/data owners.

**Tech Stack:** Python, Streamlit, browser JavaScript embedded by Streamlit, pytest, Runless V2.

**Spec:** `docs/superpowers/specs/2026-10-22-universal-streamlit-navigation-speed-v1.md`

## Global Constraints
- Frozen sports pages are not modified.
- No sports model/data/probability/ranking semantics change.
- Internal links only are forced same-tab; external links remain unchanged.
- No interval polling and no background destination prefetch.
- Exact-head Runless proof is required before merge.

## Review Focus
- Internal relative/query/hash links that Streamlit marks `_blank` must remain in the current tab.
- External links must not be rewritten.
- Rapid consecutive taps must invalidate stale delayed transition work.
- Back/forward must remain supported.
- The terminal overlay must inherit all existing destination resolver overlays.

---

### Task 1: Browser navigation contract

**Files:**
- Create: `tests/test_universal_page_experience_v2.py`
- Create: `universal_page_experience_v2.py`

**Interfaces:**
- Consumes: V1 destination labels and existing page-experience shell behavior.
- Produces: `page_experience_controller_markup_v2(route)` and same-tab/latest-tap browser contract.

- [ ] **Step 1: Write the failing test** proving V2 is absent and requiring internal-link normalization, external-link preservation, a MutationObserver, monotonic navigation generation, and no interval polling.
- [ ] **Step 2: Run the focused test and verify RED.**
- [ ] **Step 3: Implement minimal V2 controller.**
- [ ] **Step 4: Run the focused test and verify GREEN.**

### Task 2: Universal runtime successor

**Files:**
- Create: `tests/test_universal_page_experience_runtime_v2.py`
- Create: `universal_page_experience_runtime_v2.py`

**Interfaces:**
- Consumes: Runtime V5 route/load/commit APIs and V2 controller.
- Produces: `render_page_experience_app_v2(core)`.

- [ ] **Step 1: Write failing runtime tests** requiring preserved scope guards, one active destination render, V2 controller mount, and no background prefetch.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement runtime V2 as a forward-only successor.**
- [ ] **Step 4: Verify GREEN.**

### Task 3: Terminal activation + proof metadata

**Files:**
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1.py`
- Modify: `app.py`
- Create: `tests/test_universal_navigation_speed_terminal_v1.py`
- Create: `devsystem/runless_proof_plans/api2-universal-streamlit-navigation-speed-v1.json`
- Create: `devsystem/task_ledgers/api2-universal-streamlit-navigation-speed-v1.json`

**Interfaces:**
- Consumes: current NBA PRA terminal resolver ownership and Runtime V2.
- Produces: exact production entrypoint ownership and Runless proof plan.

- [ ] **Step 1: Write failing terminal activation test.**
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Add terminal overlay and advance `app.py` to it without changing sports resolver logic.**
- [ ] **Step 4: Add Runless proof plan and task ledger.**
- [ ] **Step 5: Run focused universal suite + py_compile and verify GREEN.**
- [ ] **Step 6: Request exact-head Runless proof, open one PR, merge exact authorized SHA, verify merged main, finalize ledger, closeout GREEN_FROZEN, and stop.**
