# API2 NFL Game Total Page 2 S-Tier V3 Design

## Intent
Upgrade selected-game NFL Game Total Page 2 from the certified V12 premium report into a compact decision-grade analytics command center while preserving all frozen Page 1, projection, provider-routing, and model-influence contracts.

## Product hierarchy
1. Game Intelligence hero: matchup, schedule/venue, Market Total, Kyre Total, Edge, Final Read, confidence/market/data status.
2. Game Script: certified model total plus team-score split only when an authoritative split is present; never derive a split from the total.
3. Why This Read: strongest certified drivers only.
4. Market Context: full verified quote/movement when available; otherwise one compact semantic state rather than a four-cell dash grid.
5. Projection Range: non-overlapping model and market callouts.
6. Matchup Edges: certified team offense PF/G vs opponent defense PA/G and scoring signal.
7. Total Drivers: certified projection adjustments classified into scoring-up, scoring-down, or neutral.
8. Matchup History: verified recent context only; compact semantic no-history state.
9. Key Availability: official context only; compact pending state if unavailable.
10. Game Environment: temperature, wind/gust, precipitation, venue, pressure/impact when present.
11. Bottom Line: compact executive summary.
12. Data & Sources: collapsed provenance/transparency.

## Hard contracts
- API2 only. No MONSTER authority/state/evidence.
- `nfl_game_totals_hub_v12` remains frozen and is a compatibility/presentation ancestry dependency.
- Page 1 remains owned by V11 / `nfl_game_totals_page1_s_tier_v1` and must render unchanged.
- Certified V8/V9/V10 analytics remain projection and market-read authorities.
- Kyre Sports API remains the application-facing data gateway. V13 adds no direct provider calls.
- No new ESPN, ESPN BET, or SGO dependency in V13.
- Sportsbook, matchup-history, and availability model influence remains exactly 0.0%.
- Stake sizing and wager actions remain OFF.
- Null is never converted to zero. No synthetic projected team scores, recent form, market movement, injury impact, or provider facts.
- Market data is comparison-only; Kyre projection remains the visual/analytical primary.

## Semantic zero-blank rules
- Missing verified market: `MARKET NOT VERIFIED YET` and a concise explanation; no empty quote grid.
- Missing matchup history: `NO RELEVANT RECENT HISTORY` / first-matchup semantic context; no giant unavailable card body.
- Missing official availability: `AVAILABILITY VERIFICATION PENDING`; no fabricated healthy/active designation.
- Missing authoritative team projected points: `TEAM SPLIT NOT CERTIFIED`; the certified model total remains visible.
- Missing historical/recent-form data: do not synthesize it from season averages.

## Visual rules
- Preserve navy/glacier-blue language.
- Reduce vertical whitespace/card padding on mobile.
- Numbers and analytical decisions are the primary hierarchy; headings are secondary.
- Avoid repeated borders and debug/certification prose.
- Projection-range market/model labels use separate callout lanes so near-equal values cannot overlap.
- Green = verified/favorable; yellow = neutral/pending; red = verified adverse/impacting. Unknown states are not colored as adverse.

## Acceptance
- New additive owner: `nfl_game_totals_hub_v13.py`.
- Universal NFL Game Total adapter routes to V13 while preserving explicit V12/V11/Page1 ancestry anchors.
- V12 and existing regression suites remain green.
- V13 targeted tests prove hierarchy, zero-blank states, no synthetic team split, certified matchup edges, total drivers, range-label separation, mobile compactness, and model-influence invariants.
- Step 2G requires protected-main merge, feature-scoped `api2-main` parity, live Streamlit proof, finalization ledger handoff, durable `GREEN_FROZEN`, and lease release.
