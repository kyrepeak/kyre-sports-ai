# Universal Atomic Navigation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all site navigation atomically replace the outgoing destination so visitors never see the prior sports page behind a new route, while preventing background destination prefetch.

**Architecture:** Keep `app.py` on the existing NFL Daily Picks V3 terminal. Preserve that terminal's current loader ownership and delegate only final rendering to `universal_atomic_navigation_runtime_v1.render_atomic_app(frozen_runtime)`. The atomic runtime reuses Universal Runtime V5 state, route, scope, health, and fallback contracts. Every destination renders inside one replaceable `st.empty()` content slot; route changes show an opaque transition shield before selected-destination loading; the atomic path never executes bounded prefetch. Future NFL Daily Picks V4 freezes V3 and therefore inherits this behavior without cross-lane writes.

**Tech Stack:** Python 3, Streamlit, pytest, existing Universal Runtime V5 modules.

**Spec:** `docs/superpowers/specs/2026-10-19-universal-atomic-navigation-v1.md`

## Global Constraints
- One authoritative branch/PR/proof path under Step 2A.
- No individual sport-page mutations.
- No model/projection/probability/sportsbook logic mutations.
- Existing route generation/scope stale-commit protection remains mandatory.
- Background destination prefetch is disabled in the active atomic render path.
- Ordinary same-route reruns do not display the full transition shield.
- `app.py` remains source-main-equivalent and is not owned by this workstream.
- No NFL Daily Picks V4-owned path is modified.

## Review Focus
- Rapid sport-to-sport taps: only the newest route generation may commit.
- Market-to-market taps within one sport: outgoing content must remain hidden during load.
- Canonical URL route changes: receive the same atomic transition behavior.
- Destination load exceptions: outgoing content must not reappear behind a failed handoff.
- Same-route widget reruns: no unnecessary full-screen loading flash.
- V4 compatibility: V4 can freeze V3 and inherit the atomic render behavior without an entrypoint conflict.

---

### Task 1: Pure transition helpers

**Files:**
- Create: `universal_atomic_navigation_v1.py`
- Create/Test: `tests/test_universal_atomic_navigation_v1.py`

- [x] Write RED coverage for canonical route identity and opaque route-specific transition markup.
- [x] Implement `route_identity`, `is_route_transition`, and `transition_markup`.
- [x] Verify helper contract GREEN.

### Task 2: Terminal-agnostic atomic runtime

**Files:**
- Create: `universal_atomic_navigation_runtime_v1.py`
- Create/Test: `tests/test_universal_atomic_navigation_terminal_inheritance_v1.py`

- [x] Write RED coverage proving terminal-agnostic ownership, render ordering, stale-generation guards, and zero background prefetch.
- [x] Implement one destination slot plus one opaque transition slot.
- [x] Shield and clear outgoing destination before `load_destination` on route identity changes.
- [x] Load only the selected adapter, re-check generation/scope, render inside the destination slot, and unmask only after current-generation commit.
- [x] Preserve Runtime V5 fallback and health checks.
- [x] Verify focused inheritance contract GREEN.

### Task 3: Non-conflicting V3 terminal inheritance

**Files:**
- Modify: `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py`
- Keep unchanged: `app.py`

- [x] Preserve V3 loader patch ownership (`choose_prefetch`, `load_destination`, `resolve_destination`).
- [x] Replace only V3 final rendering with `render_atomic_app(frozen_runtime)`.
- [x] Restore/confirm `app.py` is identical to source main and still imports V3.
- [x] Confirm the competing NFL V4 workstream owns `app.py` and V4 files without path overlap from this lane.
- [x] Confirm V4 RED contract freezes V3, allowing future inheritance.

### Task 4: Exact-head regression proof and finalization

**Files:**
- `devsystem/runless_proof_plans/monster-universal-atomic-navigation-v1.json`
- `devsystem/task_ledgers/monster-universal-atomic-navigation-v1.json`

- [ ] Lock exact candidate SHA after docs/ledger/proof plan are final.
- [ ] Run the Runless proof-plan commands exactly once in the existing sandbox.
- [ ] Confirm focused Atomic tests, universal route/isolation tests, current NFL V3 tests, current NBA regressions (excluding documented obsolete exact-owner assertions), compile, and Runtime V5 certification are GREEN.
- [ ] Verify branch diff contains no `app.py` change and no NFL V4-owned path.
- [ ] Open one PR only after exact-head proof succeeds.
- [ ] Obtain one authoritative `runless-final-gate` result for that exact candidate.
- [ ] Merge only the proved exact head, verify merged main, transact frozen registry/read-back, release any owned lease, and record `MONSTER_UNIVERSAL_ATOMIC_NAVIGATION_V1_FROZEN`.
