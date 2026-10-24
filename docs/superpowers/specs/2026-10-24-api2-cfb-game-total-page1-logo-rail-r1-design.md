# API 2 CFB Game Total Page 1 Premium Logo Rail R1 — Design

## Goal
Upgrade the already-merged upcoming-game selector on CFB Game Total Page 1 into a compact premium horizontal matchup rail without changing the Kyre Sports API contract, Page 2, or any model/projection/probability/ranking/selection behavior.

## Matchup chip contract
Each chip contains only:
- away team logo
- away abbreviation
- `@`
- home abbreviation
- home team logo
- Phoenix-local kickoff time underneath

The rail must not include O/U, probability, confidence, edge, venue, sportsbook, consensus, line movement, or any other analytics. Those remain in the selected analytics card below the rail.

## Interaction
- one horizontal row only
- no wrapping
- touch swipe on mobile
- mandatory scroll snapping
- fixed compact 176px x 78px chips
- selected chip receives glacier-blue premium emphasis
- natural right padding leaves the next matchup partially discoverable on narrow screens
- selection remains on Page 1 through `cfbgt_game`
- `OPEN ANALYSIS` remains the Page 2 handoff

## Identity and logo ownership
Team identity is application-facing only through Kyre Sports API `team_identity`. The frontend makes no direct provider request. `logo_url` is rendered when present; `fallback_monogram`/team abbreviation remains underneath and becomes visible if the image is missing or fails to load.

## Frozen boundaries
- Kyre Sports API is the only application-facing gateway.
- No SGO.
- No ESPN.
- No ESPN BET.
- Sportsbook projection influence remains `0.0`.
- No model mutation.
- No projection mutation.
- No probability mutation.
- No ranking mutation.
- No selection mutation.
- No Page 2 mutation.
- Upcoming-only filtering from the merged V4 baseline remains intact.
- Existing V3 selected analytics card remains the deep card rendered beneath the selector.

## Success proof
1. RED test demonstrates V5/logo rail is absent.
2. V5 focused contract passes.
3. Python compilation passes.
4. CFB Game Total Page 1 source policy passes.
5. Relevant CFB Game Total Page 1 regression suite passes.
6. PR head equals tested exact head.
7. Merge uses expected-head protection.
8. Merged main receives a fresh regression proof.
9. Freeze token is persisted/read back from the frozen-artifact registry.
