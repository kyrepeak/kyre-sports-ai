# API2 NBA PRA Terminal Route Restore R1

## Scope
Restore only the active NBA/PRA terminal route to `nba_pra_runtime_v2` while preserving the existing CFB Game Total terminal and canonical NFL Rushing route ownership.

## Root cause
The current terminal delegated NBA/PRA through the CFB bootstrap loader chain, which still contained an older NBA PRA overlay that selected `nba_pra_page1_v1`. That reintroduced the legacy SportsGameOdds/Odds-API.io UI even though the current Kyre Sports API-only NBA PRA runtime already existed and live PRA data was healthy.

## Repair
- Terminal owns `nba/pra` directly.
- NBA/PRA loads `nba_pra_runtime_v2` and `render_nba_pra_runtime_v2`.
- The NBA/PRA branch does not consult the stale resolver.
- No SGO, SportsGameOdds, ESPN, or ESPN BET path is added.
- NFL Rushing and all unrelated routes remain unchanged.

## Proof
- RED regression reproduced before the repair.
- Exact-head compile gate passes.
- Focused terminal/page-sync/runtime tests: 17 passed.
- Gateway/no-ESPN/live-acceptance tests: 23 passed.
- Full NBA PRA test family: 160 passed.
- Live Kyre Sports API PRA market: 220 observations / 110 players, VERIFIED, no consensus averaging, 0.0 sportsbook projection influence.
- Live Page 1 API-only snapshot: 11 upcoming games / 103 PRA players / 206 matched observations, VERIFIED/OK.

## Freeze token
`API2_NBA_PRA_TERMINAL_ROUTE_RESTORE_R1_FROZEN`
