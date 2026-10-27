# API2 NFL Game Total Page 2 S-Tier V2 Design

## Intent
Turn NFL Game Total Page 2 from a development/debug-style analytics stack into the approved premium decision dashboard while preserving Page 1 and all certified projection owners.

## Goals
- Match the approved mockup hierarchy: hero summary, Why This Read, Market Context, Matchup History, Key Availability, Game Profile, Projection Range, Bottom Line, collapsed Data & Sources.
- Add exact-team matchup history when verified history exists.
- Keep sportsbook data comparison-only and matchup history context-only; both have model influence 0.0%.
- Remove visible STEP labels, raw event/market IDs, repeated source disclaimers, and the giant certification card from the primary UI.
- Preserve selected-game routing and Back to Game Totals.
- Preserve Page 1 source and visual output unchanged.

## Non-goals
- No model/projection formula changes.
- No stake sizing or wager execution.
- No Page 1 redesign.
- No ESPN, ESPN BET, or SGO dependency.

## Constraints
- API2 only; no MONSTER state or authority.
- Kyre Sports API remains the application-facing data gateway philosophy.
- Existing V8/V9/V10 analytics remain authoritative for scoring, pace, explosiveness, red-zone, environment, projection, and market read.
- NFL.com Official Injury Report may supply availability context; nflverse supplies matchup history.
- Historical closing total is shown only when a verified `total_line` exists; otherwise render semantic `—` and do not infer an O/U result.
- Historical context never feeds the projection.

## Approach
Chosen approach: additive successor `nfl_game_totals_hub_v12.py`. V12 reuses V11 Page 1 behavior exactly, builds a new Page 2 presentation surface, and routes the universal runtime Game Total adapter to V12. A small context helper owns matchup-history and availability normalization so presentation code stays focused.

Alternatives rejected: directly rewriting V11 would weaken the frozen Page 1 proof boundary; rebuilding analytics would duplicate already-certified V8/V9/V10 owners.

## Acceptance
The selected-game Page 2 renders all approved sections, no visible STEP labels or raw IDs, exact verified matchup history when available, semantic empty states otherwise, 0.0% influence locks, and working back navigation. Page 1 remains owned by `nfl_game_totals_page1_s_tier_v1` and its frozen card code is not modified.
