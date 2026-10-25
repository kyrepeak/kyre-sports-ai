# API2 NFL Passing TDs Canonical Router V1 Design

## Intent
Promote NFL Passing TDs from generic NFL hub ownership to a first-class canonical API2 route without changing projection math or touching MONSTER.

## Goals
- Make `nfl/passing-tds` own a dedicated runtime target.
- Keep Kyre Sports API as the only application-facing data gateway.
- Inherit Step 2D data-truth semantics and Step 2E canonical registration.
- Remove the Passing TDs route's dependency on `nfl_hub_v18` / `nfl_hub_v1` fallback ownership.
- Preserve semantic fail-closed behavior rather than fabricate quarterback/market data when a certified Passing TDs payload is unavailable.

## Non-goals
- No Passing TD projection/model redesign.
- No direct FanDuel, DraftKings, ESPN, ESPN BET, SGO, or other provider access from the frontend/runtime.
- No changes to Passing Yards, Rushing Yards, Receiving Yards, Receptions, Anytime TD, or MONSTER.

## Constraints
- One API2 branch, one PR, one proof lane.
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- Canonical registry must point `("nfl", "passing-tds")` directly to the dedicated runtime.
- Universal Runtime V5 must resolve Passing TDs through an explicit dedicated adapter.
- Existing Step 2E registry validation must remain green.

## Approaches considered
1. **Keep `nfl_hub_v18` ownership.** Rejected because it falls through to the old NFL foundation for Passing TDs.
2. **Build on Passing Yards presentation ownership.** Rejected as canonical ownership because Passing TDs is a distinct market and should not silently borrow another page's route boundary.
3. **Dedicated Passing TDs runtime + explicit universal adapter.** Selected. It creates clean route ownership now, keeps the surface safely fail-closed, and leaves future Passing TDs data/model work isolated behind the same stable canonical route.

## Design
Create `nfl_passing_tds_runtime_v1.py` with one public renderer, `render_nfl_passing_tds_runtime()`. It owns only the Passing TDs page boundary, imports no old NFL hub, makes no provider calls, and renders a truthful semantic unavailable/certification state rather than fabricated values.

Update `api2_universal_sports_router_registry_v1.py` so `nfl/passing-tds` uses adapter kind `nfl-passing-tds` and target `nfl_passing_tds_runtime_v1` while retaining `kyre_sports_api` + `api2_step2d_data_truth_gate_v1` metadata.

Update `universal_runtime_v5_loader.py` with `_nfl_passing_tds_adapter()` and resolve Passing TDs through it before the generic NFL adapter path.

Add a focused TDD contract proving dedicated ownership, Step 2D/2E inheritance, provider isolation, and no regression in universal Step 2E coverage.
