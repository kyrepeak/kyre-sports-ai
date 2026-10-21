# API 2 Universal Page Experience V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every current and future universal KYRE SPORTS AI route one shared floating `↑ TOP` control and one atomic slow-transition loading shield that prevents outgoing-page bleed.

**Architecture:** Preserve Universal Atomic Navigation V2 as the frozen behavioral parent. Add a terminal-agnostic Universal Page Experience controller/runtime that owns TOP plus broader page-transition intent classification, then switch one ancestor terminal seam to the new runtime so all descendants inherit it without page-by-page edits. Certify coverage from `universal_sports_nav_registry_v1.SPORTS`, deep-route parameters, and the existing Runtime V5 generation/scope authority.

**Tech Stack:** Python 3, Streamlit, parent-window JavaScript injected through `st.html` / `streamlit.components.v1.html`, pytest, existing Universal Runtime V5 + Runless V2 proof/finalization authority.

**Spec:** `docs/superpowers/specs/2026-10-21-api2-universal-page-experience-v1.md`

## Global Constraints

- Universal ownership only; do not patch individual Moneyline, Spread, Game Total, Top Picks, Passing Yards, PRA, or other sport pages.
- Keep the existing loader anti-flash threshold at exactly `140 ms`.
- Loader is fully opaque `#060b13` whenever visible.
- TOP touch target is at least `44 px`; default visibility threshold is `320 px` unless a focused browser test proves another threshold is needed.
- No sports provider calls, model/projection/probability changes, or Kyre Sports API routing changes.
- Do not introduce SGO, ESPN, or ESPN BET.
- Do not introduce background destination prefetch, duplicate route authority, repeated polling, or stacked event listeners.
- Preserve Runtime V5 generation/scope `can_commit` / `commit_if_current` stale-write protection.
- Page transitions include sport/market navigation, canonical/deep route changes, Page 1↔Page 2, Analyze/Open/View/Back actions, and browser back/forward.
- Local interactions such as Line Lab sliders, local sort/filter, inputs, accordions, and stable-route panel controls must not retain a full-page loader.
- Step 2A: one branch, one PR, one exact-head Runless proof path, no duplicate proof submissions, failure classification before any successor candidate.

## Review Focus

- **Nested/changed Streamlit scroll owner:** TOP must find the active parent scroll surface and fall back safely to `window/document`, then scroll that surface to zero.
- **Repeated reruns/navigation:** singleton refresh must never stack TOP nodes, overlays, mutation observers, pointer handlers, or `popstate` handlers.
- **Ambiguous button labels:** generic in-page buttons must cancel before 140 ms when canonical/deep route identity stays stable; known route-changing Analyze/Open/View/Back actions must remain protected.
- **Mobile safe area:** TOP must stay inside the visible lower-right safe area and keep a ≥44 px target without covering critical navigation.
- **JavaScript mount failure:** server fallback must still cover a canonical route transition opaquely and must never reveal the outgoing page under a failed destination.

---

## File Structure

- Create `universal_page_experience_v1.py` — pure controller/markup ownership for TOP, transition intent classification, destination labels, singleton lifecycle, reduced-motion styling.
- Create `universal_page_experience_runtime_v1.py` — Runtime V5 adapter that mounts Page Experience before destination loading while preserving V2 render ordering, stale-write guards, and server fallback.
- Modify `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py` — one inheritance seam: import/call the new universal runtime instead of Atomic Navigation Runtime V2; descendants inherit automatically.
- Create `tests/test_universal_page_experience_v1.py` — TOP/controller/transition-classifier contracts.
- Create `tests/test_universal_page_experience_runtime_v1.py` — runtime ordering/fail-closed/idempotent mount contracts.
- Create `tests/test_universal_page_experience_coverage_v1.py` — registry-driven current/future-route coverage plus deep-route samples.
- Create `devsystem/execution_plans/api2-universal-page-experience-v1.json`, `devsystem/runless_proof_plans/api2-universal-page-experience-v1.json`, and `devsystem/task_ledgers/api2-universal-page-experience-v1.json` during proof binding.

### Task 1: Universal TOP + singleton controller

**Files:**
- Create: `universal_page_experience_v1.py`
- Test: `tests/test_universal_page_experience_v1.py`

**Interfaces:**
- Consumes: `universal_atomic_navigation_v2.destination_page_name(route)` and the existing `140 ms` loading contract.
- Produces: `PAGE_EXPERIENCE_VERSION: str`, `TOP_REVEAL_PX: int`, `page_experience_controller_markup(route: Any | None = None) -> str`, `page_experience_fallback_markup(route: Any) -> str`.

- [ ] **Step 1: Write failing singleton/TOP tests**

Add tests asserting markup contains one versioned singleton key, exactly one `data-kyre-universal-top="v1"` identity, `TOP_REVEAL_PX == 320`, a ≥44 px control contract, lower-right fixed positioning with safe-area offsets, and no Streamlit widget/session-state call for TOP.

- [ ] **Step 2: Run focused RED test**

Run: `python -m pytest -q tests/test_universal_page_experience_v1.py`
Expected: FAIL because `universal_page_experience_v1` does not exist.

- [ ] **Step 3: Implement controller shell**

Implement `page_experience_controller_markup(route=None) -> str` using one `window.parent` singleton. Reuse the existing V2 destination-name semantics and `140 ms` one-shot timeout; add TOP DOM, scroll-owner detection, scroll listener, smooth-to-zero behavior, mobile safe-area CSS, `prefers-reduced-motion` fallback, and refresh/destroy lifecycle that reuses rather than stacks listeners/nodes.

- [ ] **Step 4: Add Review Focus tests owned by this task**

Pin nested scroll-owner fallback, repeated-refresh singleton count, and mobile-safe-area / ≥44 px markup contracts.

- [ ] **Step 5: Run GREEN test**

Run: `python -m pytest -q tests/test_universal_page_experience_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add universal page experience controller`

### Task 2: Transition classification + anti-bleed behavior

**Files:**
- Modify: `universal_page_experience_v1.py`
- Modify/Test: `tests/test_universal_page_experience_v1.py`

**Interfaces:**
- Consumes: singleton controller from Task 1.
- Produces: browser-side `PAGE_TRANSITION` vs `LOCAL_INTERACTION` intent classification embedded in `page_experience_controller_markup`.

- [ ] **Step 1: Write failing transition-classification tests**

Assert the controller treats sport/market shell clicks, canonical URL changes, `popstate`, Page 1→Page 2 Analyze/Open/View actions, Page 2→Page 1 Back actions, and game/player deep-route changes as page transitions; assert sliders/ranges, text inputs, selects, local sort/filter controls, toolbar/sidebar, and stable-route actions cancel/hide before the 140 ms threshold.

- [ ] **Step 2: Run focused RED test**

Run: `python -m pytest -q tests/test_universal_page_experience_v1.py`
Expected: FAIL on the new classification assertions.

- [ ] **Step 3: Implement transition intent rules**

Extend the parent-window controller so `pointerdown` captures only candidate page transitions, compares canonical/deep route identity, arms one timeout, and cancels immediately when Streamlit stabilizes without a route/view identity change. Preserve opaque `#060b13`, human destination labels, and fail-closed visibility during a genuine slow/failed transition.

- [ ] **Step 4: Add Review Focus ambiguity test**

Exercise a generic in-page button that reruns while route identity remains unchanged; prove the full-screen overlay is not retained. Exercise Analyze/Back with deep-page identity change; prove it remains protected.

- [ ] **Step 5: Run GREEN test**

Run: `python -m pytest -q tests/test_universal_page_experience_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: classify universal page transitions`

### Task 3: Universal runtime inheritance seam

**Files:**
- Create: `universal_page_experience_runtime_v1.py`
- Modify: `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py`
- Test: `tests/test_universal_page_experience_runtime_v1.py`

**Interfaces:**
- Consumes: `page_experience_controller_markup(route)` / `page_experience_fallback_markup(route)` and existing Runtime V5 core interface (`_load_runtime`, `_consume_pending_intent`, `_commit_navigation_intent`, `_reconcile_query_navigation`, `_normalize_active_scope`, `resolve_destination`, `load_destination`, `can_commit`, `commit_if_current`).
- Produces: `render_page_experience_app(core: ModuleType) -> object | None`.

- [ ] **Step 1: Write failing runtime-order tests**

Assert `render_page_experience_app` mounts the controller before `load_destination`, keeps one destination slot, preserves `can_commit` / `commit_if_current`, uses opaque fallback markup when browser mounting fails, and clears/reveals only after a current-generation render completes.

- [ ] **Step 2: Run focused RED test**

Run: `python -m pytest -q tests/test_universal_page_experience_runtime_v1.py`
Expected: FAIL because the runtime module does not exist.

- [ ] **Step 3: Implement runtime adapter**

Create `render_page_experience_app(core)` by preserving the proven Atomic Navigation Runtime V2 ordering and stale-write contract while substituting the Page Experience controller/fallback. Do not add prefetch or polling.

- [ ] **Step 4: Switch the single ancestor seam**

In `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py`, replace only the Atomic Navigation Runtime V2 import/call with `from universal_page_experience_runtime_v1 import render_page_experience_app` and `return render_page_experience_app(frozen_runtime)`. Keep all route-owner/provider/model lines unchanged.

- [ ] **Step 5: Add fail-closed JS-mount Review Focus test**

Force controller mount failure in the fake Streamlit runtime and assert the opaque server fallback is rendered on route transition before destination load and outgoing content is not restored on destination exception.

- [ ] **Step 6: Run GREEN test**

Run: `python -m pytest -q tests/test_universal_page_experience_runtime_v1.py tests/test_universal_atomic_navigation_v2.py tests/test_universal_atomic_navigation_v2_inheritance.py`
Expected: PASS after updating inheritance expectations to the new child runtime while preserving V2 as the parent contract.

- [ ] **Step 7: Commit**

Commit message: `feat: inherit universal page experience runtime`

### Task 4: Registry-driven “literally every page” certification

**Files:**
- Create: `tests/test_universal_page_experience_coverage_v1.py`
- Modify only if required by test expectation: `tests/test_universal_atomic_navigation_v2_inheritance.py`

**Interfaces:**
- Consumes: `universal_sports_nav_registry_v1.SPORTS`, `MarketRoute.page_params`, `page_experience_controller_markup`, terminal inheritance chain.
- Produces: executable certification that every live registered route and representative deep route inherits the universal experience.

- [ ] **Step 1: Write registry enumeration test**

Iterate every live `SportRoute` / `MarketRoute` in `SPORTS`; for each canonical route build a route object and assert the Page Experience controller can produce a human label and universal controller markup without any page-specific import.

- [ ] **Step 2: Add deep-route samples**

For every market declaring `game_id` and/or `player_id` in `page_params`, construct representative deep identities and assert controller coverage. Include explicit Page 1→Page 2 / Page 2→Page 1 Analyze/Back intent contracts.

- [ ] **Step 3: Add terminal-chain inheritance test**

Assert current production `app.py` still imports the NBA PRA terminal, that terminal still inherits NFL Daily Picks V4, V4 still inherits V3, and V3 now delegates to `universal_page_experience_runtime_v1`. This is the proof that existing and future descendants inherit without page edits.

- [ ] **Step 4: Run coverage GREEN test**

Run: `python -m pytest -q tests/test_universal_page_experience_coverage_v1.py tests/test_universal_page_experience_runtime_v1.py tests/test_universal_page_experience_v1.py`
Expected: PASS across all live registered routes.

- [ ] **Step 5: Commit**

Commit message: `test: certify universal page experience coverage`

### Task 5: Regression gate + Step 2A proof binding

**Files:**
- Create: `devsystem/execution_plans/api2-universal-page-experience-v1.json`
- Create: `devsystem/runless_proof_plans/api2-universal-page-experience-v1.json`
- Create: `devsystem/task_ledgers/api2-universal-page-experience-v1.json`
- No additional product files unless a classified regression proves one is necessary.

**Interfaces:**
- Consumes: exact candidate artifact/dependency map from Tasks 1–4.
- Produces: one exact-head Runless V2 proof request and freeze token `API2_UNIVERSAL_PAGE_EXPERIENCE_V1_FROZEN`.

- [ ] **Step 1: Run focused universal regression gate**

Run all new Page Experience tests plus existing `tests/test_universal_atomic_navigation_v2.py`, `tests/test_universal_atomic_navigation_v2_inheritance.py`, Runtime V5 route/generation/scope tests, and existing universal navigation tests. Expected: all PASS.

- [ ] **Step 2: Run frozen sports regression gate**

Run current NBA PRA Page 1/Page 2, every-player Analyze, and representative NFL/CFB/WNBA/MLB registered-route smoke suites named in the repository. Expected: all PASS; no sports-model/provider files changed.

- [ ] **Step 3: Compile exact product/control files**

Run `python -m py_compile` for `universal_page_experience_v1.py`, `universal_page_experience_runtime_v1.py`, the one modified terminal seam, and new test/control Python files. Expected: exit `0`.

- [ ] **Step 4: Bind one Step 2A ledger/proof plan**

Record exact source main, one branch/PR, scoped universal-shell lease, artifact map, dependency map, proof commands, `140 ms`, `320 px`, forbidden providers, and freeze token. Do not submit a second proof if one already exists for the exact candidate/fencing generation.

- [ ] **Step 5: Exact-head Runless proof**

Submit one proof request. If terminal `FAILED`, classify the durable failure first and patch only that root cause before creating one successor candidate. If `main` drift is disjoint, reconcile the same PR once and never retry the failed identity candidate.

- [ ] **Step 6: Merge + freeze**

Require `runless-final-gate`, merge exact authorized candidate, verify merged-main parentage, write/read the canonical finalization ledger, preserve legacy registry immutability, and close the durable terminal latch.

- [ ] **Step 7: Final read-back**

Verify durable state `GREEN_FROZEN`, failure class `NONE`, exact receipt digest, merged-main SHA, freeze token, manifest state hash, zero live Runless leases, zero scope-aware holders, blocker `NONE`, remaining work `NONE`.
