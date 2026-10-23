# CFB Game Total Page 1 Final Polish R1

## Goal
Keep Page 1 compact while adding only three scan-speed upgrades: NCAA-owned team identity/logo assets, explicit Over/Under probability labels, and a Kyre Sports API-owned market intelligence strip for exact-book consensus and independently verified line movement.

## Hard constraints
- Kyre Sports API is the only application-facing gateway.
- No SGO, ESPN, or ESPN BET in request/fallback/enrichment/verification/history/development/production paths.
- Frontend does not select providers, call provider sites, average conflicting lines, infer opening lines from first-seen data, fabricate values, or convert null to zero.
- Page 2, models, projections, probabilities, rankings, and selection logic remain unchanged.
- Team logos use NCAA official school assets derived from verified NCAA schedule slugs; presentation has a text/monogram fallback if an image fails.
- Consensus is an exact-line mode/cluster across current approved book quotes. Ties return `NO_CLEAR_CONSENSUS`; no averaging.
- Line movement appears only when an explicit independently verified opener is present. Otherwise return `OPENING_LINE_NOT_VERIFIED`.

## TDD
1. Prove RED for missing API enrichments and missing V3 presentation.
2. Add API-owned identity/consensus/movement fields.
3. Add compact V3 presentation and activate it through the existing CFB wrapper.
4. Prove focused + preserved regressions through Runless V2.
5. Exact-head PR/merge, deployment readback, immutable finalization ledger, GREEN_FROZEN closeout, lease release.
