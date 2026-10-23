# NFL Rushing Yards Page 1 Cleanup V1 Design

## Intent
Make NFL Rushing Yards Page 1 feel like a polished Kyre Sports market board: fast to scan, unmistakably team-aware, and visually lighter than the current box-on-box layout. Preserve the frozen Page 1/Page 2 architecture and all Kyre Sports API data ownership.

## Goals
- Keep every verified upcoming-game RB1/RB2 card on one league-wide board with no game-selection layer.
- Add subtle team identity without turning the page into a rainbow wall.
- Reduce card height and visual clutter while preserving market, projection, edge, model side, recent form, workload, YPC, rush-defense context, and Page 2 handoff.
- Make semantic empty states look intentional rather than broken.
- Keep the black/glacier-blue Kyre shell as the dominant visual language.

## Non-goals
- No projection, probability, ranking, sportsbook, provider, schedule, roster, role, matchup-history, or Page 2 analytics changes.
- No new external provider calls.
- No game selector or game-detail layer on Page 1.
- No replacement of Kyre Sports API as the application-facing gateway.

## Chosen approach: restrained team accents
Each card keeps the Kyre dark surface but receives team-specific CSS variables derived locally from canonical `team_abbr` presentation metadata. Team identity appears through a narrow left accent rail, player-photo ring, RB1/RB2 pill, compact team mark, and subtle border glow. The full card background does not switch to team colors.

This is preferred over full team-colored cards because 32 strong backgrounds would destroy scanability and visual consistency. It is preferred over a glacier-blue-only board because the user explicitly wants immediate team recognition.

## Card hierarchy
1. **Identity row:** player photo, player name, RB1/RB2 pill, team logo/abbr, opponent, kickoff.
2. **Single analytics strip:** Market / Kyre / Edge / Model, separated internally rather than four independent boxed cards.
3. **Scouting strip:** L5, ATT/G, YPC, and rush-defense difficulty in one compact row.
4. **Action:** `FULL ANALYSIS →`, visually clear without underlining every statistic.

## Team color behavior
- Static UI theme metadata only; never treated as sports/statistical data.
- Every NFL team has a deterministic primary/secondary/accent mapping.
- Accent selection favors a visible team-identifying color on the dark Kyre surface; very dark team primaries use a recognizable secondary/accent color.
- Unknown team abbreviations fall back to glacier blue.

## Semantic market behavior
For a verified market, show the sportsbook-specific line and book. For `MARKET_NOT_POSTED`, `LINE_CURRENTLY_OFF_BOARD`, or `DATA_UNAVAILABLE`, do not render a false numeric value.

A not-posted card should read deliberately:
- Market: `LINE PENDING`
- Edge: `WAIT`
- Model: `WAIT`
- Note: `Projection ready • sportsbook market not posted`

Projection may still render when independently ready. No `0`, `0.0`, `N/A`, generic `Unavailable`, or fabricated odds/edge may be introduced.

## Visual rules
- Remove broad inherited underlines from card content.
- Use color to communicate edge/model direction, not decoration everywhere.
- Positive edge / OVER: positive semantic class.
- Negative edge / UNDER: negative semantic class.
- Pending/wait states: muted amber/neutral class.
- Rush-defense difficulty: favorable / medium / tough / elite semantic classes.
- Preserve mobile one-column behavior and keep the analytics strip readable without horizontal scrolling.

## Header
Use:
- Kicker: `KYRE AI · NFL RUSHING YARDS`
- Title: `RB Market Board`
- Subtitle: current week/date span, active RB1/RB2 count, `upcoming games only`.

## Data contract preservation
The frontend continues to call only `load_rushing_yards_slate`, which targets Kyre Sports API. No SGO, ESPN, or ESPN BET dependency is added. Existing canonical IDs, upcoming-game filtering, automatic weekly rollover, sportsbook integrity, source lineage, semantic states, and Page 2 canonical player/game routing remain unchanged.

## Success criteria
- All 32 NFL abbreviations resolve to a deterministic team theme, with a safe fallback.
- A rendered card exposes team CSS variables and visible team identity accents.
- The card contains one analytics strip rather than four standalone metric boxes.
- Card-wide inherited underlines are suppressed; only intentional action styling remains.
- Verified positive/negative edges and OVER/UNDER states receive semantic classes.
- Market-not-posted cards show `LINE PENDING` + `WAIT` states and no fabricated zero.
- Header reads `RB Market Board` and `KYRE AI · NFL RUSHING YARDS`.
- Existing Page 2 query handoff and upcoming-games behavior remain covered by regression tests.
