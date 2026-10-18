# API 2 Universal Runtime V5 — Design

Date: 2026-10-17
Status: USER-DESIGN-APPROVED / WRITTEN-SPEC-PENDING-REVIEW
Repository: `kyrepeak/kyre-sports-ai`
Base main SHA at spec creation: `f5748cf102035cde773ffe4b2fc7f8dfdea1f7bf`

## 1. Purpose

API 2 currently has correct sports-page features, but the universal Streamlit navigation/runtime has accumulated multiple compatibility layers, rerun bridges, temporary monkey-patches, transition masks, legacy source execution, and page-local state cleanup. The observed production symptoms are:

- switching sports can feel slow;
- a previously active sport can remain visible underneath the newly selected sport;
- a stale page can finish rendering after the user already navigated elsewhere;
- the wrong game/page can occasionally appear after another selection;
- long browsing sessions can become less stable or feel progressively more sluggish;
- repeated navigation can leave stale runtime state that requires a reboot to recover.

The goal is to fix these problems once at the universal runtime layer without rebuilding the individual sports pages, projection models, data providers, or frozen page-specific behavior.

## 2. User-Approved Product Decisions

The following choices were explicitly approved during design review:

1. Keep Streamlit rather than migrate the visible frontend to React/Next.js at this stage.
2. Use an instant visual handoff: the outgoing page disappears immediately when a destination is tapped.
3. Preserve each sport's last market/game/page state, but keep inactive sports dormant.
4. Show the last verified cached view immediately when available, then refresh live data behind it.
5. Prefetch only one or two likely next destinations under a strict budget.
6. Latest tap always wins. Every navigation receives a new render/route generation, and older generations are forbidden from painting after supersession.
7. Use a staged Universal Runtime V5 cutover rather than replacing every legacy router in one production switch.
8. Require measurable performance budgets, long-session stress certification, and a single rollback switch before GREEN + FROZEN.

## 3. Current Architecture Problem

The current entrypoint and navigation stack intentionally preserve frozen historical behavior, but that preservation has created too many runtime owners.

At the current base:

- `app.py` seeds canonical route state, reads preserved legacy source from `app_legacy_entrypoint_v1.py`, rewrites the selected router import in memory, compiles the rewritten source, and executes it on Streamlit reruns.
- `streamlit_memory_lazy_router_universal_nav_v2.py` clears cross-route query/session keys and temporarily replaces renderer/import/markdown functions while delegating through older routers.
- `streamlit_memory_lazy_router_universal_nav_v4.py` adds callback-first route commits, transition masking, rerun-safe guard unwrapping, temporary `st.pills` replacement, legacy `selectbox` bridging, and root-render wrapping.
- individual sports routes remain layered through historical router successors and compatibility paths.

Those layers were individually justified when introduced, but together they allow too many moving parts to participate in a single tap. The runtime therefore needs one terminal authority above the existing pages.

## 4. Design Principle

The permanent rule for V5 is:

> Exactly one active route, exactly one active render generation, and exactly one universal route owner at any time.

State may persist across sports. Rendering may not.

A superseded generation may finish network or computation work, but it may not paint, replace active route state, change active widgets, or overwrite visible content.

## 5. High-Level Architecture

Universal Runtime V5 sits above existing sports pages and owns only cross-page runtime behavior.

```text
User Tap
  -> V5 Route Controller
  -> Commit canonical route + increment generation
  -> Retire outgoing render scope
  -> Mount destination shell immediately
  -> Restore destination sport vault
  -> Show verified cached snapshot if available
  -> Lazy-load selected destination only
  -> Start live refresh for current generation
  -> Accept refresh only if generation is still current
  -> Save refreshed snapshot
  -> Prefetch at most 1–2 bounded next destinations
```

Existing page modules remain responsible for their page-specific UI, data interpretation, projection logic, market logic, and existing frozen behavior. They no longer own cross-sport navigation.

## 6. Core Components

### 6.1 V5 Route Controller

The V5 Route Controller becomes the sole authority for:

- active `sport_id`;
- active `market_id`;
- active page/game/player route identity where applicable;
- canonical URL route state;
- route generation counter;
- active render scope identity;
- per-sport state vault selection;
- destination lifecycle transitions.

A tap creates a new immutable route intent and increments the generation.

Example:

```text
Generation 41: NFL / Rushing Yards / Game A
User taps NBA
Generation 42: NBA / Spread
```

Generation 41 becomes stale immediately. It may no longer paint to the active surface.

### 6.2 Render Generation Gate

Every active-page render and refresh receives the generation that authorized it.

Before any visible commit, callback mutation, late async result application, or active-state write, the operation must prove:

```text
operation.generation == runtime.current_generation
```

If false, the operation is discarded from the active surface.

This prevents:

- MLB content appearing under NFL after a later tap;
- a previous game replacing the currently selected game;
- late provider responses resurrecting an old page;
- stale callbacks mutating the active route.

The generation check must be centralized rather than reimplemented differently by each page.

### 6.3 Single Active Render Scope

V5 creates one render scope for the destination page.

On route change:

1. outgoing scope becomes `RETIRED`;
2. outgoing visible page surface is removed/covered immediately;
3. destination scope becomes `ACTIVE`;
4. only the active scope may render to the main page surface.

Leaving a page must reduce that page's live UI ownership to zero.

### 6.4 Per-Sport State Vaults

Each sport receives an isolated state vault.

A vault may contain:

- last selected market;
- last selected game;
- last selected team/player;
- manual date overrides;
- page-local filters;
- page-specific navigation state;
- last verified cached snapshot metadata;
- freshness timestamps;
- prefetch hints.

The active sport's vault may be mounted into the destination page. Inactive sport vaults remain stored but dormant.

The current V2 behavior of deleting outgoing sport-local state on cross-sport handoff must be replaced by a save/isolate model. Cross-sport state retirement should remove active UI ownership without destroying remembered state.

### 6.5 Verified Snapshot Cache

The cache exists to improve perceived navigation speed, not to silently serve stale live information as current.

Rules:

- only a previously verified/renderable destination snapshot may be shown instantly;
- each snapshot includes a timestamp, source/freshness metadata, route identity, and compatibility version;
- stale snapshots may be displayed only with an internal freshness state that triggers refresh;
- live refresh replaces the snapshot only if its generation is still current;
- a refresh for an inactive sport may update that sport's private cache, but may not touch the active page;
- page/model truth remains controlled by existing data/model rules.

TTL policy must be data-class aware. Schedule data can tolerate a longer TTL than live odds, live scores, injury/availability, or rapidly changing market data.

### 6.6 Lazy Destination Loading

The universal runtime must not import/render unrelated page modules merely because those routes exist in the navigation registry.

V5 should resolve the active destination to a lazy loader and import only the selected page plus its direct runtime dependencies.

Heavy providers, page-specific loaders, and model work should begin after the destination generation is committed.

### 6.7 Bounded Prefetch

Prefetch is optional acceleration and must never compete with the active page.

Rules:

- maximum 1–2 likely next destinations;
- no unbounded whole-site preloading;
- lower priority than active destination work;
- cancel/ignore prefetch if navigation pressure or active work requires resources;
- prefetch may populate verified snapshot/cache layers only;
- prefetch may not mutate active route state or visible UI;
- provider/API rate limits remain authoritative.

Likely candidates may include another market in the active sport or a likely adjacent game, but prediction complexity should remain intentionally small.

### 6.8 Immediate Destination Shell

The outgoing sport/page should stop being visible as soon as the new route is committed.

The destination should immediately display the persistent KYRE SPORTS AI shell/navigation plus a destination-specific loading/snapshot surface.

The user must never continue looking at a visibly interactive old sport while the new sport is already canonical.

### 6.9 Runtime Health Guard

V5 maintains lightweight health invariants and diagnostics:

- active route-owner count;
- active render-scope count;
- current generation;
- stale-generation paint attempts;
- stale callback attempts;
- wrapper/guard depth;
- route lifecycle count;
- route commit latency;
- shell-visible latency;
- cached-content-visible latency;
- live-refresh latency;
- module/import timing where useful.

If a rerun or hot reload leaves leaked V5 runtime state, the health guard may normalize V5-owned state back to one active owner/scope before rendering.

It must not silently rewrite page/model business logic.

A second simultaneous universal route owner is a hard regression signal, not a tolerated condition.

## 7. Page Lifecycle

Each route follows a controlled lifecycle:

```text
NEW
 -> ENTERING
 -> ACTIVE
 -> REFRESHING (optional, still ACTIVE)
 -> IDLE
 -> RETIRING
 -> DORMANT
```

A superseded generation transitions immediately toward `RETIRING/DORMANT` for UI ownership even if provider work is still finishing.

Required invariant:

```text
visible_active_scope_count == 1
```

for steady-state user-visible rendering.

## 8. Navigation State Model

V5 maintains two separate concepts:

1. **Global canonical route** — only one active route for the visible app.
2. **Per-sport remembered route** — each sport's last valid route for restoration.

Example:

```text
NFL vault: Rushing Yards / JAX vs BUF / selected player X
NBA vault: Spread / PHX vs LAL
Active route: NBA / Spread / PHX vs LAL
```

NFL remains remembered but cannot render until NFL becomes active again.

URL/query synchronization must follow the canonical route exactly once per committed navigation generation. Page-local URL keys from an outgoing sport cannot override the destination route.

## 9. Data Flow on Navigation

### 9.1 Same-Sport Navigation

1. tap destination market/game/player;
2. increment generation;
3. persist outgoing page state into current sport vault;
4. retire old page scope;
5. update canonical route;
6. show destination shell/snapshot;
7. lazy-load destination;
8. refresh if needed;
9. accept results only for current generation.

### 9.2 Cross-Sport Navigation

1. tap new sport;
2. increment generation;
3. save outgoing sport vault;
4. retire outgoing render scope immediately;
5. clear only active cross-route UI ownership/ephemeral keys, not remembered sport state;
6. restore destination sport vault or sport default;
7. commit canonical route/URL;
8. show destination shell/snapshot;
9. lazy-load only destination page;
10. refresh current destination;
11. prefetch bounded next destinations if idle.

### 9.3 Rapid Multi-Tap Navigation

If the user taps NFL, then NBA, then MLB quickly:

```text
Gen 51 NFL -> stale
Gen 52 NBA -> stale
Gen 53 MLB -> current
```

Only Gen 53 may paint. Generations 51 and 52 are not allowed to become visible later.

## 10. Performance Budgets

These are product targets and regression budgets, not promises that external providers can always meet.

- tap to canonical route commit: target <= 150 ms;
- destination shell visible: target <= 500 ms;
- verified cached useful content visible when available: target <= 750 ms;
- fresh live content: target approximately 1–2 seconds when providers permit;
- inactive sport page render work: 0;
- simultaneous universal route owners: exactly 1;
- simultaneous active page render scopes: exactly 1;
- stale generation paint commits: 0;
- wrapper/guard depth growth over repeated route changes: 0;
- repeated navigation must not show monotonic latency degradation caused by V5 runtime accumulation.

Measurements should distinguish provider latency from application routing/render latency.

## 11. Staged Cutover

### Stage 1 — Route Generation + Ownership

V5 becomes the terminal universal route authority while existing page implementations still render beneath it.

Goals:

- one route owner;
- generation IDs;
- immediate outgoing-page retirement;
- stale generation rejection;
- destination shell handoff.

### Stage 2 — Per-Sport Vaults + Cached Return

Introduce isolated remembered state and verified snapshot restore.

Goals:

- leave/return to sport without losing useful position;
- inactive sports remain dormant;
- cached return is immediate where safe;
- refresh cannot contaminate another active sport.

### Stage 3 — Lazy Loading + Bounded Prefetch

Move route resolution to lazy destination loaders and bounded prefetch.

Goals:

- reduce startup/route import cost;
- avoid touching unrelated sports modules;
- make likely next taps faster without API flooding.

### Stage 4 — Retire Redundant Universal Handoff Layers

Once V5 reproduces the required frozen behavior, remove or bypass redundant V2/V3/V4 universal handoff behavior from the active path.

Historical frozen source may remain in the repository for proof/compatibility. It should no longer be an active runtime owner once replacement is certified.

### Stage 5 — Long-Session Certification

Stress the final active path across all sports before freeze.

Required scenarios include:

- rapid cross-sport taps;
- repeated same-sport market changes;
- repeated game/player switching;
- back/forward URL behavior;
- mobile navigation;
- intentionally delayed provider responses;
- cached destination return;
- stale cache refresh;
- 30–60 minute simulated browsing session;
- repeated NFL -> MLB -> NBA -> CFB -> NFL -> WNBA -> MLB cycles;
- hot reload/rerun recovery;
- no duplicate navigation controls or leaked page bodies.

## 12. Rollback

V5 must have one explicit activation/rollback switch at the universal runtime boundary.

Rollback returns universal routing to the current certified pre-V5 terminal runtime without changing individual sports pages or models.

The rollback switch is not permission to run two routers at once. Exactly one universal route owner remains active in either mode.

## 13. Compatibility and Frozen-State Rules

- Existing frozen sports-page logic must not be reopened merely to adopt V5.
- Model math, projection ownership, sportsbook influence rules, player/team identity rules, and page-specific data contracts remain unchanged unless a proven compatibility defect requires a separately scoped fix.
- V5 adapters may translate canonical route/vault state into a page's existing expected session/query shape.
- Active-path compatibility shims should shrink as stages prove replacement behavior.
- Any frozen artifact touched during implementation requires exact thaw/forward-port/freeze handling through the existing control plane.
- Proof remains Runless-authoritative; no duplicate proof or GitHub Actions fallback should be introduced.

## 14. Failure Handling

V5 must fail safely:

- stale generation: discard active-surface commit;
- destination render exception: expose a destination error state rather than uncovering the outgoing page;
- cache decode/version mismatch: ignore cache and render fresh;
- provider timeout: retain valid cached snapshot when permitted and mark refresh unavailable/stale internally;
- duplicate route owner: hard diagnostic/regression failure;
- leaked V5 guard/scope after interrupted rerun: normalize V5-owned runtime state to one active owner;
- prefetch failure: never block active destination;
- rollback activation: single-owner fallback only.

## 15. Observability

Add structured route lifecycle timing/events sufficient to answer:

- what did the user tap?;
- what generation was created?;
- when was the outgoing scope retired?;
- when was the destination shell visible?;
- was cached content used?;
- when did live data finish?;
- was a stale generation discarded?;
- how many active owners/scopes existed?;
- did wrapper depth or route latency grow during the session?;
- which portion of latency came from application runtime versus provider/network work?

Diagnostics must remain lightweight enough not to become a new source of page latency.

## 16. Testing Strategy

Implementation is TDD-driven.

Minimum categories:

1. **Route controller unit tests** — generation monotonicity, latest-tap-wins, URL synchronization, remembered routes.
2. **Render gate tests** — stale generation cannot paint or mutate active state.
3. **Vault tests** — cross-sport state survives but remains isolated.
4. **Cache tests** — snapshot compatibility/freshness and refresh rules.
5. **Prefetch tests** — max 1–2, lower priority, no active-state mutation.
6. **Lazy-load tests** — inactive/unselected sport modules are not imported/rendered.
7. **Lifecycle tests** — leaving page retires all live UI ownership.
8. **Self-heal tests** — interrupted rerun does not stack route owners/wrappers.
9. **Performance-budget tests/instrumentation** — route/runtime latency separated from provider latency.
10. **Cross-sport regression tests** — existing frozen page routing still reaches the correct owners.
11. **Browser/mobile stress certification** — repeated rapid taps and long-session behavior.
12. **Rollback test** — exactly one owner in V5 mode and exactly one owner in fallback mode.

## 17. Non-Goals

This project does not:

- migrate the frontend to React/Next.js;
- redesign every sports page;
- change projection formulas;
- replace sports-data providers solely for this runtime work;
- preload the whole website;
- create a general distributed task system;
- preserve an inactive page's live widgets/DOM just to make returning look instant;
- allow multiple route owners for compatibility.

## 18. Migration Safety

The staged rollout must use additive V5 modules/adapters first. Replacement of older universal runtime layers occurs only after equivalent behavior is proven.

Each stage should be independently certifiable and rollback-capable. A failed stage must not require reopening already-frozen sports pages.

## 19. Definition of Done

Universal Runtime V5 may be declared GREEN + FROZEN only when all of the following are proven on merged main:

- one universal route owner;
- one active render scope;
- latest tap always wins;
- stale generations cannot paint;
- outgoing page disappears immediately on route commit;
- per-sport remembered state restores correctly;
- inactive sports execute zero page render work;
- cached verified return works without misrepresenting freshness;
- bounded prefetch stays within policy;
- selected destination is lazy-loaded without unrelated sports render work;
- long-session stress does not accumulate wrapper depth, duplicate controls, stale route ownership, or monotonic runtime slowdown;
- performance instrumentation meets the agreed application-side budgets or records a clearly classified provider-bound exception;
- fallback switch is tested;
- all required regression suites pass;
- exact-head Runless proof succeeds;
- frozen registry/ledger read-back is complete;
- workstream lease is released;
- durable state is `GREEN_FROZEN`.

## 20. Expected End State

The user experience should be:

```text
Tap NBA
-> NFL disappears immediately
-> NBA shell appears immediately
-> last verified NBA view appears when available
-> NBA refreshes live
-> NFL remains remembered but dormant
-> late NFL work cannot become visible
```

After extended browsing, the same rules still hold. The website should feel like one coherent app rather than a chain of historical Streamlit routers.
