# NBA PRA Enrichment Without ESPN — Implementation Plan

**Goal:** Restore NBA PRA player identity, headshots, history, projections, probabilities, and edge KPIs through Kyre Sports API without ESPN or SGO, while preserving the working sportsbook market path.

## Architecture

Streamlit -> Kyre Sports API -> NBA data router -> best eligible provider for the requested data type.

The frontend never calls NBA Official, Basketball-Reference, Sportradar, SportsDataIO, ESPN, or SGO directly.

## Provider policy

- Identity/roster: NBA Official first; Sportradar then SportsDataIO only when configured. Canonical frontend identity is `KYRE_PLAYER_ID`, never a provider ID.
- History: NBA Official first; Sportradar/SportsDataIO when configured; Basketball-Reference is an allowed history fallback.
- Market odds: preserve the existing Kyre Sports API sportsbook feed and never average conflicting lines.
- ESPN: forbidden in this workstream.
- SGO: forbidden in this workstream.
- Failures are explicit: HEALTHY / DEGRADED / UNAVAILABLE. No silent `{}` collapse and no fabricated data.

## Implementation

1. Add a focused failing contract test proving: no ESPN/SGO active path, canonical IDs, provider health/fallthrough, history -> projection -> probability/edge, and Kyre-API-only frontend transport.
2. Add `runless_v2/nba_pra_enrichment_v1.py` with a typed provider router, canonical ID normalization, NBA Official primary attempt, configured licensed-provider slots, and Basketball-Reference history fallback. Provider-specific IDs remain metadata only.
3. Expose enrichment through the existing Kyre Sports API NBA router so no new frontend/provider path is created.
4. Add a small Streamlit-side Kyre API enrichment client and wire `nba_pra_page1_api_only_v1.py` to inject returned profiles while explicitly disabling the legacy ESPN backup path.
5. Remove the active SGO fallback from the Kyre market request path while preserving direct verified sportsbook data.
6. Run focused tests, full NBA PRA regression, universal runtime certificate, exact-head Runless proof, one merge, production read-back, and final freeze.

## Acceptance proof

- SGO not used.
- ESPN not used.
- Sportsbook odds still populate.
- Canonical player IDs resolve.
- Player enrichment/headshots resolve where a verified NBA ID is available.
- Game history populates from an eligible provider.
- Projection, probability, BEST OVER EDGE, and BEST UNDER EDGE populate.
- Provider failure falls through safely and explicit DATA_UNAVAILABLE is returned only after eligible providers are exhausted.
- Exact deployed HEAD verified with no NBA page regressions.
