# NFL Rushing Yards Page 2 Command Center V2 Design

## Intent
Turn NFL Rushing Yards Page 2 into the decision cockpit for a selected RB. Page 1 remains the fast scan surface; Page 2 explains exactly why the Kyre projection, edge, and Over/Under lean exist.

## Chosen approach
Use a **decision-first analytical command center**. The top of the page shows the actionable market decision, then progressively explains workload, recent form, opponent run defense, game script, matchup history, comparable matchups, advanced rushing efficiency, market integrity, personnel/availability context, and the final Kyre read.

This is preferred over a stat-dashboard-first layout because the user should know the decision immediately and then be able to audit the evidence underneath it.

## Goals
- Lead with player identity, role, opponent, kickoff, market line, Kyre projection, edge, side probability, confidence, expected carries, and expected YPC.
- Add verified workload intelligence: season carries/game, L3/L5 carries, team rushing-attempt share, workload trend, red-zone carries, goal-line carries, fourth-quarter carries, and leading/trailing rushing usage where supported by verified play-by-play.
- Add recent-form intelligence: L3/L5 averages, median, floor, ceiling, current-line hit rate when a verified market exists, and a clean game log.
- Expand opponent run-defense intelligence: attempts/yards/YPC allowed, rank/grade, explosive-run rate allowed, stuff rate, success rate allowed, and rush EPA allowed where verified inputs exist.
- Add game-script intelligence using verified football data only: team rushing volume and the player’s rushing usage while leading/trailing and in the fourth quarter. Do not invent spread/total/weather fields.
- Preserve verified RB-vs-defense history and add comparable-matchup history derived only from canonical verified games.
- Add advanced efficiency: explosive-run rate, stuff rate, rushing success rate, rush EPA/attempt, red-zone and goal-line usage where source columns exist.
- Keep sportsbook records independent. Current line/price may be shown only from the verified sportsbook observation already routed through Kyre Sports API. Opening line and movement must use semantic states until verified history exists.
- Add a deterministic final Kyre read: supporting factors, risks, and what is still unverified. No free-form fabricated facts.
- Keep source lineage visible.

## Data contract
Kyre Sports API remains the **only application-facing data gateway**. The existing Rushing Yards slate schema remains backward compatible; Page 2 fields are additive inside each card's `detail` object.

The frontend must never call a provider directly.

### Approved data behavior
- Canonical player/team/game identity remains mandatory before joins.
- Current sportsbook market remains book-specific and is never averaged into a fake universal line.
- NFLverse-derived analytics are permitted only from verified canonical play-by-play rows already routed inside Kyre Sports API.
- Missing inputs are never converted to zero.
- Semantic states are required for legitimately absent or not-yet-verified data.

## Page hierarchy
1. **Decision Cockpit** — player/team identity, RB1/RB2, opponent, kickoff, market, projection, edge, model side, probability, confidence, expected carries/YPC.
2. **Workload Intelligence** — season, L3/L5 carries, rush share, workload trend, red-zone/goal-line/4Q usage, leading/trailing usage.
3. **Recent Form** — L3/L5/season average, median, floor, ceiling, hit rate if market verified, game log.
4. **Opponent Run Defense** — yards/attempts/YPC allowed, rank/grade, explosive allowed, stuff rate, success rate allowed, EPA allowed.
5. **Game Script** — player/team rushing-volume context and semantic game-market/weather state when those fields are not verified.
6. **Matchup + Comparable History** — prior RB-vs-defense meetings and verified games against defenses in the same run-defense tier.
7. **Advanced Efficiency** — explosive rate, stuff rate, success rate, EPA/attempt, red-zone and goal-line share.
8. **Market Intelligence + Final Kyre Read** — book-specific price, market state, movement semantic state, evidence, risks, and source lineage.

## Semantic empty states
Use contextual labels such as:
- `First career matchup`
- `No comparable matchups`
- `Market not posted yet`
- `Opening line not captured by verified feed`
- `Movement history not captured by verified feed`
- `Weather verification pending`
- `Personnel verification pending`
- `No injury designation` only when an approved source explicitly supports that conclusion

Never display blank, `N/A`, generic `Unavailable`, or false zero.

## Non-goals
- Do not change Page 1.
- Do not change the projection model formula or allow sportsbook data to influence the model projection.
- Do not change RB1/RB2 derivation.
- Do not change upcoming-game filtering or automatic weekly rollover.
- Do not add a new direct frontend provider dependency.
- Do not use SGO, ESPN, or ESPN BET.

## Visual direction
Professional dark analytical terminal, compact hierarchy, fewer decorative boxes, strong typography, restrained team-color identity, one clear primary verdict, and tables/strips where comparison is more useful than isolated cards. Mobile must remain readable without horizontal page overflow.