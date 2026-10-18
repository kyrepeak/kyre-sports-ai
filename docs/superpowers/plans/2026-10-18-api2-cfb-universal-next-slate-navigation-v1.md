# API 2 CFB Universal Next Slate Navigation V1

## Goal
Make every active CFB page inherit two shared navigation rules: finite game/player/team selectors are tap-only, and date-driven pages automatically resolve the nearest verified upcoming FBS slate instead of asking the user to hunt through a calendar.

## Step 2A authority
- Branch: `api2-cfb-universal-next-slate-nav-v1`
- Base main: `b66dbaf8373cdc7b53ba9154497f028dfbe80b73`
- Scope lease: `SCOPE-LEASE-D31956AE0607F22D21C7AB9B`
- One branch, one PR, one Runless exact-head proof, one merge, one closeout.

## Architecture
1. `cfb_universal_next_slate_navigation_v1.py` owns next-slate resolution and the read-only CFB date-input bridge.
2. The frozen `cfb_schedule_v1.games_for_date` remains the primary schedule owner.
3. If that owner returns no rows, navigation alone falls back to ESPN's FBS scoreboard (`groups=80`) to discover an upcoming date. Fallback data never enters any projection, probability, ranking, or sportsbook model.
4. `universal_runtime_v5_loader_v13.py` delegates to V12 and wraps CFB adapters only.
5. Existing `universal_tap_only_selector_v2` supplies popover/button finite selectors, while intentional free-text controls such as `Search team` remain typeable.
6. Runtime V5 changes exactly one loader import from V12 to V13.

## Invariants
- A slate qualifies only if at least one game is pregame/scheduled and its kickoff is strictly in the future.
- Live, halftime, final/closed/completed, cancelled/postponed, stale-pregame, and unknown-status rows cannot select a slate.
- Empty dates are skipped automatically up to the bounded scan horizon.
- If no verified upcoming slate is available, navigation fails closed rather than inventing a date.
- Non-CFB routes delegate unchanged to V12, preserving the frozen NFL universal future-navigation layer.
- No model, projection, probability, ranking, line, sportsbook, stake-sizing, team-ID, player-ID, or game-ID math changes.

## TDD evidence
- RED: focused contract failed 7/7 because V1/V13 did not exist.
- GREEN: 7/7 passed after the shared CFB layer and Runtime V5 handoff were implemented.
- Provider RED: NCAA schedule returned HTTP 200 with zero parsed upcoming games; an added fallback test failed as expected.
- Provider GREEN: 8/8 passed after adding ESPN navigation-only fallback.
- Live check at 2026-10-18T23:05Z resolved 2026-10-20 in under one second; ESPN confirmed three FBS pregame matchups on that date.
- Current-contract regression: compile + Runtime V5/universal navigation suite passes; legacy repo assertions tied to retired entrypoints are excluded rather than used to roll production backward.
