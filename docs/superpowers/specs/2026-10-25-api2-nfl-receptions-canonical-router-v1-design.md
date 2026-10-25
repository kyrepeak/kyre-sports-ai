# API2 NFL Receptions Canonical Router V1 Design

## Intent
Promote NFL Receptions from generic NFL hub ownership to a first-class canonical API2 route without changing projection math or touching MONSTER.

## Goals
- Make `nfl/receptions` own a dedicated runtime target.
- Keep Kyre Sports API as the only application-facing data gateway.
- Inherit Step 2D data-truth semantics and Step 2E canonical registration.
- Remove the Receptions route's dependency on `nfl_hub_v18` / `nfl_hub_v1` fallback ownership.
- Preserve fail-closed behavior rather than fabricate player/market data when a certified Receptions data surface is unavailable.

## Non-goals
- No Receptions projection/model redesign.
- No direct FanDuel, DraftKings, ESPN, ESPN BET, SGO, or other provider access from the frontend/runtime.
- No changes to Passing Yards, Rushing Yards, Receiving Yards, Passing TDs, Anytime TD, or MONSTER.

## Constraints
- One API2 branch, one PR, one proof lane.
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- Canonical registry must point `("nfl", "receptions")` directly to the dedicated runtime.
- Universal Runtime V5 must resolve Receptions through an explicit dedicated adapter.
- Existing Step 2E registry validation must remain green.

## Approaches considered
1. **Keep `nfl_hub_v18` ownership.** Rejected because it falls through to the old NFL foundation for Receptions.
2. **Reuse the historical V236 app-level handoff.** Rejected as canonical ownership because it is a legacy whole-app wrapper and intentionally fail-closed.
3. **Dedicated Receptions runtime + explicit universal adapter.** Selected. It creates clean route ownership now, keeps the surface safely fail-closed, and leaves future Receptions data/model work isolated behind the same stable canonical route.

## Design
Create `nfl_receptions_runtime_v1.py` with one public renderer, `render_nfl_receptions_runtime()`. It owns only the Receptions page boundary, imports no old NFL hub, makes no provider calls, and renders a truthful semantic unavailable/certification state rather than fabricated values.

Update `api2_universal_sports_router_registry_v1.py` so `nfl/receptions` uses adapter kind `nfl-receptions` and target `nfl_receptions_runtime_v1` while retaining `kyre_sports_api` + `api2_step2d_data_truth_gate_v1` metadata.

Update `universal_runtime_v5_loader.py` with `_nfl_receptions_adapter()` and resolve Receptions through it before the generic NFL adapter path.

Add a focused TDD contract proving dedicated ownership, Step 2D/2E inheritance, provider isolation, and no regression in universal Step 2E coverage.
