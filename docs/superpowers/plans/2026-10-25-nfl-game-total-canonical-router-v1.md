# NFL Game Total Canonical Router V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the certified NFL Game Totals compact page to first-class canonical `nfl/game-total` ownership without changing Game Totals product logic.

**Architecture:** Keep the compact layout/V10 stack untouched. Change only the Step 2E registry and base Universal Runtime V5 resolution so `nfl/game-total` directly owns and renders `nfl_game_totals_compact_layout_v1`, eliminating generic `nfl_hub_v18` fallback from the canonical path.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, Streamlit runtime adapters.

**Spec:** `docs/superpowers/specs/2026-10-25-nfl-game-total-canonical-router-v1-design.md`

## Global Constraints
- API 2 only; MONSTER untouched.
- Step 2A: one branch, one PR, one authoritative proof path.
- Anti-Loop: no duplicate runs/PRs/deployments or repeated unfinished polling.
- Step 2B: acceptance criteria and proof map locked before production edits.
- Step 2C: classify terminal failures before changing strategy.
- Preserve Step 2D Kyre Sports API truth metadata and Step 2E route coverage.
- Preserve compact-layout/V10 product behavior and all unrelated routes.

## Review Focus
- `nfl/game-total` must never resolve to `nfl_hub_v1` or `nfl_hub_v18`.
- The dedicated adapter must render `render_nfl_game_totals_hub()` from `nfl_game_totals_compact_layout_v1`.
- Existing compact-layout invariants must remain presentation-only over V10.
- Step 2D metadata must remain `kyre_sports_api`, data-truth-gated, and frontend-direct-provider false.
- Existing dedicated NFL route ownership must remain unchanged.

---

### Task 1: TDD canonical ownership lock

**Files:**
- Create: `tests/test_api2_nfl_game_total_canonical_router_v1.py`
- Create: `.github/workflows/api2-nfl-game-total-canonical-router-v1.yml`

**Interfaces:**
- Consumes: current `ROUTER_REGISTRY`, `universal_runtime_v5_loader.py`, compact-layout/V10 modules.
- Produces: failing proof that defines the dedicated registry kind/target and dedicated base-V5 adapter contract.

- [ ] **Step 1: Write the failing canonical ownership test**
Require registry target `nfl_game_totals_compact_layout_v1`, a dedicated adapter kind, no generic NFL hub target, direct compact-layout import/render, preserved Step 2D metadata, compact-layout/V10 invariants, and full Step 2E registry validation.

- [ ] **Step 2: Add focused GitHub Actions proof lane**
Compile the routing boundary and run the new canonical test plus compact-layout and Step 2E regressions.

- [ ] **Step 3: Open the single authoritative PR and verify RED**
Expected: focused canonical proof fails because production still registers `nfl_hub_v18` and base V5 lacks the dedicated Game Total adapter.

### Task 2: Minimal production routing implementation

**Files:**
- Modify: `api2_universal_sports_router_registry_v1.py`
- Modify: `universal_runtime_v5_loader.py`

**Interfaces:**
- Consumes: Task 1 contract.
- Produces: `_nfl_game_total_adapter(route: RuntimeRoute) -> DestinationAdapter` and first-class registry ownership.

- [ ] **Step 1: Update only the Game Total registry entry**
Set dedicated adapter kind and target `nfl_game_totals_compact_layout_v1`.

- [ ] **Step 2: Add the dedicated base-V5 adapter**
Load `nfl_game_totals_compact_layout_v1`, render `render_nfl_game_totals_hub()`, and select it before generic NFL handling.

- [ ] **Step 3: Verify GREEN on the authoritative PR head**
Expected: focused canonical proof and compact-layout/Step 2E regressions pass.

### Task 3: Exact-head proof, merge, and freeze

**Files:**
- Verification only unless a root-cause repair is required.

**Interfaces:**
- Consumes: Task 2 exact candidate head.
- Produces: terminal exact-head proof and merged/frozen canonical ownership.

- [ ] **Step 1: Run required regressions**
Focused Game Total canonical proof, compact-layout/V10 regression, Step 2A/Anti-Loop, Step 2D data truth, Step 2E universal router, and existing dedicated NFL route regressions.

- [ ] **Step 2: Review exact diff and candidate SHA**
Reject unrelated changes or a moved head.

- [ ] **Step 3: Merge only the proven exact head**
Use expected-head protection.

- [ ] **Step 4: Require post-merge terminal proof**
Confirm the merged API2 head and deployment/proof path are terminal before declaring GREEN + FROZEN.
