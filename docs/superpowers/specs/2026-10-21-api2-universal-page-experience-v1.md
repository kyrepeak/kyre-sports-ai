# API 2 Universal Page Experience V1 — Architecture Design

**Status:** Draft for user review  
**Workstream:** `api2-universal-page-experience-v1`  
**Source main:** `077d3f6a79cf168735bf1a2cf71c138549e7c176`  
**Date:** 2026-10-21

## 1. Goal

Make two behaviors universal across the entire KYRE SPORTS AI website:

1. Every reachable page and subpage has one professional floating `↑ TOP` control that returns the visitor to the top of the active content surface.
2. Every page-to-page or deep-route transition that is not effectively instant hides the outgoing page behind a full-screen KYRE SPORTS AI loading surface until the selected destination is ready, so stale/old page backgrounds never remain visible.

This is a shared-shell/navigation feature. It must not be implemented as repeated page-level patches.

## 2. User-facing contract

### 2.1 Universal TOP

- Every reachable sports page, market page, game page, player page, Page 2/deep analysis page, Top Picks page, and future registered page inherits one `↑ TOP` control automatically.
- The control is fixed near the lower-right safe area, above mobile browser/UI collision zones.
- It is visually consistent with the black + glacier-blue KYRE SPORTS AI system.
- It remains unobtrusive near the top and becomes visible after meaningful downward scroll.
- One tap/click returns the active page to the top using smooth scrolling when supported.
- It must not focus a text field, trigger the software keyboard, change route state, or rerun sports-data logic.
- It must work on desktop and mobile.

### 2.2 Universal transition/loading shield

- Route/page transitions follow this lifecycle:
  `tap intent -> protect outgoing page -> resolve/load destination -> destination stable -> reveal destination`.
- Existing Universal Atomic Navigation V2 remains the frozen parent behavior.
- Keep the existing 140 ms anti-flash threshold: if the destination becomes stable before the threshold, the loader never visibly flashes.
- If the transition is still running after 140 ms, an opaque full-screen KYRE SPORTS AI loading surface covers the outgoing content.
- The loading surface must be fully opaque; no previous sport/page/card may be visible behind it.
- The surface shows a human destination label when available, such as `NBA PRA`, `NFL Passing Yards`, `CFB Game Total`, or `NBA PRA • Player`.
- The loader disappears only after the active destination returns to a stable/current-generation state.
- A destination failure must fail closed: do not expose the outgoing page underneath a failed/partial destination.

## 3. Coverage contract — literally every page

Coverage is registry/runtime-driven, not manually maintained per page.

The universal experience must apply to:

- sport-to-sport navigation;
- market-to-market navigation;
- Moneyline, Spread, Game Total, Over/Under, Top Picks, Daily Picks and equivalent game-line pages;
- player-prop markets including Passing Yards, Rushing Yards, Receiving Yards, Receptions, Passing TDs, PRA, Points, Rebounds, Assists and other registered props;
- game cards and game-detail/deep routes;
- Page 1 -> Page 2 analysis transitions;
- Page 2 -> Page 1/back transitions;
- player `Analyze` / open-analysis actions;
- browser back/forward (`popstate`);
- every current canonical route in the Universal Sports registry;
- every future canonical route that enters through the universal runtime/shell.

No page receives a special exemption merely because it was created earlier or uses a legacy renderer behind the universal runtime.

## 4. Non-navigation interactions

A full-page loader must not fire for ordinary in-page controls that do not change the owned page/view, including:

- Line Lab sliders;
- tabs/segmented controls that only change a local panel;
- local sorting/filtering;
- accordion/detail expansion;
- input controls;
- harmless reruns where the canonical/deep-page identity stays the same.

The universal classifier must distinguish `PAGE_TRANSITION` from `LOCAL_INTERACTION` before showing a long-lived transition shield. Fast false-positive pointer intent must be cancelled before the 140 ms threshold whenever the route remains local/stable.

## 5. Architecture

### 5.1 Preserve frozen parents

Do not rewrite Universal Atomic Navigation V1/V2 in-place as page patches. V2 is the behavioral parent for delayed opaque loading.

Create a new terminal-agnostic Universal Page Experience layer that composes/inherits the existing V2 navigation authority.

Recommended modules:

- `universal_page_experience_v1.py` — pure/shared browser-controller markup, TOP behavior, transition-intent classification and destination labeling extensions.
- `universal_page_experience_runtime_v1.py` — mounts the singleton controller before destination loading and delegates route rendering to the existing atomic/runtime authority.
- one terminal-chain integration seam so the current production runtime inherits the new universal experience without modifying individual sport page renderers.
- focused tests plus a route-coverage certification test.

Exact file names may be adjusted during implementation planning if the current terminal chain exposes a cleaner inheritance seam, but ownership must remain universal rather than page-specific.

### 5.2 One parent-window singleton

Install one idempotent controller on `window.parent`, following the existing V2 pattern.

It owns:

- transition overlay DOM;
- TOP control DOM;
- scroll observer/listener;
- pointer/navigation intent capture;
- Streamlit script-state observation;
- browser `popstate` handling;
- cleanup/idempotent refresh.

Repeated Streamlit reruns must refresh/reuse the existing singleton rather than stacking listeners or duplicate TOP buttons/loaders.

### 5.3 Transition classification

Classification priority:

1. **Known universal navigation:** sport/market controls are always `PAGE_TRANSITION`.
2. **Canonical URL/deep-route change:** route identity change is `PAGE_TRANSITION`.
3. **Shared deep-page actions:** Analyze/Open/View/Back actions that change the owned page/subpage are `PAGE_TRANSITION`.
4. **Browser back/forward:** always arm transition protection.
5. **Local controls:** sliders, inputs and stable-route panel actions are `LOCAL_INTERACTION` and do not retain the full-screen loader.

When intent is ambiguous, fail toward protecting visual correctness during a slow page transition, but cancel immediately when the runtime proves the active page identity did not change.

## 6. TOP control behavior

- DOM identity is singleton and versioned, e.g. `data-kyre-universal-top="v1"`.
- Hidden at/near page top; visible after a defined scroll threshold (implementation-plan default: 320 px unless testing shows a better safe threshold).
- Position: fixed lower-right safe area with responsive offsets.
- Touch target >= 44 px.
- Visual treatment: black/dark glass surface, glacier-blue border/text/accent, subtle shadow/glow, clear upward arrow.
- Uses the actual parent scroll owner; the implementation must detect/fallback between document/window and Streamlit's scroll container rather than assuming one browser layout.
- Clicking the control does not call Streamlit widgets, mutate session state, or cause a rerun.

## 7. Loading-screen visual contract

Use one premium universal loading treatment:

- fully opaque `#060b13` base;
- `KYRE SPORTS AI` glacier-blue brand label;
- human-readable destination name;
- lightweight animated glacier-blue pulse/progress treatment;
- no old-page transparency;
- no random team/player logo inherited from the outgoing page;
- no sportsbook/model values rendered in the loader;
- accessible `aria-live` semantics;
- reduced-motion-safe fallback.

The loader should feel intentional, not like a browser error or generic spinner.

## 8. Runtime safety

- Existing Runtime V5 generation/scope stale-write protection remains authoritative.
- No background destination prefetch is introduced.
- No duplicate route authority.
- No new async/polling loop; use event/state observers and one-shot timeout behavior.
- Controller installation is idempotent.
- No sports provider calls originate from this feature.
- No sportsbook/model/projection/probability logic changes.
- No Kyre Sports API routing changes.
- No SGO, ESPN or ESPN BET dependency is introduced.
- Existing frozen page behavior remains unchanged except for universal shell presentation/navigation protection.

## 9. Step 2A / anti-loop execution contract

Implementation uses exactly:

- one active problem: `Universal Page Experience V1`;
- one authoritative branch;
- one PR;
- one exact-head Runless proof path;
- one scoped lease set for universal-shell files;
- no duplicate proof requests;
- no retry of a failed proof without first classifying root cause;
- exact candidate/main provenance before merge/freeze;
- terminal durable read-back before `GREEN_FROZEN` is claimed.

If `main` advances for a disjoint workstream, the same PR may receive one successor candidate reconciled onto current main; the failed identity-drift proof remains immutable and is never retried.

## 10. Acceptance matrix

### A. Universal TOP

1. A registry-driven test enumerates every current reachable canonical sport/market route and proves the universal shell/controller is installed for each.
2. Deep player/game/Page-2 routes inherit the same controller.
3. Exactly one TOP control exists after repeated reruns/navigation.
4. TOP becomes visible after downward scroll and hides near the top.
5. TOP returns the active scroll surface to the top.
6. TOP does not trigger a Streamlit rerun or software keyboard.
7. Mobile viewport placement stays inside safe visible bounds.

### B. Universal loading/anti-bleed

8. Sport -> sport slow transition shows an opaque loader before old content can bleed.
9. Market -> market slow transition shows the loader.
10. Page 1 -> Page 2 slow transition shows the loader.
11. Page 2 -> Page 1/back slow transition shows the loader.
12. Player Analyze/open slow transition shows the loader.
13. Game/deep-route slow transition shows the loader.
14. Browser back/forward slow transition shows the loader.
15. Fast transition completing before 140 ms produces no visible loading flash.
16. A failed/slow destination never exposes outgoing content beneath a partial destination.
17. Loader destination labels are human-readable rather than raw IDs.
18. Old sport/team/page background elements are not visible while the loader is active.

### C. Local-interaction protection

19. Line Lab slider changes do not show a full-page loader.
20. Local sorting/filtering/stable-route controls do not retain a full-page loader.
21. Repeated reruns do not stack event listeners, overlays or TOP controls.

### D. Regression / ownership

22. Existing Universal Atomic Navigation V2 tests stay green.
23. Universal Runtime V5 route/generation/scope regressions stay green.
24. Current NBA PRA Page 1/Page 2 and every-player Analyze frozen regressions stay green.
25. Current NFL/CFB/WNBA/MLB registered-route smoke coverage stays green.
26. Production code compiles.
27. Proof scope shows no sport-model/provider files changed unless a universal terminal inheritance seam requires an explicitly reviewed one-line import/delegation change.

## 11. Definition of GREEN + FROZEN

This workstream is not complete because the code exists, a PR merges, or Vercel says Ready.

`GREEN_FROZEN` requires:

- all acceptance tests pass on one exact candidate SHA;
- Runless V2 exact-head proof succeeds with failure class `NONE`;
- immutable receipt binds the candidate/artifact map;
- authorized merge binds that candidate into main;
- merged-main provenance verifies exact candidate parentage;
- finalization/freeze ledger records the workstream and manifest state;
- canonical durable Runless read-back is `GREEN_FROZEN`;
- zero live Runless workstream leases;
- zero scope-aware execution holders for this workstream;
- no unresolved blocker or remaining implementation work.

Only then may the universal TOP + loading feature be called 100% GREEN + FROZEN.
