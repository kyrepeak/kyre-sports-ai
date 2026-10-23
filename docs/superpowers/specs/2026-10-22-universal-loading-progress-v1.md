# Universal Loading Progress V1 Design

## Intent
Keep the existing KYRE SPORTS AI universal loading takeover, but add a visible 0–100 progress value and determinate bar so users can tell how far the page transition has advanced.

## User goal
The loader must feel alive and informative without lying about elapsed time. Percentages represent completed universal runtime stages, not a guessed countdown.

## Selected approach
Use real stage-gated progress with CSS smoothing between stage values. The client overlay starts at 0% when a real page transition begins. The server runtime advances only when actual milestones complete: 15% route accepted, 35% destination adapter resolved, 70% destination payload/module loaded, 90% renderer about to commit, 100% successful current-generation commit.

## Alternatives considered
1. Timer-only 0–100 animation — rejected because it can reach a misleading value while the page is still loading.
2. Historical ETA model — deferred because reliable per-route timing history is not yet part of the universal runtime contract.
3. Stage-gated progress — selected because it is universal, truthful, lightweight, and preserves current speed architecture.

## Requirements
- Preserve the current dark grid / blue KYRE SPORTS AI loading design.
- Show a large readable integer percentage from 0% through 100%.
- Make the horizontal bar determinate and visually move to the same percentage.
- Start at 0% only for real page transitions, never local interactions.
- Advance only on real runtime milestones; no interval timer, no fake elapsed-time loop.
- Clamp any progress input to 0–100 and escape status/page text.
- Keep same-tab navigation, latest-tap-wins, stale-write guards, one-destination rendering, and no background prefetch.
- Preserve NBA PRA registration order, CFB Top Picks V19 routing, and the current NFL rushing terminal-route fix.
- Preserve browser back/forward behavior.
- No sports model, projection, probability, ranking, provider, sportsbook, or Kyre Sports API data semantics change.
- SGO, ESPN, and ESPN BET remain forbidden.

## Non-goals
- Do not estimate seconds remaining.
- Do not add page-specific provider progress.
- Do not mutate frozen V1/V2/V3 page-experience files or the current repair terminal.

## Failure behavior
If the browser controller cannot mount, the server-held loading takeover must still show the same stage percentage. If a navigation generation becomes stale, it must not advance or commit progress for the old destination.
