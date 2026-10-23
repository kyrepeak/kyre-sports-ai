# Universal Streamlit Regression Repair V1

## Goal
Repair the two regressions introduced by Universal Streamlit Navigation + Maximum-Speed Runtime V1 without rolling back same-tab/latest-tap speed behavior.

## Root cause
1. The speed terminal imports frozen Runtime V5 before the NBA PRA terminal overlay. That causes the navigation UI to initialize before PRA is injected into the NBA registry.
2. Page Experience Runtime V2 only renders the transition loading surface when the browser controller fails, while V1 rendered it on every real route transition.

## Requirements
- NBA PRA must appear in NBA navigation again and resolve through `nba_pra_runtime_v2`.
- Transition loading screens must appear on route changes again.
- Same-tab internal navigation remains active.
- Latest-tap generation remains active.
- No background prefetch.
- No sports model, probability, ranking, provider, odds, or data semantics change.
- CFB Top Picks V19 and existing NFL/NBA/CFB routes remain preserved.
- Forward-only successor; do not mutate frozen V2 runtime or V1 speed terminal.
