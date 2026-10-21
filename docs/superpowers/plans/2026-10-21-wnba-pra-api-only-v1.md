# WNBA PRA API-Only Multi-Source Repair V1

## Goal
Restore the WNBA PRA player board while keeping Kyre Sports API as the only application-facing gateway. FanDuel remains the primary player-prop source; DraftKings is queried only when FanDuel is empty or degraded. SportsGameOdds/SGO, ESPN, and ESPN BET are prohibited from the active request, fallback, enrichment, verification, and production path.

## Root causes
1. The active Streamlit bridge depended on the legacy Step-5O persisted snapshot endpoint, which rejected durable refresh because its old SQLite store contract was not configured even though the newer WNBA durable storage stack is healthy.
2. The direct FanDuel collector currently returns no usable PRA market for the verified Finals slate.
3. The legal fallback registry for this page had no active secondary source even though the repository already contained a certified DraftKings Step-19A transport.
4. DraftKings quote rows require event-participant enrichment by source event id before the existing WNBA schedule matcher can consume them.
5. The historical PRA model imports a legacy sportsbook namespace; the successor temporarily interposes an API-only compatibility module so the old provider implementation is never loaded on the active WNBA PRA request path.

## Implementation
- Add `sports_api/wnba_pra_market_gateway_v1.py` with ordered provider routing: FanDuel first, DraftKings second only when primary is empty/degraded.
- Preserve each exact sportsbook quote: provider, player, side, line, American odds, timestamp, and source event identity. Never average or synthesize lines.
- Enrich provider event participants inside Kyre Sports API before quote delivery.
- Add GET `/api/v1/wnba/pra/market-board` and mount it through the existing WNBA market router.
- Add `wnba_pra_api_market_bridge_v2.py`; Streamlit makes one Kyre API market-board read and no sportsbook request.
- Advance the compatibility route to `wnba_pra_hub_v3617.py` and keep existing projection/probability/ranking/selection math unchanged.
- Add provider-aware `wnba_pra_product_view_v3.py` so the page labels the actual selected sportsbook rather than hardcoding FanDuel.

## Verification evidence
- TDD RED: 10/10 focused contract tests failed before implementation because successor modules/wiring were absent.
- Focused GREEN: 10 passed.
- Nearby regression: 23 passed.
- Exact API HTTP smoke: 200 READY; FanDuel EMPTY; DraftKings READY; 30 PRA quote rows; 15 players; line averaging false.
- Streamlit bridge smoke: CONNECTED; 30 rows; 15 players; one verified game matched; zero unmatched games.
- Existing same-book/same-line pairing: 15 exact DraftKings PRA pairs across 15 players.
- Active compatibility-route import check: no SportsGameOdds/SGO or ESPN module loaded before the product model is invoked.

## Finalization
Use one PR, one exact-head Runless proof, expected-head merge, shared-host release promotion only after proof, public WNBA PRA browser verification, immutable finalization record, scope-lease release, then stop at GREEN + FROZEN.
