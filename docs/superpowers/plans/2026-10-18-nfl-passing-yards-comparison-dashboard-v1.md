# NFL Passing Yards Comparison Dashboard V1

## Goal
Replace the current long-form Passing Yards presentation with a professional synchronized two-quarterback comparison dashboard while preserving all certified model, probability, market, identity, schedule and data behavior.

## Authority
- Branch: `api2-nfl-passing-yards-comparison-v1`
- Base main: `be3a8b470b4b085a87c50a0da18c1db965be9881`
- Scope lease: `SCOPE-LEASE-986673DF618965395A33BA4E`
- One PR / one Runless proof / one freeze chain only.

## Implementation
1. Add `nfl_passing_yards_hub_v89.py` as presentation-only owner using the frozen V43 certified capture seam.
2. Render a matchup hero, final projection/market overview near the top, sticky section nav, and synchronized QB-left/QB-right rows for profile, defense, pressure, weapons, projection, probability, and market. Render the shared game environment once full-width.
3. Use two columns for tablet/desktop and responsive one-column stacking on narrow phones. Suppress duplicate legacy page/header output.
4. Add one NFL Passing Yards override to the existing `universal_runtime_v5_loader_v11.py`; all other destinations keep their current owners.
5. Keep Universal Runtime V5 on its existing V11 loader import.
6. Prove with focused tests plus existing Passing Yards/runtime regressions.

## Safety invariants
- Presentation only; no projection/probability/market/context math changes.
- Sportsbook projection influence remains 0.0; stake sizing remains off.
- Existing certified captured HTML is reused, not recomputed.
- No unrelated sport/market route ownership changes.
- No duplicate PR/proof/deployment/lease.

## Completion
Exact-head preview READY -> one Runless proof -> merge exact authorized head -> finalization ledger freeze/read-back -> release scope -> GREEN + FROZEN.
