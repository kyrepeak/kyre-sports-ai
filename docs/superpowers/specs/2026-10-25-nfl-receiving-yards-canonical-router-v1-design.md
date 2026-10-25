# NFL Receiving Yards Canonical Router V1 Design

## Intent
Promote NFL Receiving Yards to first-class canonical runtime ownership so Universal Runtime V5 reaches the frozen Receiving Yards V21 page directly instead of through the shared generic NFL adapter.

## Goals
- Register `nfl/receiving-yards` as a dedicated `nfl-receiving-yards` route.
- Add `_nfl_receiving_yards_adapter(route)` that imports `nfl_receiving_yards_hub_v21` directly and renders `render_nfl_receiving_yards_hub()`.
- Resolve `receiving-yards` before the shared `_nfl_adapter` fallback.
- Preserve Step 2D Kyre Sports API gateway metadata and Step 2E registry validation.
- Preserve all frozen Receiving Yards V21 UI, model, market isolation, multi-source data behavior, player-vs-defense history, and 0.0 sportsbook projection influence.

## Non-goals
- No Receiving Yards UI redesign.
- No model/projection/provider math changes.
- No data-source migration in this router task.
- No MONSTER changes.

## Constraints
- API 2 only.
- One authoritative branch/PR/run path.
- TDD RED before production code.
- No generic NFL hub/slate/schedule imports on the canonical Receiving Yards route.
- Exact-head proof before merge and post-merge verification before freeze.

## Approaches
1. **Dedicated direct adapter — chosen.** Add a Receiving-specific adapter and resolver branch targeting frozen V21. Smallest change and matches the hardened NFL router pattern.
2. Keep shared `_nfl_adapter` and only rename the registry kind. Rejected because runtime would still depend on generic NFL hub/slate plumbing.
3. Build a new Receiving runtime/page version. Rejected because V21 already owns the certified page and this task is routing ownership only.

## Acceptance proof
A focused test must fail on the current baseline because the registry kind is generic and `_nfl_receiving_yards_adapter` is absent, then pass after the minimal change. Regression proof must confirm registry validation, direct V21 target, dedicated resolver selection, no generic fallback dependencies for Receiving Yards, and preserved V21 invariants.
