# CFB Game Total Page 1 — Upcoming Rail Step 1 Design

## Intent
Keep CFB Game Total Page 1 simple and professional: users should see only games they can still act on, choose one matchup from a compact horizontal rail, and view the already-certified V3 market card for that selected matchup.

## Goals
- Kyre Sports API remains the only application-facing gateway.
- Hide every game at or after kickoff from pregame Page 1, including explicit-date requests.
- Exclude live/final/completed states before sportsbook routing so dead games do not waste provider calls.
- Add a compact horizontally scrollable matchup rail showing matchup, current O/U when available, and Phoenix kickoff.
- Render exactly one selected existing V3 analytics card under the rail; default to the earliest upcoming game.
- Preserve the selected game's existing OPEN ANALYSIS handoff to Page 2.

## Non-goals
- No Page 2 changes.
- No new projection, probability, ranking, selection, model, or sportsbook math.
- No provider expansion in this step.
- No redesign of the V3 analytics card beyond composing it beneath the rail.

## Constraints
- No SGO, ESPN, or ESPN BET request/source path.
- Kyre Sports API owns schedule filtering and final delivery.
- NCAA remains schedule/identity owner through the existing API contract.
- Sportsbook-specific lines remain separate; no averaging.
- Missing data is never converted to zero or fabricated.
- Page 1 remains America/Phoenix-facing.
- Existing frozen V3 behavior is preserved as the base; Step 1 is an additive successor plus the minimum activation seam.

## Approach
### Selected: API-first upcoming filter + additive V4 rail successor
The API filters dead games before market routing. A V4 Page 1 successor reuses V3 rendering helpers and shows a horizontal rail plus one selected V3 card. The current bootstrap wrapper activates V4 with a one-line successor pointer change.

### Rejected: presentation-only filtering
This could hide dead games visually but would still waste sportsbook calls and violate Kyre Sports API ownership of final delivery.

### Rejected: full Page 1 redesign in Step 1
That would prematurely build later hero/probability/reasoning steps and enlarge regression risk.

## Acceptance
Step 1 is GREEN only when tests prove: explicit-date started games are removed before market collection; future games remain; live/final semantic states are removed; V4 renders a horizontal rail; only one selected card renders; the default selection is earliest upcoming; the bootstrap activates V4; Page 2/model/projection boundaries remain unchanged.