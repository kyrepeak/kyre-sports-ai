# API2 NFL Moneyline Page 2 War Room V1 Design

## Intent
Create a selected-matchup NFL Moneyline Page 2 that feels like a premium War Room while preserving the existing frozen Moneyline analytical chain. Page 1 remains the slate/consumer surface and gains only a navigation link into Page 2.

## Approved visual direction
War Room Hybrid: dark premium command-center layout, dense but readable, mobile-first, glacier-blue/teal accents, strong verdict hierarchy, no giant raw tables.

## Page 2 hierarchy
1. Matchup hero: teams, records, kickoff/venue, best moneylines, Kyre pick, model win probability, market probability, model edge, confidence/final state, price ceiling context.
2. Why Kyre Likes This Side: 3-5 deterministic evidence bullets, biggest reason to bet, biggest reason the pick could lose.
3. Team-v-Team Advantage Board: strength index, scoring offense, scoring defense, recent form, and QB/availability; only verified metrics, semantic empty when unavailable.
4. Matchup History: last 5 verified meetings by default, full verified history in a collapsed expansion, series snapshot, average margin, and a history insight. History is presentation context only and has model influence 0.0.
5. Expected Game Script: favored-side win path and opponent upset path derived only from frozen profiles/context.
6. Key Player Availability: existing verified QB/injury/depth context; no invented player status.
7. Recent Form & Situational Intel: records/profile evidence already owned by the frozen chain.
8. Market Intelligence: existing frozen sportsbook snapshot, best prices, no-vig market probability, edge/EV; sportsbook influence on model P(win) remains 0.0.
9. 5M Simulation Lab: existing Monte Carlo output only; do not rerun simulation.
10. Risk / Upset Radar: deterministic risks from uncertainty, availability, market/data quality, and matchup evidence.
11. Final Verdict: frozen V8 grade/state and leader; no new grading thresholds.

## Data architecture
- Kyre Sports API remains the only application-facing gateway.
- Create `sports_api/api/nfl_moneyline_page2_v1.py` for Page 2 enrichment/normalization.
- Matchup history uses `sports_api.nfl_data_nflverse_v1` only. No SGO, ESPN, or ESPN BET.
- Missing history or context produces semantic empty states; never fabricate or convert missing values to zero.
- Frontend must not call external providers.

## Routing
- Create successor `nfl_moneyline_hub_v20.py` over V19.
- Page 1 stays visually/analytically owned by V19; V20 injects a `VIEW FULL ANALYSIS →` link for each matchup.
- Selected Page 2 URL contract: `?sport=nfl&market=moneyline&view=analysis&game=<canonical-game-id>`.
- `Back to Games` returns to `?sport=nfl&market=moneyline`.
- `universal_runtime_v5_loader_v21.py` changes only the NFL Moneyline module target from V19 to V20.

## Frozen boundaries
- No changes to V8 final grading, V7 edge/EV, V6 Monte Carlo, V5 market/no-vig math, V4.x probability/calibration, or V2/V3 availability ownership.
- `SPORTSBOOK_MODEL_INFLUENCE = 0.0` and `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0` stay invariant.
- Stake sizing stays OFF.
- Page 2 is presentation/enrichment only.

## Mobile acceptance
At ~390 px width: one selected matchup only, no horizontal page overflow, sections stack cleanly, last-five history remains readable, Full History collapses by default, and the final verdict is reachable without nested scroll containers.

## Step 2G acceptance
Before GREEN/FROZEN: certified feature artifacts are present on protected `main` and `api2-main`; the canonical live Streamlit URL renders Page 2 for an actual upcoming NFL Moneyline game; required War Room markers are visible; stale/wrong-sport/error markers are absent.