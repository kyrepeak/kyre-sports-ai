# CFB Game Total Page 1 V2 — Step 3 Matchup Hero + Phoenix Time

## Goal
Replace the current Page-1 matchup/date presentation with the approved overview hero while preserving frozen Step 1/2 data/model behavior.

## Requirements
- `America/Phoenix` is the canonical display timezone.
- The Oct. 8, 2026 7:00 PM ET example must render as 4:00 PM AZ.
- Day choices are tomorrow-and-beyond only in Phoenix time.
- The hero includes teams, logos, records, conferences, venue/location, weather, precipitation, wind, Phoenix kickoff, and Overview / Full Analysis segmented presentation.
- Overview is active. Full Analysis is reserved for the later Page-2 build and must not fake a completed route.
- Preserve V35 multi-source display enrichment.
- Do not mutate projection/model/probability/ranking/qualification math.
- Sportsbook projection influence remains 0.0%.
- Do not edit frozen V35 or frozen Router V190.

## Implementation
1. Add a pure Phoenix/future-window presentation helper.
2. Add Page V36 over V35 and temporarily replace only V11/V14/V25 presentation seams during the render call.
3. Add a CFB-only activation hook that changes the in-memory `streamlit_memory_lazy_router_v190.GAME_TOTAL_PAGE` target from V35 to V36.
4. Call that activation hook from the existing unfrozen universal-shell runtime before `render_app()` executes.
5. Prove with the focused Step-3 test through Runless.
6. Merge exact head, reuse proof on merged main, atomically freeze/read back.

## Rollback
Reset the Step-3 branch to source main `0244ed0b203ad2996cb6d79409f69ba151029008`; frozen Step 1/2 artifacts are never modified.
