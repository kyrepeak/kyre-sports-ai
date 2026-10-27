# MONSTER WNBA PRA Upcoming-Only R2 Final-Card Guard

Authority: MONSTER ONLY.

## Goal
Close the last Page 1 path through which a live/final game could survive after the upstream schedule gate: the bottom Certified PRA Pick section.

## Root cause
V2 builds the final section from `payload.final_card`. When a final-card item no longer has a corresponding eligible player row, V2 still renders it using fallback values.

## Repair
Add a presentation-only V3 successor. Before delegating to the proven V2 final-section HTML, retain only final-card items whose exact `(player_name, line)` key exists in current eligible Page 1 rows.

## Frozen boundaries
- R1 status/tip-time schedule gate unchanged.
- No sportsbook/provider routing changes.
- No projection, probability, edge, qualification, ranking, or selection math changes.
- No Page 2 changes.

## Acceptance
1. stale final card + zero eligible rows => no Certified PRA Pick HTML;
2. wrong-line stale card => hidden;
3. exact player+line current row => final card still renders;
4. compatibility hub installs R1 upcoming gate first and then V3 Page 1 successor;
5. R1 upcoming-only regressions remain green;
6. exact head earns App-5204253 runless-final-gate before merge;
7. production browser confirms the final Atlanta @ Golden State slate cannot produce active Page 1 players, Top 3, or stale Certified PRA Picks;
8. final MONSTER freeze checkpoint is written/read back.
