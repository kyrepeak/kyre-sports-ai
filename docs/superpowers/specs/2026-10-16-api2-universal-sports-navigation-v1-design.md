# API 2 Universal Sports Navigation V1 — Architecture Design

**Status:** Draft for user review  
**Repository:** `kyrepeak/kyre-sports-ai`  
**Design branch:** `api2-universal-sports-navigation-v1-design`  
**Design base:** `89eeeec30e4966d0e15100766b743af3591d4996`  
**Scope:** Navigation architecture and presentation only. No sports-model, probability, simulation, provider, or projection changes.

## 1. Intent

Kyre Sports currently exposes sport and market navigation through multiple Streamlit selectors and nested router overlays. On mobile this consumes too much vertical space and creates a fragmented mental model: the user selects a sport in one control, a market in another control, then may encounter additional page controls before seeing actual sports content.

The target experience is one universal, compact, sticky navigation layer shared by every current and future sports page. It must be visually clean, fast to switch, deterministic under Streamlit reruns, compatible with current frozen page/rendering workstreams, and able to migrate away from the legacy selector/router ownership model without a risky hard cutover.

Success means a user can move from any supported sports page to any other supported sport/market with one or two taps, never become trapped by stale query/session state, refresh or share the exact route, and see the same navigation model on phone, tablet, and desktop.

## 2. User-approved product decisions

The design incorporates the following approved requirements:

1. The universal sports navigation is sticky while scrolling.
2. Row 1 contains sports; Row 2 contains markets for the active sport.
3. Both rows use compact horizontal pills and may scroll horizontally on narrow screens.
4. The navigation remembers the last market used for each sport.
5. The universal navigation becomes the single navigation system for all current and future sports pages.
6. Page-level date selection remains below the sticky navigation.
7. Sport/market selection updates a clean canonical URL so refresh, bookmark, and share preserve the exact route.
8. Migration uses a safe cutover: the new navigation becomes the only visible navigation first, while existing routers remain temporarily as compatibility adapters.
9. Only sports and markets backed by working live pages appear.
10. The same two-row navigation pattern is used on mobile, tablet, and desktop.
11. A compact `KYRE SPORTS` brand/title remains inside the sticky header.

## 3. Current-state constraints

The current production entrypoint imports `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1`, which then delegates into an existing chain of frozen and compatibility routers. The repository also contains many sport/market-specific router layers that patch or intercept Streamlit `selectbox` behavior.

This design must therefore avoid a direct rewrite of frozen sports pages or model code. Universal Navigation V1 will sit above the current router stack as the single navigation authority and translate its canonical route into the legacy session-state keys expected by existing pages during migration.

The current repository pins Streamlit `1.64.0`. Universal Navigation V1 should use native Streamlit interaction primitives available in the pinned runtime and CSS for presentation/sticky behavior. It must not require a new frontend framework or a second SPA.

## 4. Non-goals

Universal Navigation V1 will not:

- change betting models, fair lines, Monte Carlo simulations, probabilities, provider ownership, team/player identity logic, or sportsbook-influence rules;
- redesign the body of individual sports pages;
- make non-live or incomplete sports/pages visible;
- delete all legacy router modules during initial activation;
- add cross-device account-level navigation preference sync;
- introduce a new JavaScript application shell;
- make page-specific controls such as date, matchup, player, or line selection universal unless a later design explicitly promotes them.

## 5. Target UX

The persistent header is:

```text
KYRE SPORTS

🏈 NFL   🏟️ CFB   🏀 NBA   ⚾ MLB   🏀 WNBA
Moneyline   Spread   Game Total   Passing   Rushing   …
```

The exact sports and markets are registry-driven. Only currently live destinations are rendered.

### 5.1 Sticky behavior

The complete navigation shell remains visible while the user scrolls. The brand is intentionally compact. The sport and market rows are horizontally scrollable when they exceed available width.

The sticky shell must not cover page content. The page body begins below a measured/known navigation height or equivalent Streamlit layout offset.

### 5.2 Active state

The active sport and market receive the existing black + glacier-blue visual language. Inactive pills remain visually quieter but retain accessible contrast and tap targets.

The UI must expose active state semantically where the selected native Streamlit control permits it, and keyboard focus must remain visible.

### 5.3 Date and page-level controls

Date remains directly below the universal header, owned by the active page/workstream. The universal navigation owns only sport and market selection in V1.

### 5.4 Per-sport last-market memory

Within the current browser/Streamlit session, each sport remembers its most recently selected live market.

Example:

- NFL → Spread
- NBA → Moneyline
- MLB → Slate
- switch back to NFL → Spread

V1 does not require persistence across a completely new browser session. A refresh/deep link remains stable through canonical URL state. Cross-session persistence can be considered later without changing the route contract.

## 6. Architecture overview

Universal Navigation V1 introduces one authority above all sport-specific routers:

```text
User tap / cold-start URL
          │
          ▼
Universal Navigation Controller
          │
          ├── validates route against Live Route Registry
          ├── applies precedence rules
          ├── remembers last market per sport
          ├── writes canonical URL only when necessary
          └── emits one canonical route intent
                         │
                         ▼
                Compatibility Adapter
                         │
                         ├── translates canonical sport/market to legacy keys
                         └── suppresses old visible sport/market selectors
                                      │
                                      ▼
                            Existing frozen router/page stack
```

The key invariant is:

> Exactly one component may decide the active sport and market: Universal Navigation Controller V1.

Legacy routers may consume translated state during migration, but they may not override a newer explicit universal-navigation selection.

## 7. Proposed components

The implementation plan may refine filenames, but the architecture requires the following responsibilities.

### 7.1 Live Route Registry

A declarative registry defines what Universal Navigation is allowed to show and route to.

Conceptual shape:

```python
SPORTS = {
    "nfl": {
        "label": "NFL",
        "icon": "🏈",
        "legacy_sport": "NFL",
        "default_market": "moneyline",
        "markets": {
            "moneyline": {
                "label": "Moneyline",
                "legacy_market": "Moneyline",
                "live": True,
            },
            "spread": {
                "label": "Spread",
                "legacy_market": "Spread",
                "live": True,
            },
        },
    },
}
```

Registry rules:

- IDs/slugs are stable machine identifiers and are not display labels.
- Display labels may change without breaking URLs.
- A destination is rendered only when `live=True` and its required compatibility target exists.
- New sports/markets register here instead of creating a new top-level selector owner.
- Registry validation must reject duplicate slugs, missing defaults, non-live defaults, and duplicate legacy identities.

### 7.2 Universal Navigation Controller

The controller owns state resolution and transitions. It should be mostly pure/testable logic, separated from Streamlit rendering.

Canonical state concept:

```text
active_sport_id
active_market_id
last_market_by_sport
route_source
navigation_epoch
```

Suggested Streamlit session keys may be namespaced such as:

```text
ks_universal_sport
ks_universal_market
ks_universal_last_market
ks_universal_nav_source
ks_universal_nav_epoch
```

Legacy keys such as `ks_sport_touch`, `ks_nfl_market_touch`, `ks_cfb_market_touch`, and `ks_nba_market_touch` remain adapter outputs during migration, not authorities.

### 7.3 Sticky Navigation Renderer

The renderer consumes the validated canonical route and live registry and renders:

- compact `KYRE SPORTS` brand;
- sport pill row;
- active-sport market pill row;
- horizontal overflow behavior;
- black + glacier-blue active styling;
- sticky container behavior across phone/tablet/desktop.

The renderer returns explicit user intent to the controller. It does not directly mutate legacy router keys.

### 7.4 Compatibility Adapter

The adapter maps a validated canonical route to the exact state expected by the existing nested router/page stack.

Responsibilities:

- set the legacy sport value corresponding to the canonical sport;
- set only the relevant legacy market key;
- avoid touching page-level keys such as date/game/player unless required to preserve an existing route;
- hide/suppress legacy top-level sport and market selectors so the user sees only Universal Nav;
- prevent nested query restorers from overriding a newer explicit universal-nav transition;
- preserve frozen page/model behavior.

The adapter is temporary architecture. It can be retired only after the corresponding destination is directly registered/rendered without relying on legacy navigation ownership.

### 7.5 Production Activation Overlay

Initial activation should be an outer additive layer above the currently booted production router. It should not rewrite previously frozen router modules merely to adopt the new navigation.

The production entrypoint changes only after the new controller, registry, renderer, adapter, and regression suite are certified.

## 8. Route precedence contract

A deterministic precedence order is mandatory to prevent the existing stuck/snap-back behavior.

Highest to lowest authority:

1. **Explicit Universal Nav tap in the current rerun**
2. **Canonical URL on cold start / when no newer in-session user intent exists**
3. **Remembered last market for the newly selected sport**
4. **Registry default market for that sport**
5. **Legacy query/session values only as migration inputs when no higher authority exists**

A lower-authority source must never overwrite a higher-authority route in the same navigation epoch.

## 9. Canonical URL contract

Universal Navigation owns canonical sport and market parameters.

V1 canonical format:

```text
?sport=nfl&market=spread
?sport=cfb&market=game-total
?sport=nba&market=spread
```

Page-specific state remains namespaced/preserved separately, for example:

```text
?sport=cfb&market=game-total&game_id=401234567
?sport=nfl&market=passing&player_id=12345&date=2026-10-18
```

Rules:

- `sport` and `market` are the only universal route parameters in V1.
- Route IDs use stable lowercase canonical slugs, not display labels.
- Legacy keys such as `ks_sport`, `ks_cfb_market`, `ks_nba_market`, etc. may be read during migration on cold start but are normalized into the canonical form.
- After normalization, legacy universal-navigation query keys are removed rather than kept as competing state.
- Page-specific parameters are preserved unless they are invalid for the newly selected destination.
- Query parameters are written only when the canonical target differs from the current canonical URL, preventing rerun/write loops.
- Invalid sport/market combinations fail closed to the nearest valid live route: valid sport + remembered/default live market, or global default live sport + its default market.

## 10. Sport switch behavior

When the user taps another sport:

1. Controller receives explicit `sport` intent.
2. Controller checks `last_market_by_sport[new_sport]`.
3. If remembered market is still live, it becomes active.
4. Otherwise the registry default market becomes active.
5. Canonical URL updates once.
6. Compatibility adapter translates the canonical route to legacy state.
7. Existing page stack renders the selected destination.

No sport-specific legacy router may subsequently snap the route back during that rerun.

## 11. Market switch behavior

When the user taps a market pill:

1. Controller validates that market belongs to the active sport and is live.
2. Controller sets active market.
3. Controller updates `last_market_by_sport[active_sport]`.
4. Canonical URL updates once.
5. Adapter applies legacy translation.
6. Destination renders.

## 12. Safe-cutover migration

### Phase A — Inventory and registry

Create the live route registry from verified current destinations. No navigation behavior changes yet.

### Phase B — Controller and renderer behind tests

Build canonical state resolution, route precedence, memory behavior, canonical URL normalization, and sticky renderer with no production activation.

### Phase C — Compatibility adapter

Map each registered route to existing legacy session/router expectations. Hide old visible sport/market selectors while keeping their rendering routes intact underneath.

### Phase D — Universal visible cutover

Activate Universal Nav as the only visible sport/market control on current live pages.

All currently registered routes must pass navigation regression proof before this phase can be marked GREEN + FROZEN.

### Phase E — Adapter retirement, later work

After route-by-route direct ownership exists, retire legacy selector interception and obsolete query restoration modules in separate bounded workstreams. Do not combine broad deletion with initial activation.

## 13. Failure and rollback behavior

Universal Navigation must fail closed.

If registry validation fails or the universal navigation layer cannot initialize:

- do not silently route to an arbitrary page;
- surface a deterministic navigation-unavailable state or delegate to the known frozen parent according to the implementation plan's approved fallback;
- do not partially mutate legacy session keys.

Initial activation must be reversible by restoring the previous production import/outer overlay. No sports model/data rollback should be necessary because those systems are not modified.

## 14. Compatibility rules for existing pages

During V1 migration:

- frozen sports-page rendering remains untouched unless a specific compatibility defect requires an explicit thaw/new outer overlay;
- existing date/game/player selections should survive market/sport navigation only when meaningful for the destination;
- sport-specific market names are translated in one adapter table rather than scattered across router patches;
- direct fast routes (for example NFL fast paths) must be tested so they cannot bypass the universal controller;
- old deep links continue to work during the migration window by normalization into canonical `sport`/`market` form;
- old selectors may still exist in frozen source but must not be visible or authoritative once Universal Nav is active.

## 15. New-page registration contract

After Universal Navigation V1 is active, a new sports page must not create a new global sport selector or independent route restoration owner.

A new destination instead provides:

- canonical sport ID;
- canonical market ID;
- display label;
- live/disabled status;
- default eligibility;
- compatibility/direct render target;
- any page-specific parameter schema.

This becomes a permanent architecture rule for future sports-page work.

## 16. Accessibility and responsive requirements

- Minimum practical tap target equivalent to existing mobile controls.
- Keyboard focus remains visible.
- Active state cannot rely on color alone where the chosen native control exposes selection semantics.
- Horizontal overflow must not trigger page-wide horizontal scrolling.
- Sticky header must respect narrow iPhone-class widths and desktop widths.
- Long market lists scroll independently within their row.
- The active pill should be scrolled into view after route changes when feasible with the chosen native primitive.
- Reduced-motion preferences should not be defeated by custom animation.

## 17. Performance requirements

The universal nav must remain lightweight:

- no sports data/API fetch is triggered merely to render navigation;
- registry is static/cached configuration;
- route transitions do not create duplicate async work;
- canonical URL writes are idempotent;
- controller logic is pure enough to test without booting every sports provider;
- compatibility translation occurs before expensive page rendering.

## 18. Testing and proof matrix

Implementation must use TDD and prove both state logic and real route integration.

Required test categories:

### Controller unit tests

- cold-start canonical deep link;
- invalid sport fallback;
- invalid market fallback;
- user tap beats stale URL;
- user tap beats stale legacy session keys;
- remembered last market per sport;
- remembered market removed from registry falls back to default;
- no duplicate URL writes for unchanged route;
- page-specific params preserved where valid.

### Registry tests

- unique sport IDs;
- unique market IDs per sport;
- every visible sport has at least one live market;
- default market is live;
- every live destination has a compatibility/direct target;
- no planned/disabled destination leaks into visible nav.

### UI/source tests

- `KYRE SPORTS` brand present;
- sports and market rows exist;
- sticky contract present;
- old visible sport/market dropdown ownership is suppressed after activation;
- date remains outside/below universal navigation.

### Integration regression matrix

Every registered live sport and market must be reachable from at least one different sport/market in the same session.

Minimum cross-sport transitions include:

- NFL → CFB → NFL and restoration of NFL last market;
- NFL → NBA → NFL;
- NBA → MLB → NBA;
- MLB → WNBA → MLB;
- CFB → NFL;
- refresh on canonical URL;
- old legacy deep link → canonical normalization;
- direct/fast NFL routes cannot bypass controller;
- CFB Game Total Page 1 → Page 2 retains the universal header and does not corrupt the selected universal market;
- browser back/forward behavior does not create a route tug-of-war.

### Responsive proof

At minimum certify representative narrow-mobile, tablet, and desktop widths. The implementation plan should reuse existing browser/proof infrastructure where possible rather than introducing a new test system.

## 19. Control-plane requirements

Implementation follows the current API 2 execution contract:

- one authoritative branch/PR/proof path per active implementation step;
- Step 2A before mutation;
- exact-head verification;
- Runless final-mile proof where supported;
- no duplicate async work or repeated polling;
- preserve unrelated active thaws/leases/workstreams;
- proof before merge;
- merge read-back;
- canonical finalization ledger/freeze;
- lease release;
- GREEN + FROZEN only after durable read-back.

The architectural work must not import live state from MONSTER or another workstream.

## 20. Proposed acceptance criteria

Universal Sports Navigation V1 is complete only when all of the following are true:

1. One visible sticky navigation shell is present across every registered live sports page.
2. Sport row and market row use compact horizontal pills.
3. Only live destinations appear.
4. Switching sports restores that sport's last-used live market for the current session.
5. Switching market updates canonical route state exactly once.
6. Canonical `sport`/`market` URLs refresh/share correctly.
7. Legacy deep links normalize without taking authority away from a newer user tap.
8. Old visible sport/market dropdowns are absent during normal navigation.
9. Existing page-specific date/game/player controls continue to function.
10. Frozen model/probability/provider behavior is unchanged.
11. Cross-sport and same-sport route regression matrix passes on supported proof infrastructure.
12. The initial activation can be rolled back by removing/restoring only the outer universal-navigation activation layer.
13. Final merged state is certified and GREEN + FROZEN under the API 2 finalization contract.

## 21. Architectural invariants

The implementation must preserve these invariants:

- **One route authority:** only Universal Navigation decides active sport/market.
- **Tap wins:** explicit current user intent outranks stale URL/session state.
- **Canonical URL, not competing URL state:** legacy navigation query keys are migration input only.
- **Registry-driven visibility:** if it is not registered live, it is not shown.
- **Adapters translate; they do not decide.**
- **Page controls stay page-owned.**
- **No sports math/data mutation.**
- **Safe cutover before deletion.**
- **New pages register; they do not create another global router owner.**

## 22. Design handoff

After the user approves this written spec, the next required step is to create a detailed implementation plan using the `writing-plans` workflow. No production implementation begins from design approval alone.
