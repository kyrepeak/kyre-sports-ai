# API 2 Universal Runtime V5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the layered universal Streamlit navigation/runtime with one staged V5 route authority that switches immediately, remembers each sport safely, rejects stale renders, lazy-loads only the active destination, and remains stable during long sessions.

**Architecture:** V5 is additive first and becomes the sole universal route owner only after its generation, vault, render-gate, cache, lazy-load, health, and rollback contracts are proven. Existing sports-page modules remain responsible for page UI/data/model behavior; V5 owns cross-sport route state, active render scope, cached-return orchestration, prefetch budget, and runtime health. The current certified runtime remains available behind one rollback switch until merged-main stress certification completes.

**Tech Stack:** Python 3.13, Streamlit, pytest, existing `universal_sports_nav_*` contracts, existing lazy-router/page modules, Runless V2 proof/finalization.

**Spec:** `docs/superpowers/specs/2026-10-17-api2-universal-runtime-v5-design.md`

## Global Constraints

- Keep Streamlit; do not migrate the visible frontend to React/Next.js in this workstream.
- Exactly one active universal route owner, one active route, and one active render generation at a time.
- Latest tap always wins; stale generations may not paint or mutate active route/UI state.
- Inactive sports may retain remembered state/cache but must execute zero active page-render work.
- Preserve each sport's last valid market/game/player/date/filter state without allowing inactive state to leak into the active sport.
- Show only previously verified cached destination data immediately; refresh live data afterward and accept visible refresh results only for the current generation.
- Prefetch at most 1–2 likely destinations and never let prefetch block or mutate the active destination.
- Existing frozen sports-page/model/projection/provider behavior stays untouched unless a separately proven compatibility defect requires it.
- No unbounded eager imports/preloading.
- Application-side performance targets: route commit <=150 ms, destination shell <=500 ms, verified cached useful content <=750 ms when available, no monotonic V5-caused latency growth over repeated navigation.
- Rollback must select exactly one owner; V5 and fallback may never be active simultaneously.
- Proof remains Runless-authoritative with `github_actions_fallback = 0` and exact-head/frozen-registry/finalization rules.

## Review Focus

1. **Browser back/forward or stale URL page params:** canonical V5 route must win once per generation; outgoing `date/game_id/player_id` keys must not resurrect the previous sport. Pin in Task 1 and Task 6 tests.
2. **Late provider/cache refresh after rapid multi-tap:** a superseded generation may update only its private cache, never active UI/route state. Pin in Task 3 and Task 4 tests.
3. **Registry evolution invalidates remembered market/game state:** vault restore must validate against current `universal_sports_nav_registry_v1` and fall back to the sport default rather than crashing or reviving a retired route. Pin in Task 2 tests.
4. **Hot reload/interrupted rerun leaves wrapper/scope residue:** self-heal must normalize V5-owned runtime state to exactly one owner/scope without stacking wrappers. Pin in Task 6 and Task 7 tests.
5. **Cache schema/version or provider freshness mismatch:** incompatible snapshots must be ignored and refreshed; no stale value may be labeled current. Pin in Task 4 tests.

---

## File Structure

### New runtime files

- `universal_runtime_v5_state.py` — pure route-generation/runtime state engine; no Streamlit imports.
- `universal_runtime_v5_vault.py` — per-sport remembered route/page-state capture and restore.
- `universal_runtime_v5_scope.py` — active render-scope lifecycle and generation commit gate.
- `universal_runtime_v5_snapshot.py` — verified snapshot metadata/cache and generation-safe refresh acceptance.
- `universal_runtime_v5_loader.py` — lazy destination loader + bounded prefetch policy.
- `universal_runtime_v5_health.py` — owner/scope invariants, timing events, long-session degradation checks.
- `streamlit_memory_lazy_router_universal_runtime_v5.py` — one Streamlit terminal owner, immediate handoff shell, V5/fallback switch, current-page compatibility adapter.

### Existing files modified only at activation/finalization stage

- `app.py` — switch the preserved-entrypoint runtime import to V5 only after V5 tests are green; preserve current certified fallback identity.
- `devsystem/runless_proof_plans/api2-universal-runtime-v5.json` — exact Runless commands/artifacts/freeze token.
- `devsystem/finalization_ledger_v2/...` and frozen registry — mutated only through existing finalization/forward-port authority, never hand-edited as product code.

### New tests

- `tests/test_universal_runtime_v5_state.py`
- `tests/test_universal_runtime_v5_vault.py`
- `tests/test_universal_runtime_v5_scope.py`
- `tests/test_universal_runtime_v5_snapshot.py`
- `tests/test_universal_runtime_v5_loader.py`
- `tests/test_universal_runtime_v5_terminal.py`
- `tests/test_universal_runtime_v5_health.py`
- `tests/test_universal_runtime_v5_stress.py`
- `tests/test_universal_runtime_v5_rollback.py`

---

### Task 1: Route Generation + Canonical State Engine

**Files:**
- Create: `universal_runtime_v5_state.py`
- Test: `tests/test_universal_runtime_v5_state.py`
- Reference only: `universal_sports_nav_controller_v1.py`
- Reference only: `universal_sports_nav_registry_v1.py`

**Interfaces:**
- Consumes: `RouteIntent`, `RouteState`, `resolve_route(...)`, `get_market(...)`, `get_sport(...)`.
- Produces:
  - `@dataclass(frozen=True) RuntimeRoute(sport_id: str, market_id: str, params: Mapping[str, str], generation: int, source: str)`
  - `@dataclass(frozen=True) RuntimeState(active: RuntimeRoute, last_route_by_sport: Mapping[str, RuntimeRoute], generation: int)`
  - `bootstrap_runtime(route_state: RouteState, params: Mapping[str, str] | None = None) -> RuntimeState`
  - `commit_intent(state: RuntimeState, intent: RouteIntent, params: Mapping[str, str] | None = None) -> RuntimeState`
  - `is_current_generation(state: RuntimeState, generation: int) -> bool`
  - `canonical_query_patch(previous: RuntimeRoute, current: RuntimeRoute, existing_query: Mapping[str, object]) -> dict[str, str | None]`

- [ ] **Step 1: Write failing route-generation tests**

Cover:
- first tap increments generation exactly once;
- rapid NFL -> NBA -> MLB produces generations N+1/N+2/N+3 and only final state is current;
- same exact route tap does not create a second owner but still resolves deterministically;
- remembered market is restored when returning to a sport;
- canonical query patch removes outgoing `date`, `game_id`, `player_id` when destination route does not own them;
- browser/back URL values cannot override a later explicit tap generation.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_state.py`
Expected: FAIL because `universal_runtime_v5_state` does not exist.

- [ ] **Step 3: Implement the pure state engine**

Implement only the interfaces above. Use immutable dataclasses/mapping copies. Reuse `resolve_route` for registry/default/remembered-market validation; do not import Streamlit or page modules.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_universal_runtime_v5_state.py tests/test_universal_sports_nav_controller_v1.py tests/test_universal_sports_nav_url_v1.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add universal_runtime_v5_state.py tests/test_universal_runtime_v5_state.py
git commit -m "feat: add V5 route generation authority"
```

---

### Task 2: Per-Sport State Vaults

**Files:**
- Create: `universal_runtime_v5_vault.py`
- Test: `tests/test_universal_runtime_v5_vault.py`
- Reference only: `universal_sports_nav_registry_v1.py`

**Interfaces:**
- Consumes: `RuntimeRoute` from Task 1; `get_market(...)`, `get_sport(...)` and `MarketRoute.page_params`.
- Produces:
  - `VAULT_SESSION_KEY = "ks_v5_sport_vaults"`
  - `@dataclass(frozen=True) SportVault(sport_id: str, market_id: str, page_params: Mapping[str, str], local_state: Mapping[str, object], revision: int)`
  - `capture_vault(session: Mapping[str, object], route: RuntimeRoute) -> SportVault`
  - `store_vault(session: MutableMapping[str, object], vault: SportVault) -> None`
  - `restore_vault(session: MutableMapping[str, object], sport_id: str) -> SportVault | None`
  - `apply_vault_to_session(session: MutableMapping[str, object], vault: SportVault) -> None`
  - `retire_active_ephemeral_state(session: MutableMapping[str, object], outgoing_sport_id: str) -> tuple[str, ...]`

- [ ] **Step 1: Write failing vault tests**

Cover:
- NFL market/game/player state survives NFL -> NBA -> NFL;
- inactive NFL keys are not treated as active NBA keys;
- only route-owned page params from `MarketRoute.page_params` are restored;
- removed/invalid remembered market falls back to current sport default;
- vault revision increments only when stored content changes;
- `retire_active_ephemeral_state` removes V5-owned transient callback/scope keys but does **not** delete remembered sport state.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_vault.py`
Expected: FAIL because module/interfaces are absent.

- [ ] **Step 3: Implement vault capture/restore/isolation**

Use one serialized mapping under `VAULT_SESSION_KEY`; keep route memory isolated by sport ID. Do not persist arbitrary Streamlit widget objects/callables; allow only scalar/list/dict page-local values whose keys belong to the sport/market compatibility namespace or registered page params.

- [ ] **Step 4: Run GREEN + old cross-route regression**

Run: `python -m pytest -q tests/test_universal_runtime_v5_vault.py tests/test_api2_universal_shell_route_top_live_handoff_v2.py tests/test_api2_universal_nav_tap_first_handoff_v1.py`
Expected: all pass; old tests remain as compatibility evidence, not the new destructive-vault contract.

- [ ] **Step 5: Commit**

```bash
git add universal_runtime_v5_vault.py tests/test_universal_runtime_v5_vault.py
git commit -m "feat: add per-sport V5 state vaults"
```

---

### Task 3: Single Render Scope + Stale-Generation Commit Gate

**Files:**
- Create: `universal_runtime_v5_scope.py`
- Test: `tests/test_universal_runtime_v5_scope.py`

**Interfaces:**
- Consumes: `RuntimeState`, `RuntimeRoute`, `is_current_generation(...)` from Task 1.
- Produces:
  - `@dataclass(frozen=True) RenderScope(scope_id: str, generation: int, sport_id: str, market_id: str, status: str)` where status is one of `ACTIVE`, `RETIRING`, `DORMANT`.
  - `new_scope(route: RuntimeRoute) -> RenderScope`
  - `retire_scope(scope: RenderScope) -> RenderScope`
  - `can_commit(scope: RenderScope, runtime: RuntimeState) -> bool`
  - `commit_if_current(scope: RenderScope, runtime: RuntimeState, commit: Callable[[], T]) -> T | None`
  - `assert_single_active_scope(scopes: Iterable[RenderScope]) -> RenderScope`

- [ ] **Step 1: Write failing scope/generation tests**

Cover:
- one active scope passes invariant;
- two active scopes raise `RuntimeError("API2_V5_DUPLICATE_ACTIVE_SCOPE")`;
- scope from generation 41 cannot commit after generation 42 exists;
- a late provider result's commit callback is never invoked after supersession;
- retiring/dormant scope cannot mutate active state;
- scope IDs are deterministic enough for tracing but unique across generations.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_scope.py`
Expected: FAIL because scope module is absent.

- [ ] **Step 3: Implement scope lifecycle and commit gate**

Keep module pure Python. `commit_if_current` is the only public helper later runtime code uses before visible/state commits from refresh work.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_universal_runtime_v5_scope.py tests/test_universal_runtime_v5_state.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add universal_runtime_v5_scope.py tests/test_universal_runtime_v5_scope.py
git commit -m "feat: gate V5 renders by active generation"
```

---

### Task 4: Verified Snapshot Cache + Generation-Safe Refresh

**Files:**
- Create: `universal_runtime_v5_snapshot.py`
- Test: `tests/test_universal_runtime_v5_snapshot.py`

**Interfaces:**
- Consumes: `RuntimeRoute`, `RenderScope`, `RuntimeState`, `commit_if_current(...)`.
- Produces:
  - `SNAPSHOT_SCHEMA_VERSION = 1`
  - `@dataclass(frozen=True) SnapshotKey(sport_id: str, market_id: str, params_fingerprint: str)`
  - `@dataclass(frozen=True) VerifiedSnapshot(key: SnapshotKey, payload: object, verified_at_epoch_ms: int, ttl_ms: int, schema_version: int, source_version: str)`
  - `snapshot_key(route: RuntimeRoute) -> SnapshotKey`
  - `snapshot_is_compatible(snapshot: VerifiedSnapshot, now_epoch_ms: int, expected_source_version: str) -> bool`
  - `snapshot_is_fresh(snapshot: VerifiedSnapshot, now_epoch_ms: int) -> bool`
  - `put_snapshot(cache: MutableMapping[str, object], snapshot: VerifiedSnapshot) -> None`
  - `get_snapshot(cache: Mapping[str, object], key: SnapshotKey, *, now_epoch_ms: int, expected_source_version: str) -> VerifiedSnapshot | None`
  - `accept_refresh(scope: RenderScope, runtime: RuntimeState, cache: MutableMapping[str, object], snapshot: VerifiedSnapshot, visible_commit: Callable[[VerifiedSnapshot], None]) -> bool`

- [ ] **Step 1: Write failing snapshot tests**

Cover:
- compatible verified snapshot returns immediately;
- expired snapshot can be returned as cache data only when caller requests stale-while-refresh behavior, but is not marked fresh;
- wrong schema/source version is ignored;
- cache key isolates sport/market/page params;
- generation 41 refresh after generation 42 updates the private cache but never invokes `visible_commit`;
- current-generation refresh updates cache and visible commit exactly once.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_snapshot.py`
Expected: FAIL because snapshot module is absent.

- [ ] **Step 3: Implement snapshot compatibility/freshness/acceptance**

Use canonical JSON/hash fingerprinting for params. The cache stores data payloads/metadata, never a live Streamlit widget or DOM object. Keep TTL supplied by caller/data class; do not hardcode one TTL for all sports data.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_universal_runtime_v5_snapshot.py tests/test_universal_runtime_v5_scope.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add universal_runtime_v5_snapshot.py tests/test_universal_runtime_v5_snapshot.py
git commit -m "feat: add verified V5 route snapshots"
```

---

### Task 5: Lazy Destination Loading + Bounded Prefetch

**Files:**
- Create: `universal_runtime_v5_loader.py`
- Test: `tests/test_universal_runtime_v5_loader.py`
- Reference only: `streamlit_memory_lazy_router_v1.py`
- Reference only: current terminal route chain rooted at `streamlit_memory_lazy_router_api2_nfl_rushing_cleanup_v1.py`

**Interfaces:**
- Consumes: `RuntimeRoute`, `SnapshotKey`.
- Produces:
  - `@dataclass(frozen=True) DestinationAdapter(route_key: tuple[str, str], loader: Callable[[], object], renderer: Callable[[object], object], source_version: str, ttl_ms: int)`
  - `@dataclass(frozen=True) PrefetchRequest(route: RuntimeRoute, priority: int)`
  - `resolve_destination(route: RuntimeRoute) -> DestinationAdapter`
  - `load_destination(adapter: DestinationAdapter) -> object`
  - `choose_prefetch(active: RuntimeRoute, candidates: Sequence[RuntimeRoute], *, limit: int = 2) -> tuple[PrefetchRequest, ...]`
  - `run_prefetch(requests: Sequence[PrefetchRequest], load: Callable[[RuntimeRoute], object]) -> tuple[object, ...]`

- [ ] **Step 1: Write failing loader/prefetch tests**

Cover:
- resolving one active route does not import/load unrelated sport modules;
- every `live=True` registry market has a V5 destination adapter or explicit fail-closed adapter;
- active NFL route does not load MLB/WNBA/CFB/NBA destination work;
- `choose_prefetch(..., limit=2)` never returns more than two;
- active route is never included as prefetch;
- prefetch failure is swallowed/classified and does not fail active loader;
- prefetch callback cannot mutate route/session state by interface design.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_loader.py`
Expected: FAIL because loader module is absent.

- [ ] **Step 3: Implement lazy adapters and bounded policy**

Build adapters around the existing **current production page entrypoints**, not old historical versions. Import destination modules only inside adapter `loader` callables. If a registered route has no certified render surface, use a fail-closed adapter that renders the existing safe warning rather than falling through to another sport/page.

- [ ] **Step 4: Run GREEN + lazy-router regressions**

Run: `python -m pytest -q tests/test_universal_runtime_v5_loader.py tests/test_streamlit_memory_lazy_router_universal_nav_v1.py tests/test_api2_universal_nav_single_owner_speed_v1.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add universal_runtime_v5_loader.py tests/test_universal_runtime_v5_loader.py
git commit -m "feat: add lazy V5 destination loader"
```

---

### Task 6: Streamlit V5 Terminal Owner, Immediate Handoff, Cutover + Rollback

**Files:**
- Create: `streamlit_memory_lazy_router_universal_runtime_v5.py`
- Create: `tests/test_universal_runtime_v5_terminal.py`
- Create: `tests/test_universal_runtime_v5_rollback.py`
- Modify: `app.py` activation shim only after tests pass
- Reference only: `streamlit_memory_lazy_router_universal_nav_v4.py`
- Reference only: `streamlit_memory_lazy_router_api2_nfl_rushing_cleanup_v1.py`
- Reference only: `kyre_universal_shell_runtime_v2.py`

**Interfaces:**
- Consumes all Tasks 1–5 interfaces.
- Produces:
  - `RUNTIME_MODE_SESSION_KEY = "ks_v5_runtime_mode"`
  - `V5_MODE_ACTIVE = "active"`, `V5_MODE_FALLBACK = "fallback"`
  - `render_app() -> object | None`
  - `record_bootstrap_import_ms(value: float) -> None`
  - `_commit_navigation_intent(intent: RouteIntent) -> RuntimeState`
  - `_render_destination_shell(route: RuntimeRoute) -> object`
  - `_render_active_destination(runtime: RuntimeState, scope: RenderScope) -> object | None`
  - `_render_fallback() -> object | None`

- [ ] **Step 1: Write failing terminal/rollback tests**

Cover:
- one tap commits route before destination render;
- outgoing page surface is replaced by destination shell immediately;
- only current generation can render destination body;
- rapid NFL -> NBA -> MLB renders only MLB body;
- old V2/V3/V4 route callbacks are not active owners in V5 active mode;
- fallback mode calls exactly the current certified pre-V5 terminal once;
- active and fallback owner count can never both equal 1 in the same run;
- Streamlit hot-reload with leaked prior V5 scope normalizes before render;
- app activation string points to V5 only after V5 terminal tests are green;
- browser/back query change goes through V5 canonical commit rather than directly reactivating a legacy page.

- [ ] **Step 2: Run RED before changing `app.py`**

Run: `python -m pytest -q tests/test_universal_runtime_v5_terminal.py tests/test_universal_runtime_v5_rollback.py`
Expected: FAIL because V5 terminal is absent.

- [ ] **Step 3: Implement terminal owner in fallback-default mode first**

Create the module with current certified terminal injected as fallback. Mount the existing KYRE shell, V5 route controls, generation commit, vault save/restore, immediate destination shell, snapshot display, lazy active destination, refresh acceptance and bounded prefetch. Do not edit frozen sports page/model modules.

- [ ] **Step 4: Run terminal GREEN while `app.py` is unchanged**

Run: `python -m pytest -q tests/test_universal_runtime_v5_terminal.py tests/test_universal_runtime_v5_rollback.py tests/test_api2_route_transition_mask_v1.py tests/test_api2_universal_shell_route_top_live_handoff_v2.py`
Expected: all pass.

- [ ] **Step 5: Perform exact frozen-registry/thaw preflight for `app.py`**

Read current main blob for `app.py`, frozen owners and active thaws. Create/reuse exactly one V5 workstream/lease and exact thaw authority before modifying the activation shim. Abort on main/head drift; do not create a second proof/workstream.

- [ ] **Step 6: Activate V5 in `app.py` with one rollback switch**

Replace only the preserved-entrypoint router import target with `streamlit_memory_lazy_router_universal_runtime_v5`. Preserve the exact current certified terminal as `_render_fallback` dependency and frozen compatibility markers required by regression tests.

- [ ] **Step 7: Run activation regression suite**

Run: `python -m pytest -q tests/test_universal_runtime_v5_terminal.py tests/test_universal_runtime_v5_rollback.py tests/test_api2_universal_shell_route_top_live_handoff_v2.py tests/test_api2_route_transition_mask_v1.py tests/test_api2_universal_nav_single_owner_speed_v1.py tests/test_api2_universal_nav_tap_first_handoff_v1.py tests/test_api2_universal_tap_only_selector_cross_sport_v1.py tests/test_streamlit_memory_lazy_router_universal_nav_v1.py tests/test_universal_sports_nav_controller_v1.py tests/test_universal_sports_nav_url_v1.py`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add streamlit_memory_lazy_router_universal_runtime_v5.py app.py tests/test_universal_runtime_v5_terminal.py tests/test_universal_runtime_v5_rollback.py
git commit -m "feat: activate universal runtime V5"
```

---

### Task 7: Runtime Health, Performance Budgets + Long-Session Stress Certification

**Files:**
- Create: `universal_runtime_v5_health.py`
- Test: `tests/test_universal_runtime_v5_health.py`
- Test: `tests/test_universal_runtime_v5_stress.py`
- Modify: `streamlit_memory_lazy_router_universal_runtime_v5.py` to emit health/timing events only

**Interfaces:**
- Consumes: runtime state/scope events and monotonic timestamps supplied by caller.
- Produces:
  - `@dataclass(frozen=True) RuntimeEvent(name: str, generation: int, monotonic_ms: float, values: Mapping[str, object])`
  - `@dataclass(frozen=True) RuntimeHealth(active_owner_count: int, active_scope_count: int, stale_commit_attempts: int, wrapper_depth: int, route_commit_ms: float | None, shell_visible_ms: float | None, cached_visible_ms: float | None, live_refresh_ms: float | None)`
  - `record_event(events: MutableSequence[RuntimeEvent], event: RuntimeEvent) -> None`
  - `summarize_health(events: Sequence[RuntimeEvent], *, active_owner_count: int, active_scope_count: int, wrapper_depth: int) -> RuntimeHealth`
  - `assert_runtime_health(health: RuntimeHealth) -> None`
  - `latency_trend_ms(samples: Sequence[float]) -> float`

- [ ] **Step 1: Write failing health/stress tests**

Cover:
- duplicate owner/scope is a hard failure;
- stale commit attempts are counted and never painted;
- wrapper depth after 100+ route changes equals initial depth;
- repeated route switching does not produce monotonic application-side latency growth;
- simulated `NFL -> MLB -> NBA -> CFB -> NFL -> WNBA -> MLB` cycles restore each sport correctly;
- intentionally delayed Gen N refresh after Gen N+1/N+2 cannot paint;
- simulated 30–60 minute event sequence (virtual clock, not wall-clock sleep) keeps one owner/scope;
- route commit/shell/cache metrics are separated from provider-refresh duration;
- application targets <=150/500/750 ms are asserted on controlled fake-provider paths;
- provider-bound delays are classified separately and do not falsify route-runtime timing.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_universal_runtime_v5_health.py tests/test_universal_runtime_v5_stress.py`
Expected: FAIL because health module/events are absent.

- [ ] **Step 3: Implement health summary + lightweight event hooks**

Do not add network calls. Do not log full provider payloads. Events must carry route IDs/generation/timing/invariant counters only.

- [ ] **Step 4: Run GREEN + full V5 suite**

Run: `python -m pytest -q tests/test_universal_runtime_v5_state.py tests/test_universal_runtime_v5_vault.py tests/test_universal_runtime_v5_scope.py tests/test_universal_runtime_v5_snapshot.py tests/test_universal_runtime_v5_loader.py tests/test_universal_runtime_v5_terminal.py tests/test_universal_runtime_v5_health.py tests/test_universal_runtime_v5_stress.py tests/test_universal_runtime_v5_rollback.py`
Expected: all pass.

- [ ] **Step 5: Run cross-sport/current-page regressions**

Run the existing universal-nav suite plus active NFL/CFB/NBA/MLB/WNBA route-owner tests discovered from the current terminal chain. Minimum required named tests are the activation regression suite from Task 6 plus current NFL Rushing V17, NFL Active-Slate, CFB Game Total, NBA Spread, MLB root lazy-router and WNBA PRA route-owner tests. Any failure must be classified as candidate-caused vs pre-existing/environmental before strategy changes.

- [ ] **Step 6: Commit**

```bash
git add universal_runtime_v5_health.py streamlit_memory_lazy_router_universal_runtime_v5.py tests/test_universal_runtime_v5_health.py tests/test_universal_runtime_v5_stress.py
git commit -m "test: certify V5 long-session runtime health"
```

---

### Task 8: Exact-Head Runless Proof, Merge, Registry Forward-Port + Freeze

**Files:**
- Create: `devsystem/runless_proof_plans/api2-universal-runtime-v5.json`
- Optionally create: `devsystem/api2_universal_runtime_v5_cert_v1.py` only if the proof needs a compact deterministic certification entrypoint beyond pytest.
- Finalization records/manifest: produced by existing control-plane authority after merge; do not hand-edit product branches.

**Interfaces:**
- Consumes: exact candidate head from Tasks 1–7 and existing Runless V2 transports/finalization authority.
- Produces:
  - Task/workstream: `api2-universal-runtime-v5`
  - Freeze token: `API2_UNIVERSAL_RUNTIME_V5_FROZEN`
  - Required check: `runless-final-gate`
  - Required check App ID: `5204253`
  - `github_actions_fallback: 0`

- [ ] **Step 1: Main-drift + Step 2A authority check**

Confirm exactly one active workstream, one branch/PR, one scope lease, one candidate head and one proof path. If main moved, forward-port/rebase the same authority chain before proof; do not create a competing proof.

- [ ] **Step 2: Write proof plan bound to exact candidate**

Include at minimum:
- `python -m py_compile` for all seven V5 runtime modules plus `app.py`;
- `python -m pytest -q` for the full V5 test suite;
- current universal-nav regressions;
- current representative NFL/CFB/NBA/MLB/WNBA route-owner regressions;
- deterministic stress/health cert;
- no GitHub Actions fallback.

- [ ] **Step 3: Submit exactly one Runless proof**

Use the existing privileged `runless_v2.request_proof_transport(...)` path. Wait for terminal material state; do not poll blindly or submit a second proof.

Expected terminal pre-merge state: `MERGE_AUTHORIZED`, `failure_class=NONE`, exact candidate SHA, expected main SHA, receipt digest and App 5204253 gate check.

- [ ] **Step 4: Merge exact proven PR head once**

Re-read PR head and main. Merge only if both still match proof authority. Use expected-head merge protection.

- [ ] **Step 5: Registry forward-port / thaw retirement**

Use existing `request_registry_forward_port_transport(...)` or current equivalent. Any stale thaw identity must be reconciled through supported control-plane CAS/authority, not by hand-editing registry JSON.

- [ ] **Step 6: Finalization ledger/freeze read-back**

Require immutable record for `API2_UNIVERSAL_RUNTIME_V5_FROZEN`, manifest state-hash advance, merged-main SHA, proof digest and exact artifact blobs.

- [ ] **Step 7: Durable Runless closeout**

Call the existing closeout/resume authority once after the ledger/registry material state exists. Require durable state `GREEN_FROZEN`, `failure_class=NONE`, freeze token, manifest hash and merged-main SHA.

- [ ] **Step 8: Fresh merged-main verification before completion claim**

In one fresh sandbox/check-out of merged main:
- run `python -m py_compile` for V5 modules + `app.py`;
- run full V5 suite;
- run the cross-sport activation/stress regression slice;
- read durable Runless `GREEN_FROZEN` once;
- confirm no active workstream lease;
- stop the sandbox.

Only then report `🟢 100% GREEN + 🧊 FROZEN`.

---

## Plan Self-Review Checklist

- **Spec coverage:** Tasks 1–8 cover route generation, one owner/scope, state vaults, cached return, generation-safe refresh, lazy loading, bounded prefetch, immediate handoff, self-healing/health, performance budgets, staged cutover, rollback, stress testing and final Runless freeze.
- **Step scan:** Each task has one RED test action, one minimal implementation action, verification commands and a commit boundary; activation/finalization steps are separated from product-code steps.
- **Type consistency:** `RuntimeRoute`/`RuntimeState` -> `SportVault` -> `RenderScope` -> `VerifiedSnapshot`/`DestinationAdapter` -> terminal -> health all use the Task 1 route generation as the single identity spine.
- **Review Focus:** all five highest-risk gaps are pinned to explicit tests in Tasks 1–7.
- **Proportion:** plan specifies interfaces, tests and decisions without transcribing implementation bodies.
