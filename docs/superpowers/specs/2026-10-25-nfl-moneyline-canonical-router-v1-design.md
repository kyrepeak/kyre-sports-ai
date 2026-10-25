# NFL Moneyline Canonical Router V1 Design

## Intent
Promote the already-proven NFL Moneyline V19 consumer owner to first-class canonical ownership of the live `NFL / moneyline` route.

## Goals
- Keep `nfl_moneyline_hub_v19` analytical and presentation behavior unchanged.
- Register `nfl/moneyline` as a dedicated canonical route.
- Resolve base Universal Runtime V5 directly to `nfl_moneyline_hub_v19`.
- Preserve the existing V21 Moneyline override contract while removing the Step 2E/base-V5 generic `nfl_hub_v18` mismatch.
- Preserve Step 2D Kyre Sports API truth metadata and Step 2E route coverage.
- Preserve all other dedicated NFL routes.

## Non-goals
- No Moneyline redesign.
- No probability, Monte Carlo, edge/EV, grading, stake-sizing, market-math, or sportsbook-influence changes.
- No unrelated NFL/CFB/NBA/WNBA route changes.
- MONSTER remains untouched.

## Constraints
- One API 2 branch, one PR, one authoritative proof path.
- TDD RED before production routing changes.
- Exact-head proof must include focused canonical ownership, existing V19 consumer proof, Step 2D, Step 2E, and existing dedicated NFL route regressions.

## Chosen approach
Promote the existing V19 owner in the Step 2E registry and add a thin dedicated Moneyline adapter in base `universal_runtime_v5_loader.py`. This aligns canonical ownership with the already-proven V21 terminal override without duplicating Moneyline product logic.
