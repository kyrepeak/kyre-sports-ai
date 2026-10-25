# NFL Moneyline Canonical Router V1 Implementation Plan

**Goal:** Promote the existing NFL Moneyline V19 consumer owner to first-class canonical `nfl/moneyline` ownership without changing Moneyline product logic.

## Control contract
- API 2 only; MONSTER untouched.
- Step 2A: one branch, one PR, one authoritative proof path.
- Anti-Loop: no duplicate runs/PRs/deployments or repeated unfinished polling.
- Step 2B: acceptance criteria and proof map locked before production edits.
- Step 2C: classify any terminal failure before changing strategy.
- Preserve Step 2D and Step 2E guarantees.

## Task 1 — TDD ownership lock
- Create focused test requiring registry kind `nfl-moneyline`, target `nfl_moneyline_hub_v19`, Kyre Sports API + Step 2D metadata, and no generic NFL hub target.
- Require a dedicated base-V5 `_nfl_moneyline_adapter(route)` importing V19 and rendering `render_nfl_moneyline_hub()`.
- Require `resolve_destination()` to select this adapter for `nfl/moneyline`.
- Require existing V19 consumer invariants and Step 2E validation to remain green.
- Run RED before production routing changes.

## Task 2 — Minimal implementation
- Update `api2_universal_sports_router_registry_v1.py` Moneyline registration only.
- Add dedicated Moneyline adapter and branch in `universal_runtime_v5_loader.py` before generic NFL handling.
- Do not modify `nfl_moneyline_hub_v19.py`.

## Task 3 — Exact-head verification
- Focused Moneyline canonical router proof.
- Existing V19 consumer proof.
- Step 2A / Anti-Loop.
- Step 2D data truth.
- Step 2E universal router.
- Existing dedicated NFL route regressions.
- Scope/diff review.
- Merge only the proven exact head.
- Require post-merge Step 2D success and exact-SHA Vercel deployments READY before GREEN + FROZEN.
