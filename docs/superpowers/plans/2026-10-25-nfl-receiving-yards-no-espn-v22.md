# NFL Receiving Yards V22 No-ESPN Implementation Plan

**Goal:** Move the live Receiving Yards page from the legacy ESPN-owned V21 data chain to a Kyre Sports API successor using nflverse/NFL official identity and history while preserving model behavior and sportsbook isolation.

## Task 1 — RED contract
- Add focused test for V22 live ownership, prohibited-source removal, projection invariants, exact market identity reconciliation, and Vercel mount/coverage ownership.
- Add exact-head GitHub Actions workflow.
- Verify the baseline fails because V22/API successor files do not exist and the live target is still V21.

## Task 2 — No-ESPN source owners
- Add direct FanDuel Receiving Yards adapter using canonical game context and exact team+jersey+position reconciliation metadata.
- Add Receiving projection V2 with V1-equivalent 65/35 efficiency formula and canonical Kyre/GSIS identity.
- Add Kyre Sports API Receiving Yards slate V2 using nflverse games, weekly rosters, and compact weekly player summaries (`stats_player_week`) plus NFL official team logos.
- Use those summaries for receiving workload, opponent defense, and verified player-vs-opponent history without a full-season play-by-play cold-path dependency.
- Exclude started/final games.
- Expose semantic market/provider states and 0.0 sportsbook projection influence.

## Task 3 — Frontend successor
- Add Kyre-only gateway client.
- Add compact V22 Streamlit page showing matchup, player identity, projection, market, defense and verified player-vs-opponent history.
- No direct external provider calls in frontend.

## Task 4 — Production ownership
- Repoint Step 2E registry and dedicated runtime adapter from V21 to V22.
- Mount slate V2 in `kyre_sports_api_vercel_v1.py` and remove legacy Receiving context/market mounts.
- Update universal router coverage dedicated path.
- Advance the existing Receiving canonical-router regression from the superseded V21 literal to V22.

## Task 5 — Exact-head verification and freeze
- Focused tests must pass.
- Relevant Step 2A/2D/2E and hardened NFL router workflows must pass on the exact branch head.
- Review diff for scope.
- Merge with expected-head protection.
- Verify `api2-main` merge SHA, post-merge Step 2D, exact-SHA Vercel READY deployments, `/health`, and `/api/v1/router/coverage`.
- Only then declare GREEN + FROZEN.
