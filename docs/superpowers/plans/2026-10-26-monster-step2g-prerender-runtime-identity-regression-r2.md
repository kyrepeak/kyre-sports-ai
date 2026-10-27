# MONSTER Step 2G Pre-Render Runtime Identity Regression R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore MONSTER runtime identity emission before page rendering on the current main lineage and close Step 2G with exact-head proof, live production read-back, and frozen checkpoint.

**Architecture:** Keep the existing production entrypoint and proof infrastructure unchanged except for the final call order. Reuse the existing pre-render regression contract plus current NBA PRA Page 2 focused regressions, then authorize only the exact candidate through Runless App 5204253.

**Tech Stack:** Python 3.11, Streamlit, pytest, GitHub protected main, Vercel Runless proof plane.

**Spec:** `docs/superpowers/specs/2026-10-26-monster-step2g-prerender-runtime-identity-regression-r2-design.md`

## Global Constraints
- Authority is MONSTER ONLY.
- Base SHA is exactly `e319e5c73980736ca3e5da71316e018e025eb52c`.
- One active branch, one PR, one proof path; no blind retries.
- Do not change sports, provider, sportsbook, projection, routing, or Page 2 rendering logic.
- Exact-head `runless-final-gate` from App 5204253 is required before merge.

## Review Focus
- Marker must remain exactly once and before `render_app()`.
- Page 2 module-cache evictions must remain before cache invalidation.
- V4 CSS must remain one `<style>` envelope with no post-style leakage.
- Exact-head proof must match the PR candidate, not an earlier preview SHA.
- Final production freeze must be based only on MONSTER evidence.

---

### Task 1: Restore and prove the pre-render identity invariant

**Files:**
- Modify: `app.py`
- Reuse test: `tests/test_devsystem_monster_step2g_prerender_runtime_identity_r1.py`
- Create: `devsystem/runless_proof_plans/monster-step2g-prerender-runtime-identity-regression-r2.json`
- Create: `devsystem/task_ledgers/monster-step2g-prerender-runtime-identity-regression-r2.json`

**Interfaces:**
- Consumes: existing `emit_runtime_identity_marker()` and `render_app()` calls.
- Produces: exactly one marker call ordered before exactly one render call.

- [x] **Step 1: Observe the existing regression test fail**

Run: `python -m pytest --noconftest -q tests/test_devsystem_monster_step2g_prerender_runtime_identity_r1.py`
Observed baseline: `1 failed, 5 passed`, with `marker_call < render_call` false.

- [x] **Step 2: Implement the minimal repair**

Swap only the final two calls so `emit_runtime_identity_marker()` executes before `render_app()`.

- [ ] **Step 3: Verify focused contracts**

Run the four focused pytest files and `py_compile` exactly as declared in the R2 runless proof plan. Expected: all pass.

- [ ] **Step 4: Prove and merge exact head**

Expected: `runless-final-gate` success from App 5204253 on the exact candidate; merge with expected-head protection; verify merged tree contains the tested order.

- [ ] **Step 5: Production and freeze read-back**

Expected: fresh 390x844 NBA PRA Page 2 production witness is READY with current MONSTER identity and no leaked V4 CSS text; write and independently read back `MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1_FROZEN` before declaring 100% GREEN + FROZEN.
