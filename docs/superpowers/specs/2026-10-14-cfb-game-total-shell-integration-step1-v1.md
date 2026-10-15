# CFB Game Total Shell Integration Step 1 Specification

## Goal

Make College Football -> Game Total render inside the existing KYRE SPORTS AI College Football shell, so the visible Sport and CFB Market selectors remain part of the experience exactly as they do for the other CFB markets.

## Current problem

The current Game Total Page-1 route is selected from the shared College Football market dropdown, but once active it is handed to the historical exact Game Total direct-render owner. That owner calls the Game Total surface without going through the shared root shell, so the universal Sport / CFB Market controls disappear and the page feels like a separate application.

## Confirmed root cause

`streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py` delegates non-Page-2 Game Total rendering into a chain whose active Game Total owner (`streamlit_memory_lazy_router_v181`) short-circuits to `_render_exact_game_total_surface()`. This bypasses `streamlit_memory_lazy_router_v1.render_app()`, which owns the visible KYRE SPORTS AI shell and the Sport/Market selectors.

The certified CFB Over/Under and Top Picks routes already demonstrate the correct pattern: run the shared root shell, adapt the selector to College Football, and replace only the exact selected market renderer.

## Required behavior

1. College Football -> Game Total Page 1 must render through the shared `streamlit_memory_lazy_router_v1` shell.
2. The visible market selector must remain `🎯 CFB Market` and expose the current CFB market set: Moneyline, Over/Under, Game Total, Top Picks.
3. The active Game Total content owner remains `cfb_game_total_clean_page_v43`.
4. Selecting another CFB market from the shell must leave Game Total and delegate to that market's existing frozen owner.
5. Existing Game Total route-query persistence may be reused, but no new route identity scheme is introduced.
6. Exact selected-event Page 2 remains owned by `cfb_game_total_page2_step8_final_runtime_v1` and is not modified by this step.
7. The Page-1 Game Total model, projection, probability, schedule, data providers, sportsbook influence, and selected-event semantics remain unchanged.
8. Root-shell seams changed for one render must be restored in `finally`.

## Scope

Allowed mutation:
- `streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py` — Page-1 shell routing only, under an exact scoped thaw.
- one focused regression test for this repair.
- this spec/plan and one control-plane receipt/freeze record.

Protected / forbidden:
- `app.py`
- `cfb_game_total_clean_page_v43.py`
- `cfb_game_total_page2_step8_final_runtime_v1.py`
- Moneyline, Over/Under, and Top Picks product implementations
- NFL / MLB / WNBA product code
- model/projection/probability math
- schedule/event identity/data-provider semantics
- sportsbook projection influence

## Acceptance contract

Step 1 is GREEN only when an exact-head proof demonstrates that:
- Game Total Page 1 is routed through the universal CFB shell;
- current CFB market options remain available;
- Game Total still renders V43 content;
- non-Game-Total CFB markets remain delegated;
- selected-event Page 2 ownership is unchanged;
- shell seams restore after render;
- scoped regressions pass.

Step 1 is FROZEN only after exact-head proof, merge, merged-main verification, protected-state/freeze recording, lease release, and canonical read-back.

The RuntimeError shown after date selection is explicitly Step 2 of the broader repair mission and is not patched in this Step 1 unless new evidence proves it is caused by the shell-routing change itself.
