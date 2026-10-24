# API2 CFB Moneyline Logo Rail R1 — Design

## Problem
The live CFB Moneyline Page 1 uses Streamlit `st.segmented_control` for matchup selection. On mobile this renders as a tall vertically stacked list, which is the exact UI shown in the user screenshots.

## Goal
Replace only the Moneyline matchup selector with a compact one-row horizontal swipe rail while preserving all existing V7 analytics and model behavior.

## Rail contract
Each matchup chip contains only:
- away team logo
- away abbreviation
- `@`
- home abbreviation
- home team logo
- Phoenix-local kickoff time on the second line

The repeated word `Phoenix` is omitted from each chip. The selected chip receives glacier-blue emphasis. Chips stay fixed-size, no-wrap, horizontally scrollable, and snap-aligned.

## Data ownership
The browser/application continues to use Kyre Sports API only. V8 requests team presentation identity from the existing `/api/v1/cfb/game-total/page1` Kyre Sports API contract, which owns approved NCAA identity assets. No ESPN, ESPN BET, SGO, or direct provider selection is introduced in V8.

If identity enrichment fails, the Moneyline page remains usable with monogram fallbacks.

## Integration
`app.py` is frozen and remains untouched. The existing production terminal `streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py` is the additive activation point. It intercepts only `cfb/moneyline`, loads V8, and preserves the existing NBA PRA, NFL Rushing, CFB Game Total, and fallback route chain.

V8 wraps V7 rather than copying the full page. During `render_moneyline_hub`, V8 temporarily replaces V7's segmented-control function with its HTML rail and captures the normal V7 payload for rail context. It restores all monkeypatched functions in `finally`.

## Frozen boundaries
- no model math mutation
- no probability mutation
- no ranking mutation
- no selection mutation
- sportsbook projection influence remains `0.0`
- Team Data, Model Audit, Sources, Full Slate remain V7-owned
- no `app.py` mutation
- no direct sportsbook/provider dependency in the frontend

## Verification
Focused V8 contract, Moneyline API/runtime tests, NBA PRA and NFL Rushing terminal-preservation tests, Python compile, Moneyline Page 1 source policy, and Streamlit gateway binding policy must pass. The known CFB Game Total V1 activation assertion and Moneyline live-API Streamlit dependency assertion are inherited legacy-policy drift and must be shown to reproduce on the untouched base before being classified non-regressions.
