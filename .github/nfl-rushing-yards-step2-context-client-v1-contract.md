# NFL Rushing Yards Step 2 Context Client V1

This certification connects the existing Ground Game Lab to the already-deployed Kyre Sports API `nfl_rushing_yards_context_v1` contract.

## Authoritative identity

- Official ESPN event ID is required.
- Official ESPN team IDs are required.
- Official ESPN athlete IDs are required.
- Player and team names are display-only.
- Player-name matching is forbidden.
- Fuzzy identity is forbidden.
- Synthetic event, team, or player IDs are forbidden.

## Step 2 data surface

- Current-roster verified rushing workload.
- Carries, rushing yards, yards per carry, carries per game, rushing yards per game, rushing touchdowns.
- Explicit sample-game count and baseline season.
- Opponent run-front context: rushing attempts allowed per game, rushing yards allowed per game, yards per carry allowed, rushing touchdowns allowed per game.
- Current-season completed regular-season samples are preferred by the production API; prior regular season may be used only when explicitly labeled by the API contract.

## Permanent protections

- Certified NFL Passing Yards chain remains frozen and unimported.
- Rushing Yards projection engine remains OFF.
- Probability, Monte Carlo, EV, grading, ranking, recommendation, and stake sizing remain OFF.
- Rushing Yards sportsbook projection influence remains exactly 0.0%.
- No wagering actions are enabled.
- Schema, timestamp, safety, event, team, athlete, and reciprocal-opponent violations fail closed.
- Transient transport retry may repeat only the same exact official event ID.

## Production verification

The dedicated CI lane must verify both the local client contract and the hosted Render API status contract. It also performs one exact-event production probe using official ESPN event ID `401872925`; the probe must preserve exact team/athlete identities and all frozen safety semantics.
