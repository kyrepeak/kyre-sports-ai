# Universal Atomic Navigation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all site navigation atomically replace the outgoing destination so visitors never see the prior sports page behind a new route, while preventing background destination prefetch.

**Architecture:** Add a terminal Streamlit runtime overlay above the current NFL Daily Picks V3 terminal. Reuse Universal Runtime V5 state, route, loader, scope, health, and fallback contracts; only replace final render orchestration. Every destination renders inside one replaceable `st.empty()` content slot, route changes show an opaque transition shield before loading, and the terminal does not execute bounded prefetch.

**Tech Stack:** Python 3, Streamlit, pytest, existing Universal Runtime V5 modules.

**Spec:** `docs/superpowers/specs/2026-10-19-universal-atomic-navigation-v1.md`

## Global Constraints
- One authoritative branch/PR/proof path under Step 2A.
- No individual sport-page mutations.
- No model/projection/probability/sportsbook logic mutations.
- Existing route generation/scope stale-commit protection remains mandatory.
- Background destination prefetch is disabled in the active atomic terminal.
- Ordinary same-route reruns do not display the full transition shield.

## Review Focus
- Rapid sport-to-sport taps: only the newest route generation may commit.
- Market-to-market taps within one sport: outgoing content must remain hidden during load.
- Canonical URL route changes: must receive the same atomic transition behavior.
- Destination load exceptions: old destination must not reappear behind an error.
- Same-route widget reruns: no unnecessary full-screen loading flash.

---

### Task 1: Atomic navigation terminal contract

**Files:**
- Create: `tests/test_universal_atomic_navigation_v1.py`
- Create: `universal_atomic_navigation_v1.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1.py`

**Interfaces:**
- Consumes: existing `RuntimeRoute`, Runtime V5 route/scope helpers, current NFL Daily Picks V3 terminal loader chain.
- Produces: `route_identity(route)`, `is_route_transition(before, after)`, `transition_markup(route)`, and terminal `render_app()` / `record_bootstrap_import_ms`.

- [ ] **Step 1: Write the failing test**
  - Import `universal_atomic_navigation_v1` and the new terminal module.
  - Assert route identity compares sport, market, and canonical params.
  - Assert same-route rerun is not a transition and sport/market/param change is.
  - Assert terminal source clears the destination slot and emits the shield before `load_destination`.
  - Assert terminal source renders inside the destination slot, clears the shield after render, and contains no `_run_bounded_prefetch(` call.
  - Assert upstream terminal is `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3`.

- [ ] **Step 2: Run focused test to verify RED**
  - Run: `pytest -q tests/test_universal_atomic_navigation_v1.py`
  - Expected: FAIL because the new modules do not exist.

- [ ] **Step 3: Implement minimal atomic terminal**
  - Implement pure route identity/transition/markup helpers.
  - Implement active render orchestration using existing Runtime V5 private contracts without modifying them.
  - Render stable site shell/nav first; on route change render fixed opaque shield, clear destination slot, load only selected adapter, scope-check, render inside destination slot, then remove shield.
  - Never call bounded prefetch.
  - Preserve fallback runtime.

- [ ] **Step 4: Run focused test to verify GREEN**
  - Run: `pytest -q tests/test_universal_atomic_navigation_v1.py`
  - Expected: PASS.

### Task 2: Production activation and regression proof

**Files:**
- Modify: `app.py`
- Test: `tests/test_universal_atomic_navigation_v1.py`
- Create: `devsystem/runless_proof_plans/monster-universal-atomic-navigation-v1.json`

**Interfaces:**
- Consumes: Task 1 terminal `render_app()` and `record_bootstrap_import_ms`.
- Produces: production entrypoint activation and exact-head proof plan.

- [ ] **Step 1: Extend failing activation test**
  - Assert `app.py` imports the atomic terminal and not the previous terminal directly.

- [ ] **Step 2: Run activation assertion RED**
  - Run: `pytest -q tests/test_universal_atomic_navigation_v1.py`
  - Expected: FAIL on app activation assertion.

- [ ] **Step 3: Activate terminal and add one Runless proof plan**
  - Point `app.py` to `streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1`.
  - Proof plan runs focused atomic tests plus existing Universal Runtime/navigation regression tests and runtime certification.

- [ ] **Step 4: Run focused + regression verification**
  - Run focused atomic suite and existing Universal Runtime/navigation suites.
  - Expected: all PASS.

- [ ] **Step 5: Exact-head finalization**
  - Verify candidate SHA, open one PR, obtain one Runless proof, expected-head merge, merged-main readback, frozen registry closeout, release scope lease, canonical GREEN + FROZEN readback.
