# NFL Spread Dedicated Canonical Router V1 Design

## Intent
Promote the already-certified NFL Spread V10 page to first-class API 2 canonical runtime ownership and remove the generic `_nfl_adapter` from the Spread path.

## Goals
- Make `nfl/spread` canonically target `nfl_spread_hub_v10`.
- Add a dedicated `_nfl_spread_adapter(route)` in base Universal Runtime V5.
- Make current production terminal resolution send NFL Spread through the canonical dedicated adapter.
- Preserve the existing dedicated Kyre Sports API Spread market endpoint and zero-blank/data-truth behavior.
- Preserve all Spread V10 UI, Line Lab, matchup history, schedule, model, projection, and settlement behavior.
- Preserve all unrelated routes and terminal overlays.

## Non-goals
- No Spread redesign.
- No changes to `nfl_spread_hub_v10.py`, frozen V9/V8/V3/V1 analytical ownership, market math, Monte Carlo, provider selection, odds, or projections.
- No changes to sportsbook projection influence; it remains 0.0%.
- No changes to MONSTER state or MONSTER control plane.

## Constraints
- API 2 only.
- Step 2A: one authoritative branch, PR, run/deployment/proof path.
- Anti-Loop: no duplicate PRs/runs/deployments or repeated polling of unfinished work.
- Step 2B: acceptance criteria and requirement→proof map locked before production edits.
- Step 2C: classify any terminal failure before changing strategy; repair root cause only.
- Step 2D: Kyre Sports API remains the only application-facing gateway; no SGO, ESPN, or ESPN BET; direct frontend-provider access remains false.
- Step 2E: explicit canonical registration must remain complete and valid.

## Current state / root cause
The live Spread page is V10. `universal_runtime_v5_loader_v23.py` already overlays NFL Spread to `nfl_spread_hub_v10`, but it does so through base `_nfl_adapter`, which imports shared NFL slate/hub infrastructure. Meanwhile Step 2E registry still identifies `nfl_spread_hub_v8` as canonical target. This leaves production behavior and canonical ownership out of sync.

## Approaches considered
1. **Canonical V10 dedicated adapter — chosen.** Update Step 2E target to V10, add `_nfl_spread_adapter`, and route production terminal Spread back through canonical base resolution. This removes shared runtime ownership while preserving V10 behavior.
2. Keep V23 overlay and only rename Step 2E target to V10. Rejected because Spread would still traverse `_nfl_adapter` and remain architecturally shared.
3. Create a new Spread V11 wrapper. Rejected because there is no product behavior change; another wrapper would add unnecessary ownership/version complexity.

## Success condition
- `ROUTER_REGISTRY[("nfl", "spread")]` uses dedicated `nfl-spread` ownership and target `nfl_spread_hub_v10`.
- Base Universal Runtime V5 resolves NFL Spread through `_nfl_spread_adapter`, directly loading V10 and rendering `render_nfl_hub("Spread")`.
- The current production terminal chain routes NFL Spread to canonical base resolution rather than the old shared V23 `_nfl_adapter` path.
- V10 frozen-behavior tests, Step 2D data truth, Step 2E coverage, and NFL route regressions pass on the exact candidate head.
- Exact candidate head merges; post-merge Step 2D and deployment proofs are terminal green before freeze.