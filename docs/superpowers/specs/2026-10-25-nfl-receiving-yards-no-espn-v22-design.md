# NFL Receiving Yards V22 No-ESPN Design

## Intent
Make the live NFL Receiving Yards page fully compliant with the permanent API 2 source policy: Kyre Sports API is the only application-facing gateway and ESPN/ESPN BET/SGO are prohibited.

## Root cause
The frozen V21 presentation chain still depends on legacy ESPN event/team/player IDs, ESPN event summaries/game books, ESPN roster reconciliation, and ESPN CDN identity assets. The V1 projection also hard-requires numeric ESPN identities, so relabeling is not a real migration.

## Chosen architecture
Create a successor live path rather than mutating frozen V1-V21 history:
- nflverse games -> canonical Kyre game/team identity and upcoming-only schedule
- nflverse weekly rosters -> GSIS player identity, active roster, jersey, position, headshot
- nflverse weekly player summaries (`stats_player_week`) -> receiving workload, efficiency, opponent pass-defense context, and direct player-vs-opponent history with a bounded request-time footprint
- NFL official CDN -> team logos
- FanDuel direct -> display-only Receiving Yards market observations, reconciled to nflverse by exact team + jersey + position; no fuzzy player matching
- Kyre Sports API -> sole frontend data gateway
- projection V2 -> same formula discipline as V1 (expected receptions × weighted YPR, 65% player / 35% opponent) with canonical Kyre/GSIS identity instead of numeric ESPN IDs
- Streamlit V22 -> compact successor page; no direct provider network access

The weekly-summary transport follows the already-proven Rushing Yards fast-path philosophy rather than downloading full-season play-by-play on every cold request.

## Permanent invariants
- No SGO.
- No ESPN.
- No ESPN BET.
- sportsbook projection influence = 0.0.
- no sportsbook line averaging.
- no synthetic compatibility IDs.
- no fuzzy player identity.
- missing data uses semantic states; never fabricated zeros/blanks.
- started/final games are excluded from the live page.
- historical V1-V21 files remain untouched and cease to be live production owners.
- MONSTER untouched.

## Step 2A / Anti-Loop
One active problem, one branch, one PR, one exact-head proof path. Do not create duplicate proof/deployment work. Classify a failed authoritative result before patching.

## Step 2B acceptance
1. Live registry target is V22.
2. Dedicated Receiving adapter imports only V22.
3. V22 frontend imports Kyre gateway only and contains no provider URL/transport.
4. Kyre API mounts the no-ESPN slate V2 route and unmounts legacy Receiving context/market routers.
5. Universal API coverage points Receiving Yards to the new dedicated route.
6. New live Receiving production files contain no `espn`, `sgo`, or `espn bet` source dependency.
7. Projection formula weights remain 0.65/0.35 and sportsbook influence 0.0.
8. Market mapping is exact team+jersey+position and fail-closed when ambiguous.
9. Exact-head regressions + Step 2A/2D/2E pass, merge SHA deploys READY, coverage/health are GREEN.
