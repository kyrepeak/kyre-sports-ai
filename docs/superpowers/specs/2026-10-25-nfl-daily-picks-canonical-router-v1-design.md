# NFL Daily Picks Canonical Router V1 Design

## Intent
Restore the already-frozen NFL Daily Picks V4 product as the first-class canonical owner of the live `NFL / daily-picks` destination after Step 2E temporarily registered that route to the generic `nfl_hub_v18` path.

## Goals
- Keep the existing Daily Picks V4 product/model/UI unchanged.
- Register `nfl/daily-picks` as a dedicated canonical route.
- Resolve Universal Runtime V5 directly to `nfl_daily_picks_command_center_v4`.
- Preserve Step 2D Kyre Sports API truth metadata and Step 2E route coverage.
- Prevent fallback through `nfl_hub_v18` or `nfl_hub_v1` for Daily Picks.
- Preserve Slate, Receptions, Passing TDs and Anytime TD dedicated ownership.

## Non-goals
- Do not redesign Daily Picks V4.
- Do not alter Daily Picks model probabilities, rankings, parlays, or presentation.
- Do not change unrelated NFL/CFB/NBA/WNBA routes.
- Do not touch MONSTER.

## Constraints
- One API 2 branch, one PR, one authoritative proof path.
- TDD: focused canonical-ownership test must fail before production routing changes.
- Exact-head proof must include the Daily Picks V4 regression suite plus Step 2D/Step 2E control gates.

## Approaches
1. Rebuild Daily Picks as a new runtime: rejected because V4 already exists and is frozen.
2. Keep generic `nfl_hub_v18` registration and delegate internally: rejected because it preserves ambiguous ownership.
3. **Chosen:** promote the existing V4 owner directly in the canonical registry and Universal Runtime V5 with a thin dedicated adapter. This is the smallest route-only repair and avoids duplicating product logic.
