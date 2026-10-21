# Universal Navigation Loading V2 — Design

## Goal
Whenever a site navigation interaction takes long enough to be perceptible, the outgoing page must stop being visible and a full opaque KYRE SPORTS AI loading surface must show the destination page name. If the destination resolves quickly, no loading flash should appear.

## User-facing contract
- Applies through the existing universal Runtime V5 terminal chain rather than page-by-page patches.
- Delay threshold: 140 ms.
- Slow transition: old content is fully covered by an opaque `#060b13` surface with destination name + `Loading`.
- Fast transition: timer is cancelled when Streamlit returns to `notRunning` before the threshold.
- CFB Player Props `Analyze` maps to `CFB Player Prop Intelligence Lab`.
- Game/player deep routes use human labels rather than raw query IDs.
- Browser back/forward participates through `popstate`.
- Toolbar/sidebar controls are excluded.

## Architecture
V1 remains intact as the frozen parent. V2 adds `universal_atomic_navigation_v2.py` and `universal_atomic_navigation_runtime_v2.py`. The browser controller is installed during every stable render and persists as a singleton on `window.parent`, allowing it to react to the next pointer-down before Streamlit starts the rerun. It observes `data-test-script-state`, normalizes the real camel-case Streamlit states, and uses a one-shot timeout rather than polling.

The existing NFL Daily Picks V3 terminal changes only its Atomic Navigation import from Runtime V1 to Runtime V2. V4, the NBA PRA terminal, and `app.py` continue inheriting through their current chain with no reimplementation.

## Safety
- No background destination prefetch.
- Existing Runtime V5 generation/scope `can_commit` and `commit_if_current` remain authoritative.
- No model/projection changes; sportsbook projection influence remains 0.0.
- Client script is singleton/idempotent; no repeated polling or stacked event listeners.
- If JavaScript mounting is unavailable, an opaque server fallback is used on canonical route transitions.
