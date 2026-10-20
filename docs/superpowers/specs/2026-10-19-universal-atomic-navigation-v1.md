# Universal Atomic Navigation V1 — Design

## Goal
When a visitor switches sport, market, or canonical page route, the outgoing page must never remain visibly exposed behind the incoming page and no non-selected route may perform background destination loading.

## User-facing contract
- One route owns the content surface at a time.
- On a route change, the outgoing destination is immediately covered by an opaque KYRE SPORTS AI transition surface before the incoming destination is loaded.
- The universal KYRE SPORTS navigation remains the route authority.
- Only the selected destination module is loaded/rendered for the active route; route prefetch is disabled in the atomic render path.
- Existing Runtime V5 generation/scope checks remain the stale-write guard so an obsolete route cannot commit after navigation moves on.
- The transition surface disappears only after the selected destination renderer finishes its current-generation commit.
- A failed destination load must not reveal the outgoing page beneath it.
- Ordinary reruns inside the same route must not show a full-page transition shield.

## Architecture
Atomic Navigation is terminal-agnostic. `app.py` stays on the current NFL Daily Picks V3 terminal. That terminal keeps ownership of its existing loader patches, then delegates final rendering to `universal_atomic_navigation_runtime_v1.render_atomic_app(frozen_runtime)`. The atomic runtime reuses Universal Runtime V5 route/state/scope/health/fallback contracts while owning only the final visual handoff. Destination UI renders inside one `st.empty()` content slot. On route identity change, a separate fixed opaque transition slot covers the outgoing surface, the destination slot is cleared before the selected destination loads, and background destination prefetch is not executed.

Future NFL Daily Picks V4 remains a separate workstream. Its terminal contract freezes/inherits V3, so it can inherit Atomic Navigation without this workstream modifying `app.py` or any V4-owned file.

## Protected behavior
- Do not alter sportsbook/model/projection/probability logic.
- Do not change individual sport page implementations.
- Do not change `app.py` ownership from the source-main V3 terminal.
- Do not modify any NFL Daily Picks V4-owned path.
- Keep Runtime V5 route generation/scope commit checks.
- Keep the existing fallback runtime behavior.

## Acceptance
1. A source/test contract proves no background prefetch call exists in the atomic runtime path.
2. A route-change test proves the transition is detected only when route identity changes.
3. A render-order contract proves the transition shield is emitted and destination slot cleared before `load_destination`.
4. A source/test contract proves destination rendering occurs inside a single content slot and the shield is removed only after a current-generation render commit.
5. `app.py` remains on the existing V3 terminal, while V3 delegates rendering to the terminal-agnostic atomic runtime.
6. A source/test contract proves the atomic runtime has no V3/V4 import ownership, allowing V4 to inherit V3 independently.
7. Existing Universal Runtime/navigation regression suites and Runtime V5 certification remain green.
