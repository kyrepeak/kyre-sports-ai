# NFL Game Total Canonical Router V1 Design

## Intent
Promote the already-certified NFL Game Totals compact page to first-class canonical ownership of the live `NFL / game-total` route in API 2.

## Goals
- Keep `nfl_game_totals_compact_layout_v1` presentation behavior unchanged.
- Keep its frozen V10 data/model/projection stack unchanged.
- Register `nfl/game-total` as a dedicated canonical route instead of generic `nfl_hub_v18` ownership.
- Resolve base Universal Runtime V5 directly to `nfl_game_totals_compact_layout_v1`.
- Preserve the existing Streamlit V97 → `nfl_hub_v36` → compact-layout production bridge.
- Preserve Step 2D Kyre Sports API truth metadata and Step 2E route coverage.
- Preserve all other NFL/CFB/NBA/WNBA routes.

## Non-goals
- No Game Totals redesign.
- No schedule, FanDuel market, provider, model, probability, projection, final-read, or market-math changes.
- No sportsbook influence changes; existing projection isolation remains authoritative.
- No unrelated route changes.
- MONSTER remains untouched.

## Constraints
- API 2 only.
- One branch, one PR, one authoritative proof path.
- TDD RED before production routing edits.
- No duplicate runs/PRs/deployments or repeated polling of unfinished work.
- Exact-head proof must include focused canonical ownership, compact-layout/V10 regression, Step 2D, Step 2E, and existing dedicated NFL route regressions.

## Approaches considered
1. **Direct compact-layout ownership — chosen.** Register `nfl/game-total` to `nfl_game_totals_compact_layout_v1` and add a thin dedicated base-V5 adapter calling `render_nfl_game_totals_hub()`. This matches the current production Game Total page without pulling unrelated NFL markets through a generic hub.
2. **Point canonical ownership to `nfl_hub_v36`.** Rejected because V36 is a multi-market wrapper, so canonical ownership would still be indirect/generic.
3. **Keep `nfl_hub_v18`.** Rejected because it is stale generic ownership and routes Game Total to older V8.1 behavior rather than the certified compact/V10 page.

## Success condition
`ROUTER_REGISTRY[("nfl", "game-total")]` owns a dedicated Game Totals kind and target, base Universal Runtime V5 resolves that route through a dedicated compact-layout adapter with no generic NFL hub fallback, all required regressions pass on the exact candidate, the exact proven head is merged, and post-merge proof is terminal before freeze.