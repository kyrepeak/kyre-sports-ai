# NFL Daily Picks Canonical Router V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the already-frozen NFL Daily Picks V4 product to the first-class canonical `nfl/daily-picks` owner without changing its product logic.

**Architecture:** Keep `nfl_daily_picks_command_center_v4` as the existing presentation/product owner. Change only the canonical Step 2E registry and Universal Runtime V5 adapter so Daily Picks no longer travels through `nfl_hub_v18`/`nfl_hub_v1`. Add a focused proof lane and run V4 + Step 2D + Step 2E regressions on the exact head before merge.

**Tech Stack:** Python 3.12, Streamlit runtime adapters, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-25-nfl-daily-picks-canonical-router-v1-design.md`

## Global Constraints
- API 2 only; MONSTER untouched.
- One branch, one PR, one authoritative proof path.
- Existing Daily Picks V4 model/UI logic remains frozen.
- No generic NFL hub fallback for `nfl/daily-picks`.
- Preserve Step 2D data-truth and Step 2E live-route coverage.

## Review Focus
- `nfl/daily-picks` registry target cannot regress to `nfl_hub_v18` or `nfl_hub_v1`.
- V5 `resolve_destination()` must choose the dedicated Daily Picks adapter before generic NFL routing.
- Adapter must import exactly `nfl_daily_picks_command_center_v4` and call `render_nfl_daily_picks_command_center()`.
- Existing V4 freeze/model invariants remain unchanged.
- Existing dedicated NFL routes remain green.

---

### Task 1: Lock canonical Daily Picks ownership with TDD

**Files:**
- Create: `tests/test_api2_nfl_daily_picks_canonical_router_v1.py`
- Create: `.github/workflows/api2-nfl-daily-picks-canonical-router-v1.yml`
- Modify: `api2_universal_sports_router_registry_v1.py`
- Modify: `universal_runtime_v5_loader.py`

**Interfaces:**
- Consumes: `ROUTER_REGISTRY`, `RuntimeRoute`, `DestinationAdapter`, existing `nfl_daily_picks_command_center_v4.render_nfl_daily_picks_command_center`.
- Produces: dedicated `nfl-daily-picks` registration and `_nfl_daily_picks_adapter(route)`.

- [ ] **Step 1: Write the failing ownership tests**
  - Assert registry kind is `nfl-daily-picks`.
  - Assert registry target is `nfl_daily_picks_command_center_v4` and not a generic NFL hub.
  - Assert loader contains `_nfl_daily_picks_adapter` importing the V4 owner and rendering `render_nfl_daily_picks_command_center()`.
  - Assert `resolve_destination()` selects the dedicated adapter for `daily-picks`.
  - Assert Step 2E registry validation remains empty.

- [ ] **Step 2: Run RED proof**
  - Run focused ownership test plus Step 2E regression.
  - Expected: focused Daily Picks ownership tests fail because registry/adapter are still generic; Step 2E regression remains green.

- [ ] **Step 3: Implement minimal route-only repair**
  - Change Daily Picks registry entry to `_r("nfl", "daily-picks", "nfl-daily-picks", "nfl_daily_picks_command_center_v4")`.
  - Add `_nfl_daily_picks_adapter(route: RuntimeRoute) -> DestinationAdapter` that imports only `nfl_daily_picks_command_center_v4`, calls `render_nfl_daily_picks_command_center()`, and uses a 20-second TTL.
  - Route `nfl/daily-picks` through this adapter before generic NFL handling.

- [ ] **Step 4: Run GREEN proof**
  - Focused canonical route test + Step 2E regression.
  - Daily Picks V4 tests.
  - Step 2A/Anti-Loop and Step 2D exact-head gates.

- [ ] **Step 5: Scope/freeze review and merge exact head**
  - Confirm only planned files changed.
  - Merge with expected-head SHA.
  - Require post-merge Step 2D success and exact-SHA Vercel deployments READY before GREEN + FROZEN.
