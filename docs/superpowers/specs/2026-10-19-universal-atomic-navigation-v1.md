# Universal Atomic Navigation V1 — Design

## Goal
When a visitor switches sport, market, or canonical page route, the outgoing page must never remain visibly exposed behind the incoming page and no non-selected route may perform background destination loading.

## User-facing contract
- One route owns the content surface at a time.
- On a route change, the outgoing destination is immediately covered by an opaque KYRE SPORTS AI transition surface before the incoming destination is loaded.
- The universal KYRE SPORTS navigation remains the route authority.
- Only the selected destination module is loaded/rendered for the active route; route prefetch is disabled.
- Existing Runtime V5 generation/scope checks remain the stale-write guard so an obsolete route cannot commit after navigation moves on.
- The transition surface disappears only after the selected destination renderer finishes its commit.
- A failed destination load must not reveal the outgoing page beneath it.
- Ordinary reruns inside the same route must not show a full-page transition shield.

## Architecture
Add one terminal Streamlit overlay above the current NFL Daily Picks V3 terminal. It reuses the existing Universal Runtime V5 route/state/loader contracts and the current terminal loader chain, but owns the final render orchestration. Destination UI is rendered inside one `st.empty()` content slot. On route identity change, a separate fixed, opaque transition slot covers the destination area while the old content slot is cleared and the selected destination loads. The terminal intentionally does not call Runtime V5 bounded prefetch.

## Protected behavior
- Do not alter sportsbook/model/projection/probability logic.
- Do not change individual sport page implementations.
- Do not modify the existing Universal Runtime V5 core or current NFL/NBA terminal overlays.
- Keep Runtime V5 route generation/scope commit checks.
- Keep the existing fallback runtime behavior.

## Acceptance
1. A source/test contract proves no background prefetch call exists in the terminal active path.
2. A route-change test proves the transition is detected only when route identity changes.
3. A render-order contract proves the transition shield is emitted and destination slot cleared before `load_destination`.
4. A source/test contract proves destination rendering occurs inside a single content slot and the shield is removed only after render commit.
5. `app.py` activates the atomic terminal while preserving the current terminal as its upstream.
6. Existing Universal Runtime/navigation regression suites remain green.
