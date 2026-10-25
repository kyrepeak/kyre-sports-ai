# API2 CFB Game Total Page 1 Readability R1 Design

## Intent
Keep the existing CFB Game Total Page 1 Decision Card structure, but make the matchup rail and selected-game card substantially easier to read on tablet/mobile.

## Goals
- Preserve the existing V5 horizontal logo rail and V6 Decision Card structure.
- Increase rail logos to ~42–50px, team abbreviations to ~16–18px, and kickoff text to ~12–14px.
- Increase selected-game logos to ~48–56px and team names to ~20–22px on larger screens, with readable tablet/mobile floors.
- Increase primary metric labels and values; primary totals should read at roughly 24–28px.
- Increase MODEL TILT, secondary market details, proof/freshness text, and OPEN ANALYSIS control by roughly 30–40%.
- Preserve Page 1 simplicity and keep deep analytics on Page 2.

## Non-goals
- No new analytics or data fields.
- No model, projection, probability, ranking, selection, provider, API, or Page 2 changes.
- No structural redesign of the page.
- No edits to frozen V5/V6 presentation modules.

## Constraints
- API2 only; authoritative base is `refs/heads/api2-main`.
- Create an additive `cfb_game_total_page1_atier_v7.py` successor.
- V7 must reuse V6 data/model/card logic and preserve `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0` plus all `MAY_MODIFY_* = False` boundaries.
- Bootstrap advances V6 -> V7 only.
- Mobile CSS must not reintroduce microscopic typography.

## Approaches considered
1. Edit V5/V6 CSS in place. Rejected because those predecessors are already frozen.
2. Add a V7 presentation successor with CSS scale overrides while reusing V6 logic. Chosen because it is additive, low-risk, and preserves all analytics behavior.
3. Redesign Page 1 into a new layout. Rejected because the user explicitly likes the current structure and wants only a readability/visual-hierarchy pass.

## Acceptance proof
A dedicated static contract must prove the V7 readability targets, V7 activation, V6 inheritance, zero model influence, and frozen boundaries. Existing V5/V6 Page 1 regression/source-policy tests must remain green.