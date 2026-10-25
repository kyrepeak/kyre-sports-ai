# API2 NFL Rushing Page 1 Density R1 Design

## Intent
Keep NFL Rushing Yards Page 1 as the fast league-wide RB decision board, but remove the oversized/repetitive mobile composition shown in production so each player can be scanned in seconds.

## Goals
- Preserve player headshot, name, RB1/RB2 role, matchup, kickoff, team logo, Kyre projection, market state, edge/model state, L5, attempts/game, YPC, opponent rush-defense grade, and Full Analysis handoff.
- Make the Kyre projection the visual hero while the sportsbook line is pending.
- Replace the tall 2x2 MARKET/KYRE/EDGE/MODEL block with one compact projection hero plus a three-cell MARKET/EDGE/MODEL decision strip.
- Remove repeated pending copy: pending cards must not render multiple `WAIT` values.
- Keep exactly one concise pending message such as `Sportsbook line not posted yet • projection ready`.
- Compress supporting stats into one rail and reduce mobile card height materially without hiding information.
- Preserve whole-card navigation to the selected player's NFL Rushing Yards Page 2.
- Preserve the existing upcoming-games-only slate behavior.

## Non-goals
- No changes to Page 2.
- No model, projection, probability, ranking, RB-role, sportsbook/provider routing, canonical IDs, or Kyre Sports API changes.
- No direct provider dependency in the frontend.
- No SGO, ESPN, or ESPN BET.
- No fabricated market line, edge, probability, or fallback zero.

## Constraints
- API2 only; authoritative base is `refs/heads/api2-main` at `4c79978bab5d11455dada42f7949d6978c2dc099`.
- One authoritative task/branch/PR/proof path: `api2-nfl-rushing-page1-density-r1`.
- Preserve frozen `nfl_rushing_yards_simple_rb_grid_v1.py` and the prior terminal; implement an additive Page 1 V2 successor and an additive terminal overlay.
- `app.py` may only advance the production terminal import to the new NFL Rushing Page 1 successor.
- Existing Page 1 and Page 2 regression/source-policy tests must remain green.

## Approaches considered
1. Edit V1 CSS/card rendering in place. Rejected because V1 is an existing frozen baseline.
2. Add a V2 presentation successor that reuses V1 data/helpers plus a terminal overlay that shadows only `nfl/rushing-yards`. Chosen because it is additive, low-risk, and preserves Page 2 and all analytics behavior.
3. Redesign Page 1 into a new deep dashboard. Rejected because Page 1 should stay simple and league-wide; deep analytics belong on Page 2.

## Acceptance proof
A dedicated TDD contract must prove pending cards have one semantic pending message and zero `WAIT` duplication, projection-first hierarchy, compact three-cell decision strip, preserved quick-stat rail and Full Analysis navigation, V2-only NFL Rushing terminal activation, upcoming-games-only copy, no forbidden provider strings, and untouched frozen V1/Page 2 behavior.