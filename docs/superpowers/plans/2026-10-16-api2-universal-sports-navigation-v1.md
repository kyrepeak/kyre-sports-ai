# API 2 Universal Sports Navigation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the visible per-page sport/market dropdown experience with one sticky two-row KYRE SPORTS navigation authority that remembers each sport's last market, owns canonical `sport`/`market` URLs, and safely drives the existing frozen router stack through compatibility adapters.

**Architecture:** Add a small data-only live-route registry, a pure route controller/URL codec, a Streamlit sticky renderer, and one additive production activation overlay above the currently booted router. The overlay resolves Universal Nav state before legacy routers run, translates canonical state into existing `ks_*` session keys, suppresses only legacy top-level sport/market selectors, and delegates all page rendering to the frozen/current parent until later adapter-retirement workstreams.

**Tech Stack:** Python 3.13, Streamlit 1.64.0, pytest, existing Runless V2 proof plane, existing Streamlit session/query state.

**Spec:** `docs/superpowers/specs/2026-10-16-api2-universal-sports-navigation-v1-design.md`

## Global Constraints

- Navigation architecture/presentation only; no betting model, fair-line, Monte Carlo, probability, provider-ownership, identity, or sportsbook-influence changes.
- Universal Navigation V1 is the only authority allowed to decide active sport and market after activation.
- Explicit Universal Nav intent outranks canonical URL, remembered market, registry default, and legacy state in that order.
- Canonical universal URL keys are exactly `sport` and `market`; legacy `ks_*` query keys are migration inputs only.
- Current-browser-session last-market memory is required; account/cross-browser persistence is not.
- Page controls such as date, game, player, and line remain page-owned and below/outside Universal Nav.
- Only verified live destinations are visible. `MLB -> 2+ Hits` is not live in the current root router and must not appear.
- The same sticky two-row pattern is used on mobile, tablet, and desktop; rows scroll horizontally rather than causing page-wide overflow.
- Initial activation is additive and reversible; do not rewrite/delete frozen router modules in V1.
- Existing direct/fast routes must not bypass the controller.
- New sports/pages register with Universal Nav instead of creating another global sport selector/route authority.
- Use TDD for every implementation task, one authoritative branch/PR/proof path, Runless final-mile where supported, exact-head verification, proof before merge, merge read-back, finalization ledger/freeze, and lease release.
- No GitHub Actions fallback is introduced by this plan.

## Review Focus

1. **Browser back/forward after an in-session tap:** canonical URL navigation must not let an older legacy query/session route snap the app backward on the next rerun. Task 2 adds precedence/epoch tests; Task 3 adds normalization tests.
2. **Legacy page-level parameters on cross-sport switches:** `game_id`, `player_id`, and `date` must be preserved only when valid for the destination and otherwise dropped by explicit allowlists. Task 3 pins both preserve and discard behavior.
3. **Hidden legacy selectors accidentally swallowing page controls:** selector suppression must match only known top-level sport/market labels/keys and must delegate date/player/game selectors unchanged. Task 4 adds positive and negative bridge tests.
4. **A direct NFL/CFB fast route bypassing Universal Nav:** activation must resolve/apply canonical state before delegating and prove direct route modules see translated state. Task 6 adds direct-fast-path integration tests.
5. **Registry drift when a legacy route disappears or a new route is added:** registry validation must fail closed for missing/duplicate targets, and visible-route inventory tests must deliberately require an explicit registry update. Task 1 owns this contract.

---

## File Structure

**Create**
- `universal_sports_nav_registry_v1.py` — immutable/data-only live sport+market registry and validation helpers.
- `universal_sports_nav_controller_v1.py` — pure canonical state resolution, per-sport last-market memory decisions, precedence/epoch logic.
- `universal_sports_nav_url_v1.py` — canonical query parse/normalize/write plan with page-param allowlists and legacy-query migration.
- `universal_sports_nav_compat_v1.py` — canonical-to-legacy session translation and narrow legacy-selectbox suppression bridge.
- `universal_sports_nav_ui_v1.py` — sticky KYRE SPORTS renderer using native Streamlit controls plus scoped CSS.
- `streamlit_memory_lazy_router_universal_nav_v1.py` — additive outer activation overlay; controller → URL sync → adapter → renderer → frozen parent.
- `tests/test_universal_sports_nav_registry_v1.py`
- `tests/test_universal_sports_nav_controller_v1.py`
- `tests/test_universal_sports_nav_url_v1.py`
- `tests/test_universal_sports_nav_compat_v1.py`
- `tests/test_universal_sports_nav_ui_v1.py`
- `tests/test_streamlit_memory_lazy_router_universal_nav_v1.py`
- `devsystem/runless_proof_plans/api2-universal-sports-navigation-v1.json`

**Modify**
- `app.py` — production import moves from `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1` to `streamlit_memory_lazy_router_universal_nav_v1` only after Tasks 1–6 are green.

**Read-only compatibility dependencies**
- `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`
- `streamlit_route_hygiene_v1.py`
- `streamlit_memory_lazy_router_v1.py`
- `cfb_hub_v1.py`
- `streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py`
- direct/fast NFL and CFB router modules reached by the current parent chain.

---

### Task 1: Live Route Registry and Validation Contract

**Files:**
- Create: `universal_sports_nav_registry_v1.py`
- Create: `tests/test_universal_sports_nav_registry_v1.py`

**Interfaces:**
- Produces: `MarketRoute`, `SportRoute`, `SPORTS`, `DEFAULT_SPORT_ID`, `get_sport(sport_id: str) -> SportRoute | None`, `get_market(sport_id: str, market_id: str) -> MarketRoute | None`, `visible_sports() -> tuple[SportRoute, ...]`, `validate_registry() -> tuple[str, ...]`.
- Later tasks consume stable canonical IDs, legacy labels/session keys, defaults, and page-param allowlists from this module.

**Registry decisions locked by this plan:**
- `DEFAULT_SPORT_ID = "mlb"` to preserve the current root router's fresh-session default semantics.
- Sport order: `nfl`, `cfb`, `nba`, `mlb`, `wnba` for the visible bar.
- Defaults: NFL `slate`; CFB `moneyline`; NBA `spread`; MLB `slate`; WNBA `pra`.
- NFL live markets: `slate`, `moneyline`, `spread`, `game-total`, `passing-yards`, `rushing-yards`, `receiving-yards`, `receptions`, `passing-tds`, `anytime-td`, `daily-picks`.
- CFB live markets: `moneyline`, `over-under`, `game-total`.
- NBA live markets: `spread`.
- MLB live markets: `slate`, `one-plus-hit`, `home-run`, `hits-runs-rbis`, `pitcher-strikeouts`, `matchup-explorer`, `daily-game-picks`, `moneyline`, `run-line`, `game-total`, `live-game`, `live-odds`. Do **not** register `two-plus-hits` because the current root route explicitly reports the standalone route unbuilt.
- WNBA live markets: `points`, `rebounds`, `assists`, `rebounds-assists`, `pra`, `spread`, `moneyline`, `game-total`, `daily-picks`.
- Legacy sport labels: NFL `NFL`; CFB `College Football`; NBA `NBA`; MLB `MLB`; WNBA `WNBA`.
- Legacy market values use the current authoritative labels exactly (`Passing Yards`, `Over/Under`, `Hits + Runs + RBIs`, etc.).
- MLB `live-odds` maps to `ks_mlb_live_odds_route=True`; all other MLB markets clear that flag before delegation.

- [ ] **Step 1: Write failing registry tests**

Add tests asserting the exact sport order/defaults above, canonical-to-legacy labels, exclusion of `two-plus-hits`, NBA `spread` only, unique slugs, live defaults, unique legacy identities, and every visible market having a compatibility target.

- [ ] **Step 2: Run registry tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_sports_nav_registry_v1.py`
Expected: FAIL because `universal_sports_nav_registry_v1` does not exist.

- [ ] **Step 3: Implement registry data types and helpers**

Create immutable dataclasses:

```python
@dataclass(frozen=True)
class MarketRoute:
    id: str
    label: str
    legacy_market: str
    legacy_market_key: str
    page_params: tuple[str, ...] = ()
    live: bool = True
    legacy_flags: tuple[tuple[str, object], ...] = ()

@dataclass(frozen=True)
class SportRoute:
    id: str
    label: str
    icon: str
    legacy_sport: str
    default_market_id: str
    markets: tuple[MarketRoute, ...]
```

Implement the exact registry decisions above and pure validation; do not import sports providers or render modules.

- [ ] **Step 4: Run registry tests and confirm GREEN**

Run: `python -m pytest -q tests/test_universal_sports_nav_registry_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit Task 1**

Commit message: `feat: add universal sports live route registry`

---

### Task 2: Canonical Controller, Precedence, and Per-Sport Memory

**Files:**
- Create: `universal_sports_nav_controller_v1.py`
- Create: `tests/test_universal_sports_nav_controller_v1.py`
- Read: `universal_sports_nav_registry_v1.py`

**Interfaces:**
- Consumes: registry lookup/default interfaces from Task 1.
- Produces: `RouteState`, `RouteIntent`, `resolve_route(...) -> RouteState`, `apply_sport_intent(...) -> RouteState`, `apply_market_intent(...) -> RouteState`, `remembered_market(...) -> str | None`.

Use these exact value types:

```python
@dataclass(frozen=True)
class RouteState:
    sport_id: str
    market_id: str
    source: str
    epoch: int
    last_market_by_sport: Mapping[str, str]

@dataclass(frozen=True)
class RouteIntent:
    sport_id: str | None = None
    market_id: str | None = None
    source: str = "none"
```

Valid `source` values: `tap`, `canonical_url`, `memory`, `default`, `legacy`.

- [ ] **Step 1: Write failing controller tests**

Cover: fresh default (`mlb/slate`), valid canonical cold-start, explicit tap beating stale canonical URL, tap beating legacy values, sport switch restoring remembered market, missing/removed remembered market falling back to sport default, market tap updating only that sport's memory, and monotonically increasing epoch only when canonical route changes.

- [ ] **Step 2: Run controller tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_sports_nav_controller_v1.py`
Expected: FAIL because controller module does not exist.

- [ ] **Step 3: Implement pure route-resolution functions**

`resolve_route` must accept registry-valid canonical/legacy inputs and optional explicit intent without importing Streamlit. Enforce precedence exactly: `tap > canonical_url > remembered market > registry default > legacy` for route decisions, with legacy used only when no higher authority exists.

- [ ] **Step 4: Run controller tests and confirm GREEN**

Run: `python -m pytest -q tests/test_universal_sports_nav_controller_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit Task 2**

Commit message: `feat: add universal sports navigation controller`

---

### Task 3: Canonical URL Codec and Legacy Deep-Link Normalization

**Files:**
- Create: `universal_sports_nav_url_v1.py`
- Create: `tests/test_universal_sports_nav_url_v1.py`
- Read: `streamlit_route_hygiene_v1.py`

**Interfaces:**
- Consumes: `RouteState` and registry page-param allowlists.
- Produces: `CanonicalQuery`, `parse_canonical_query(query: Mapping[str, Any]) -> CanonicalQuery`, `normalize_legacy_query(query: Mapping[str, Any], session: Mapping[str, Any]) -> CanonicalQuery`, `query_patch_for_state(state: RouteState, query: Mapping[str, Any]) -> QueryPatch`, `apply_query_patch(query: MutableMapping[str, Any], patch: QueryPatch) -> bool`.

Canonical universal keys are exactly `sport` and `market`.

- [ ] **Step 1: Write failing URL tests**

Cover canonical parse, old `ks_sport` + per-sport market normalization, explicit newer session/tap authority preventing stale legacy query takeover, idempotent no-op when URL already canonical, removal of old universal `ks_*` query keys after normalization, preservation of allowed page params (`date`, destination-valid `game_id`/`player_id`), removal of invalid cross-destination page params, and list-valued query inputs.

- [ ] **Step 2: Run URL tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_sports_nav_url_v1.py`
Expected: FAIL because URL module does not exist.

- [ ] **Step 3: Implement pure URL codec and query patch model**

Use a patch object rather than mutating query state inside parse/resolve functions. `apply_query_patch` is the only mutation helper and must return `False` when no write is needed to prevent rerun loops.

- [ ] **Step 4: Run URL tests and confirm GREEN**

Run: `python -m pytest -q tests/test_universal_sports_nav_url_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit Task 3**

Commit message: `feat: add canonical universal sports URLs`

---

### Task 4: Legacy Compatibility Adapter and Selector Suppression

**Files:**
- Create: `universal_sports_nav_compat_v1.py`
- Create: `tests/test_universal_sports_nav_compat_v1.py`
- Read: `streamlit_memory_lazy_router_v1.py`
- Read: `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`

**Interfaces:**
- Consumes: validated `RouteState`, registry legacy fields.
- Produces: `apply_legacy_route_state(state: RouteState, session_state: MutableMapping[str, Any]) -> tuple[str, ...]`, `make_legacy_selectbox_bridge(delegate: Callable[..., Any], state: RouteState) -> Callable[..., Any]`, `LEGACY_TOP_LEVEL_LABELS`.

- [ ] **Step 1: Write failing compatibility tests**

Assert exact session translations for NFL/CFB/NBA/MLB/WNBA, MLB live-odds flag handling, no mutation of unrelated page keys, and suppression only for these top-level labels: `🏟️ Sport`, `🎯 NFL Market`, `🎯 CFB Market`, `🎯 NBA Market`, `🎯 MLB Market`, `🎯 WNBA Market`. Add negative tests proving date/game/player selectboxes call the delegate unchanged.

- [ ] **Step 2: Run compatibility tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_sports_nav_compat_v1.py`
Expected: FAIL because compatibility module does not exist.

- [ ] **Step 3: Implement translation and narrow selectbox bridge**

`apply_legacy_route_state` sets `ks_sport_touch` plus only the active sport's market key, preserves other sports' remembered market keys, and manages MLB live-odds flag. The selectbox bridge returns canonical legacy values for known top-level selectors without rendering them; every other selectbox delegates exactly.

- [ ] **Step 4: Run compatibility tests and confirm GREEN**

Run: `python -m pytest -q tests/test_universal_sports_nav_compat_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit Task 4**

Commit message: `feat: add universal nav legacy adapter`

---

### Task 5: Sticky KYRE SPORTS Renderer

**Files:**
- Create: `universal_sports_nav_ui_v1.py`
- Create: `tests/test_universal_sports_nav_ui_v1.py`

**Interfaces:**
- Consumes: `RouteState`, `visible_sports()`, controller intent constructors.
- Produces: `render_universal_nav(state: RouteState) -> RouteIntent | None`, `NAV_CONTAINER_KEY = "ks_universal_nav_shell"`, `SPORT_CONTROL_KEY = "ks_universal_sport_pills"`, `MARKET_CONTROL_KEY = "ks_universal_market_pills"`.

**UI decisions locked by this plan:**
- Use `st.container(key=NAV_CONTAINER_KEY)` for one scoped sticky shell.
- Use native single-select `st.pills` for Row 1 sport IDs and Row 2 market IDs; format display from registry, never use display labels as state IDs.
- Render compact `KYRE SPORTS` brand inside the sticky shell.
- Apply scoped CSS only under `.st-key-ks_universal_nav_shell`; do not globally restyle all Streamlit controls.
- Active styling uses black + glacier-blue design language; focus remains visible.
- Row overflow is horizontally scrollable at narrow widths and must not create page-wide horizontal scrolling.
- Do not render date or page-level controls inside this module.

- [ ] **Step 1: Write failing UI/source-contract tests**

Test constant keys, presence of `st.container`/`st.pills`, registry-driven options, no sport/market `st.selectbox`, scoped sticky CSS (`position: sticky`, top/z-index, horizontal overflow), KYRE SPORTS brand, and renderer emitting `RouteIntent(source="tap")` only when the selected ID differs from current state.

- [ ] **Step 2: Run UI tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_sports_nav_ui_v1.py`
Expected: FAIL because UI module does not exist.

- [ ] **Step 3: Implement the renderer**

Keep rendering side effects in this file only. Do not write URL or legacy session state here; return intent for the activation overlay/controller to process.

- [ ] **Step 4: Run UI tests and confirm GREEN**

Run: `python -m pytest -q tests/test_universal_sports_nav_ui_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit Task 5**

Commit message: `feat: add sticky universal sports navigation UI`

---

### Task 6: Additive Production Activation Overlay and Route Integration

**Files:**
- Create: `streamlit_memory_lazy_router_universal_nav_v1.py`
- Create: `tests/test_streamlit_memory_lazy_router_universal_nav_v1.py`
- Read-only parent: `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`

**Interfaces:**
- Consumes: controller, URL codec, compatibility adapter, renderer.
- Produces: `record_bootstrap_import_ms(value: float) -> None`, `render_app() -> Any`, `MODEL_VERSION`, `FROZEN_PARENT`, `UNIVERSAL_NAV_ENABLED = True`.

**Required render order:**

```text
1. Parse canonical + legacy cold-start inputs
2. Resolve canonical RouteState
3. Render sticky Universal Nav and capture optional tap intent
4. If tap exists, resolve the newer state
5. Apply canonical URL patch once if needed
6. Translate canonical state to legacy session keys
7. Install narrow legacy-selectbox suppression bridge
8. Delegate to frozen/current parent render_app()
9. Restore patched Streamlit callable in finally
```

The overlay must call/replace the older route-hygiene responsibility rather than allowing both systems to mutate the same universal query state independently. `streamlit_route_hygiene_v1.py` remains frozen/read-only during V1; Universal Nav owns canonical `sport`/`market` normalization above it.

- [ ] **Step 1: Write failing activation/integration tests**

Cover parent delegation, controller-before-parent ordering, canonical URL cold start, fresh tap overriding stale CFB/NBA legacy query state, per-sport remembered market round-trip, NFL direct Spread path receiving `NFL/Spread` translated state, CFB Game Total Page 1→Page 2 retaining canonical CFB/Game Total state, old top-level selectors suppressed, page-level date selector delegated, and bridge restoration in `finally` after parent exceptions.

- [ ] **Step 2: Run activation tests and confirm RED**

Run: `python -m pytest -q tests/test_streamlit_memory_lazy_router_universal_nav_v1.py`
Expected: FAIL because activation overlay does not exist.

- [ ] **Step 3: Implement additive outer overlay**

Import the current production parent as `prior`; do not edit the parent. Keep parent/model behavior unchanged. Ensure one rerun transition per explicit nav action and no duplicate async/data fetch is initiated by the nav layer.

- [ ] **Step 4: Run focused integration suite and confirm GREEN**

Run:
`python -m pytest -q tests/test_universal_sports_nav_registry_v1.py tests/test_universal_sports_nav_controller_v1.py tests/test_universal_sports_nav_url_v1.py tests/test_universal_sports_nav_compat_v1.py tests/test_universal_sports_nav_ui_v1.py tests/test_streamlit_memory_lazy_router_universal_nav_v1.py`
Expected: PASS, 0 failures.

- [ ] **Step 5: Run affected existing router regressions**

Run the existing focused tests for:
- root lazy-router market contracts;
- sport-navigation category contract/functionality;
- NBA Spread site activation;
- NFL Spread V7 live activation + auto-date/mobile nav + V132/V136 fast routing;
- CFB Game Total Page 1/Page 2 fast-switch and current integration certification.

Expected: PASS for every Runless-supported affected test. If an unrelated optional dependency is missing, classify as INFRA and do not claim that test passed.

- [ ] **Step 6: Commit Task 6**

Commit message: `feat: activate universal sports navigation overlay`

---

### Task 7: Production Entrypoint Cutover, Runless Proof, and Freeze

**Files:**
- Modify: `app.py`
- Create: `devsystem/runless_proof_plans/api2-universal-sports-navigation-v1.json`
- Test: all tests from Tasks 1–6 plus affected existing router regressions.

**Interfaces:**
- Consumes: `streamlit_memory_lazy_router_universal_nav_v1.record_bootstrap_import_ms`, `render_app`.
- Produces: production boot through the Universal Nav overlay; no new route authority below it.

- [ ] **Step 1: Write the production-import assertion before editing `app.py`**

Add to `tests/test_streamlit_memory_lazy_router_universal_nav_v1.py` an assertion that runtime import in `app.py` is exactly:

```python
from streamlit_memory_lazy_router_universal_nav_v1 import record_bootstrap_import_ms, render_app
```

and that the previous parent remains referenced only as compatibility/read-only ancestry, not as the runtime boot import.

- [ ] **Step 2: Run the import assertion and confirm RED**

Run: `python -m pytest -q tests/test_streamlit_memory_lazy_router_universal_nav_v1.py`
Expected: FAIL because `app.py` still boots the prior overlay.

- [ ] **Step 3: Change only the runtime import in `app.py`**

Do not modify model/data imports or frozen compatibility comments except where the runtime-import assertion requires an explicit current-parent compatibility comment.

- [ ] **Step 4: Create the Runless proof plan**

Task/workstream ID: `api2-universal-sports-navigation-v1`.

Required plan properties:
- source main SHA is the exact main head used to create the implementation branch;
- `github_actions_fallback: 0`;
- `required_check: "runless-final-gate"`;
- `required_check_app_id: 5204253`;
- freeze token: `API2_UNIVERSAL_SPORTS_NAVIGATION_V1_FROZEN`;
- compile all six new Python runtime modules plus `app.py`;
- run all six new test files;
- run the affected existing router regression files identified in Task 6;
- no bare repository-wide pytest command unless the Runless sandbox has every dependency required by the whole repository.

- [ ] **Step 5: Run exact-head Runless proof once**

Expected terminal state before merge: `MERGE_AUTHORIZED`, failure class `NONE`, receipt digest present, required `runless-final-gate` success attached to the exact candidate SHA.

If proof fails, classify the exact failure once, patch the root cause on the same authoritative branch, and re-prove the new exact head. Do not open duplicate proof lanes.

- [ ] **Step 6: Merge exact certified head and verify merged main**

Open one PR, verify required check against exact head, merge with expected-head protection, then read back `main` and confirm the merge commit contains the certified candidate.

- [ ] **Step 7: Finalize GREEN + FROZEN**

Write canonical finalization record/manifest/bridge preserving unrelated thaws, close out Runless to durable `GREEN_FROZEN / NONE`, release only this workstream's scope lease, and independently read back:
- PR merged;
- exact candidate check success;
- merged-main SHA;
- finalization ledger freeze token/state hash;
- durable Runless `GREEN_FROZEN`;
- lease registry with this holder absent;
- zero GitHub Actions workflow runs for the candidate.

- [ ] **Step 8: Commit/closeout documentation only if required by the existing control plane**

No additional product behavior changes are allowed after exact-head proof without generating a new candidate and re-proving it.

---

## Self-Review Results

### Spec coverage

All spec sections map to implementation tasks: registry/visibility (Task 1), authority/memory/precedence (Task 2), canonical URLs/deep-link migration (Task 3), safe compatibility translation and selector suppression (Task 4), sticky responsive UI/accessibility (Task 5), safe outer activation/direct-route protection/rollback seam (Task 6), and production proof/freeze (Task 7).

### Step scan

Each task has an explicit RED test action, one implementation responsibility, a GREEN verification command, and a commit boundary. Broad integration and finalization are isolated to Tasks 6–7 rather than mixed into component construction.

### Type consistency

`RouteState` and `RouteIntent` are defined once in Task 2 and consumed unchanged by Tasks 3–6. Registry IDs are machine slugs everywhere; legacy labels remain adapter-only. URL keys remain exactly `sport`/`market` throughout.

### Review Focus coverage

All five review-focus risks have explicit owning tests in Tasks 1–4 and Task 6.

### Proportion/YAGNI

V1 adds no SPA, no new frontend framework, no account persistence, no page-control unification, and no legacy-router deletion. The plan uses one additive overlay and focused modules so the initial cutover is reversible and the frozen sports analytics remain untouched.
