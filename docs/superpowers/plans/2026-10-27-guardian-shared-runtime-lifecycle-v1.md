# Guardian Shared Runtime Lifecycle V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace contradictory direct ordering requirements in `app.py` with one neutral shared lifecycle contract that API 2 and MONSTER can both consume without sharing private state.

**Architecture:** Add a tiny system-neutral lifecycle runner with explicit pre-render hooks, one primary renderer, and post-render hooks. `app.py` passes the existing MONSTER runtime identity emitter as a pre-render hook and the existing universal `render_app` as the primary renderer. API 2 and MONSTER private ledgers, receipts, frozen registries, SHAs, and proof state remain untouched.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, existing Streamlit entrypoint.

**Spec:** KYRE GUARDIAN V1 shared-infrastructure mission and the user-approved neutral shared lifecycle repair in the active Guardian conversation.

## Global Constraints

- Guardian owns only the shared lifecycle repair and Guardian proof lane.
- Do not modify API 2 or MONSTER private ledgers, proof receipts, frozen registries, leases, checkpoints, or Steps 2A-2G state.
- Keep `devsystem/monster_runtime_identity_v1.py` MONSTER-owned and unchanged.
- Preserve all existing product-routing and projection behavior.
- No SGO, ESPN, or ESPN BET additions.
- One branch, one PR, no blind retries.

## Review Focus

- A pre-render proof hook must run before a renderer that can interrupt execution.
- Post-render hooks must not run when the renderer interrupts or raises.
- The shared lifecycle module must not import or encode API 2 or MONSTER policy.
- `app.py` must delegate ordering instead of directly calling system-owned sidecars around `render_app`.
- Existing API 2 and MONSTER shared regression tests must converge on the neutral contract without changing private proof artifacts.

---

### Task 1: Add failing Guardian contract tests

**Files:**
- Create: `tests/test_guardian_shared_runtime_lifecycle_v1.py`
- Create: `.github/workflows/guardian-shared-runtime-lifecycle-v1.yml`

- [ ] Write tests for lifecycle existence, hook order, interruption behavior, system neutrality, and `app.py` delegation.
- [ ] Push test-only state and verify Guardian CI fails for the missing lifecycle implementation.

### Task 2: Implement neutral shared lifecycle

**Files:**
- Create: `devsystem/shared_runtime_lifecycle_v1.py`
- Modify: `app.py`

**Interface:**
- `run_shared_runtime_lifecycle(*, render, pre_render_hooks=(), post_render_hooks=()) -> Any`

- [ ] Implement only the behavior pinned by Task 1.
- [ ] Wire `emit_runtime_identity_marker` as a pre-render hook and `render_app` as the primary renderer.
- [ ] Verify Guardian tests pass.

### Task 3: Converge conflicting shared regression contracts

**Files:**
- Modify: `tests/test_api2_sitewide_render_repair_r1.py`
- Modify: `tests/test_api2_sitewide_render_deployment_convergence_r2.py`
- Modify: `tests/test_api2_nfl_moneyline_page1_current_convergence_r1.py`
- Modify: `tests/test_api2_nfl_moneyline_page1_live_route_restore_r1.py`
- Modify: `tests/test_devsystem_monster_step2g_production_promotion_v1.py`
- Modify: `tests/test_devsystem_monster_step2g_prerender_runtime_identity_r1.py`

- [ ] Remove mutually exclusive direct line-order assertions.
- [ ] Require the shared lifecycle import and `pre_render_hooks=(emit_runtime_identity_marker,)` wiring instead.
- [ ] Preserve every unrelated API 2 and MONSTER assertion.
- [ ] Expand Guardian CI to run all affected regression files.

### Task 4: Exact-head verification and promotion

- [ ] Open one Guardian PR to protected `main`.
- [ ] Require Guardian CI plus existing protected `runless-final-gate` evidence.
- [ ] Verify exact PR head before merge.
- [ ] Merge only after all required checks are green.
- [ ] Re-read `main`, verify the merge SHA, all three Vercel production lanes, aliases, and runtime errors.
- [ ] Freeze only the Guardian shared-lifecycle result; do not certify API 2 or MONSTER private state.
