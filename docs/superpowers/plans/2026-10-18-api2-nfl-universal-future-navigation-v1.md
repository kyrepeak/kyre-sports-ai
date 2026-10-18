# API 2 NFL Universal Future Navigation V1

## Goal
Make every active NFL page use tap-only finite selectors and expose only not-yet-started NFL games. Live, final, unknown-status, and stale-pregame games fail closed. When the current date has no future pregame games, the existing universal active-slate resolver rolls forward to the next verified date.

## Step 2A authority
- Branch: `api2-nfl-universal-future-navigation-v1`
- Base main at start: `31e29ae8781979fcfe5e24aaccfdacc0b8f005f4`
- Scope lease: `SCOPE-LEASE-A4DF9390B221916FD391EB48`
- One PR, one Runless proof, one merge, one finalization chain.

## Architecture
1. `nfl_universal_future_navigation_v1.py` owns future-only schedule filtering and the game-selector bridge.
2. `universal_runtime_v5_loader_v12.py` delegates all existing route ownership to V11 and wraps NFL adapters only.
3. Existing `universal_tap_only_selector_v2` supplies popover/button finite selectors so mobile software keyboards are not invoked for game/player/team choices.
4. The future-only wrapper temporarily patches both `nfl_hub_v1.load_nfl_slate` and already-imported direct aliases during the active NFL render, then restores them in `finally`.
5. Runtime V5 changes only its loader import from V11 to V12.

## Safety invariants
- Only `pre` / `scheduled` / `created` games can surface.
- A parseable kickoff must be strictly later than current UTC time.
- Unknown state, live/in-progress, halftime, final/closed/completed, and stale-pregame fail closed.
- Future verified dates with TBD kickoff may remain eligible; same-day TBD fails closed.
- Non-game selector values are not filtered; all finite NFL selectboxes remain tap-only.
- No projection, probability, market, sportsbook, ranking, model, or stake-sizing math changes.
- Non-NFL routes delegate unchanged to V11.

## Verification
- RED: focused test failed because `nfl_universal_future_navigation_v1` did not exist.
- Core local assertions cover live/final exclusion, stale pregame exclusion, ESPN `game_date + tip_et`, game-option filtering, player preservation, wrapper diagnostics, and direct-import restoration.
- Exact-head Runless proof must run compile, focused contract, tap-only regressions, active-slate regressions, universal navigation regressions, and Universal Runtime V5 certification.

## Completion
Exact-head preview READY → one Runless proof → exact authorized merge → authoritative GitHub merge read-back → finalization ledger freeze/read-back → scope release → durable `GREEN_FROZEN`.

Freeze token: `API2_NFL_UNIVERSAL_FUTURE_NAVIGATION_V1_FROZEN`
