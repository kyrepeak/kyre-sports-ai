# API 2 Universal NFL Active-Slate Resolver V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every NFL page automatically open the nearest verified NFL date that still has a scheduled/live game, roll forward after an all-final slate, and preserve a deliberate manual date override across NFL markets.

**Architecture:** Add one pure NFL active-slate resolver plus one Streamlit session/runtime owner above the current terminal route chain. The runtime seeds the compatibility date (`nfl_v1_date`), bridges NFL date widgets into shared AUTO/MANUAL state, and delegates every non-NFL route unchanged. Existing market-specific smart-slate helpers remain in place for backward compatibility but stand down while the universal state is MANUAL so they cannot fight the user's explicit date choice.

**Tech Stack:** Python 3.13, Streamlit, pandas, existing ESPN NFL `load_nfl_slate`, existing nflverse schedule-calendar discovery, pytest, existing Universal Navigation V4/terminal successor chain, Runless V2 exact-head proof.

**Spec:** `docs/superpowers/specs/2026-10-17-api2-universal-nfl-active-slate-v1-design.md`

## Global Constraints

- API 2 stays in its own execution lane: do not import MONSTER live task state, branches, PRs, SHAs, runs, blockers, leases, or proof authority.
- Step 2A is mandatory before product implementation: one active problem, one authoritative branch, one authoritative PR, one proof path.
- Authoritative branch: `api2-universal-nfl-active-slate-v1`; authoritative PR: `#1638`. Do not create a replacement branch or PR.
- Before the first product-code commit, forward-port this planning branch onto the then-current protected `main` using one force-with-lease/replay of the approved spec + plan if needed. Inspect the authoritative result once; do not create a duplicate branch, PR, deployment, lease, or proof request.
- At plan self-review time, protected `main` contains the MONSTER terminal successor `streamlit_memory_lazy_router_monster_cfb_market_completeness_r1`. Preserve that successor unchanged underneath the new API 2 NFL owner.
- Use Eastern Time (`America/New_York`) as the canonical NFL calendar boundary.
- Do not hard-code Thursday/Sunday/Monday rules; verified schedule/game state chooses the date.
- Keep `nfl_v1_date` for compatibility.
- Manual date browsing remains available. MANUAL mode must never be auto-advanced by Spread, Passing Yards, Receiving Yards, or Game Total page-local smart-slate helpers.
- NFL-to-NFL market changes preserve MANUAL. A cross-sport exit/fresh NFL entry returns to AUTO by allowing the existing Universal Navigation sport-local cleanup to clear the `nfl_*` runtime state.
- Calendar discovery may identify candidate dates, but a candidate must be verified by the authoritative renderable NFL loader before it becomes active.
- Provider/calendar failure is fail-closed and retryable; never permanently cache a transient `NO_GAMES`/unavailable result.
- Do not layer a new long-lived cache over current-day game status. The universal runtime must expose terminal-status changes as soon as the existing authoritative loader refreshes; future verified schedule dates may use safe session-level reuse.
- No model, projection, probability, ranking, selection, sportsbook influence, stake sizing, or wager behavior may change.
- Preserve current Universal Navigation route-transition masking, tap-only mobile navigation, sticky `KYRE SPORTS AI` shell, Top button, and MONSTER CFB Page-2 market-completeness ownership.
- Exact-head proof-before-merge, merged-main read-back, production proof, and frozen-registry closeout are required before GREEN + FROZEN.

## Review Focus

1. **Unknown or malformed game status:** do not treat it as an all-final slate and jump ahead; fail closed instead. Task 1 pins this with `test_unknown_state_fails_closed_without_rollover`.
2. **Stale calendar hint:** if nflverse points at a date whose authoritative loader has no usable/non-final games, continue to the next candidate/fallback rather than exposing the hint. Task 1 pins this with `test_calendar_candidate_must_verify_before_selection`.
3. **Manual override vs page-local auto-advance:** a user selecting an empty/completed date must stay on it across Spread, Passing Yards, Receiving Yards, and Game Total. Task 3 pins all four helpers.
4. **Route lifetime:** NFL-to-NFL market changes preserve MANUAL, while leaving NFL and later returning starts AUTO. Tasks 2 and 4 pin both transitions.
5. **Transient provider failure/cache poisoning:** unavailable schedule truth must remain retryable and must not freeze a false empty slate. Tasks 1 and 2 pin this behavior; Task 2 also proves no extra current-day status cache delays terminal rollover beyond the authoritative loader's own freshness.

---

### Task 0: Rebase the single authority onto current protected main

**Files:**
- Preserve: `docs/superpowers/specs/2026-10-17-api2-universal-nfl-active-slate-v1-design.md`
- Preserve: `docs/superpowers/plans/2026-10-17-api2-universal-nfl-active-slate-v1.md`
- No product files may change in this task.

**Interfaces:**
- Consumes: authoritative branch `api2-universal-nfl-active-slate-v1`, PR `#1638`, current protected `main`.
- Produces: same branch + same PR rebased/forward-ported to current main with only the approved spec/plan above it.

- [ ] **Step 1: Read authoritative heads once**

Read protected `main`, branch `api2-universal-nfl-active-slate-v1`, and PR `#1638`. Record exact SHAs. Do not create another branch or PR.

- [ ] **Step 2: Forward-port the planning branch once if main advanced**

If the branch is behind/diverged from current main, replay the approved spec + plan onto current main using force-with-lease against the exact branch head observed in Step 1. Preserve PR `#1638`.

- [ ] **Step 3: Read back the same branch/PR once**

Verify the PR still points to `api2-universal-nfl-active-slate-v1`, its base is `main`, and the diff contains only the two planning docs before product implementation starts.

Expected: one authoritative lane, no duplicate async work.

---

### Task 1: Build the pure verified active-slate resolver

**Files:**
- Create: `nfl_active_slate_controller_v1.py`
- Test: `tests/test_api2_nfl_active_slate_controller_v1.py`
- Reuse: `nfl_hub_v1.py`
- Reuse: `nfl_passing_yards_next_slate_v1.py`

**Interfaces:**
- Consumes: `primary_loader(day_iso: str) -> tuple[pd.DataFrame, dict[str, Any]]`; `calendar_dates(start: date, end: date) -> Iterable[date]`.
- Produces: `resolve_active_slate(today_et: date, primary_loader: Callable, calendar_dates: Callable, *, calendar_lookahead_days: int = 370, network_fallback_days: int = 21) -> dict[str, Any]` with `state`, `resolved_date`, `source`, `reason`, and `advanced`.
- Produces: `classify_loaded_slate(games: Any, diag: Mapping[str, Any]) -> str` returning `ACTIVE`, `EXHAUSTED`, `EMPTY`, or `UNAVAILABLE`.

- [ ] **Step 1: Write the failing resolver tests**

Add tests named:
- `test_today_with_pre_game_stays_today`
- `test_today_with_live_game_stays_today`
- `test_mixed_post_and_pre_stays_today`
- `test_all_post_rolls_to_next_verified_date`
- `test_empty_today_rolls_to_next_verified_date`
- `test_calendar_candidate_must_verify_before_selection`
- `test_unknown_state_fails_closed_without_rollover`
- `test_calendar_failure_uses_bounded_primary_fallback`
- `test_provider_and_calendar_failure_is_retryable_unavailable`
- `test_irregular_schedule_date_requires_no_weekday_logic`

Use DataFrames with the existing ESPN states `pre`, `in`, `post`; assert all-final/empty dates advance, active dates do not, and unknown state returns `UNAVAILABLE` without inventing a date.

- [ ] **Step 2: Run the controller tests and verify RED**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_controller_v1.py`

Expected: FAIL because `nfl_active_slate_controller_v1` does not exist yet.

- [ ] **Step 3: Implement the minimal pure controller**

Implement the two interfaces above. Calendar discovery is only a candidate index; call `primary_loader` on every candidate before returning `FOUND`. Treat `pre`/`in` as active, all-`post` as exhausted, an empty verified frame as empty, and malformed/unknown status or `request_ok != True` as unavailable/fail-closed. Keep network fallback bounded at 21 days.

- [ ] **Step 4: Run focused tests and existing next-slate regressions**

Run:
`python -m pytest -q tests/test_api2_nfl_active_slate_controller_v1.py tests/test_nfl_spread_next_slate_v1.py tests/test_nfl_passing_yards_v41_next_game_date.py tests/test_nfl_receiving_yards_smart_slate_v11.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Commit message: `API2: add verified universal NFL active-slate resolver`

---

### Task 2: Add one AUTO/MANUAL Streamlit session owner and date-widget bridge

**Files:**
- Create: `nfl_active_slate_runtime_v1.py`
- Test: `tests/test_api2_nfl_active_slate_runtime_v1.py`
- Reuse: `nfl_hub_v1.py`
- Reuse: `nfl_passing_yards_next_slate_v1.py`

**Interfaces:**
- Consumes: Task 1 `resolve_active_slate(...)`.
- Produces constants `MODE_KEY = "nfl_active_slate_mode"`, `ACTIVE_DATE_KEY = "nfl_active_slate_date"`, `MANUAL_DATE_KEY = "nfl_manual_slate_date"`, `STATE_KEY = "nfl_active_slate_state"`, `SOURCE_KEY = "nfl_active_slate_source"`, `CHECKED_AT_KEY = "nfl_active_slate_checked_at"`.
- Produces: `prepare_nfl_active_slate(session: MutableMapping[str, Any], *, today_et: date, primary_loader: Callable, calendar_dates: Callable, now_monotonic: float | None = None) -> dict[str, Any]`.
- Produces: `is_manual_mode(session: Mapping[str, Any]) -> bool`.
- Produces: `install_nfl_date_input_bridge(session: MutableMapping[str, Any]) -> ContextManager[None]`.

- [ ] **Step 1: Write failing runtime/session tests**

Add tests proving:
- fresh session starts `AUTO`, writes the verified date to `nfl_v1_date`, and records source/state;
- current-day AUTO resolution is re-evaluated on a meaningful rerender instead of being hidden behind a second long TTL;
- safe reuse is allowed for an unchanged verified future date, but `UNAVAILABLE` is never permanently cached;
- a newly encountered NFL date widget is seeded from the universal date even if its page-local default says today;
- a user change from the bridge's last seeded widget value enters `MANUAL` and writes both `nfl_manual_slate_date` and `nfl_v1_date`;
- MANUAL seeds a different NFL market's date widget to the same manual date;
- non-NFL/non-date widgets delegate to native Streamlit unchanged;
- clearing the sport-local `nfl_*` state yields AUTO on the next fresh NFL entry.

- [ ] **Step 2: Run runtime tests and verify RED**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_runtime_v1.py`

Expected: FAIL because the runtime module does not exist.

- [ ] **Step 3: Implement the shared session owner**

`prepare_nfl_active_slate` must skip resolution in MANUAL and preserve the user's date. In AUTO it calls Task 1, writes `nfl_v1_date`, records diagnostics, allows retry on `UNAVAILABLE`, and must not add a long current-day cache over the existing authoritative loader. Do not perform network scanning itself.

- [ ] **Step 4: Implement the NFL-only date-input bridge**

Intercept only NFL date widgets (NFL-owned `nfl_*` date keys / NFL date labels). Track the last value seeded per widget so a genuine user edit can be distinguished from first render/stale page state. In AUTO, seed new market widgets to the active date; in MANUAL, seed them to the manual date; when the user's widget value differs from its last seed, switch/update MANUAL. Always restore `st.date_input` in `finally`.

- [ ] **Step 5: Run Task 1 + Task 2 tests**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_controller_v1.py tests/test_api2_nfl_active_slate_runtime_v1.py`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Commit message: `API2: add shared NFL auto manual slate runtime`

---

### Task 3: Stop legacy smart-slate helpers from fighting MANUAL mode

**Files:**
- Modify: `nfl_spread_autodate_repair_v1.py`
- Modify: `nfl_passing_yards_hub_v37.py`
- Modify: `nfl_receiving_yards_hub_v11.py`
- Modify: `nfl_game_totals_hub_v8_1.py`
- Test: `tests/test_api2_nfl_active_slate_legacy_compat_v1.py`
- Regression: `tests/test_api2_nfl_spread_autodate_mobile_nav_repair_v1.py`
- Regression: `tests/test_nfl_passing_yards_v37_smart_slate.py`
- Regression: `tests/test_nfl_receiving_yards_smart_slate_v11.py`
- Regression: exact NFL Game Totals V8/V9/V10 smart-date tests discovered with `pytest --collect-only -q tests | grep -i game_totals` before mutation.

**Interfaces:**
- Consumes: Task 2 `is_manual_mode(session)`.
- Produces: existing helper signatures unchanged; they preserve the selected date and perform zero auto-advance resolver calls while universal mode is MANUAL.

- [ ] **Step 1: Write failing compatibility tests for all four page-local auto owners**

For each page/helper, seed `nfl_active_slate_mode="MANUAL"` and a deliberate completed/empty date. Assert the legacy resolver/finder is not called, the selected/widget date is unchanged, and no page-local successor date is written.

- [ ] **Step 2: Run the compatibility tests and verify RED**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_legacy_compat_v1.py`

Expected: FAIL because the legacy helpers do not yet honor universal MANUAL state.

- [ ] **Step 3: Add the minimal MANUAL guard to each legacy auto owner**

Import/use `is_manual_mode` without changing any projection/data/model path. Preserve the exact existing AUTO behavior for Spread, Passing Yards, Receiving Yards, and Game Total.

- [ ] **Step 4: Run focused + inherited market regressions**

Run at minimum:
`python -m pytest -q tests/test_api2_nfl_active_slate_legacy_compat_v1.py tests/test_api2_nfl_spread_autodate_mobile_nav_repair_v1.py tests/test_nfl_passing_yards_v37_smart_slate.py tests/test_nfl_receiving_yards_smart_slate_v11.py`

Then run the collected Game Totals smart-date tests that cover `_auto_surface_next_slate` and V9/V10/compact rendering.

Expected: PASS; AUTO behavior remains unchanged and MANUAL never snaps forward.

- [ ] **Step 5: Commit Task 3**

Commit message: `API2: preserve manual NFL dates across smart slate pages`

---

### Task 4: Mount the universal NFL owner above the current terminal route chain

**Files:**
- Create: `streamlit_memory_lazy_router_api2_nfl_active_slate_v1.py`
- Modify: `app.py`
- Test: `tests/test_api2_nfl_active_slate_router_v1.py`
- Regression: `tests/test_api2_universal_shell_route_top_live_handoff_v2.py`
- Regression: `tests/test_api2_route_transition_mask_v1.py`
- Regression: `tests/test_api2_public_module_identity_collision_v1.py`
- Regression: `tests/test_monster_cfb_game_total_v4_route_ownership_r1.py`
- Regression: `tests/test_monster_cfb_game_total_slate_market_completeness_r1.py`
- Regression: `tests/test_monster_cfb_game_total_public_latency_r1.py`

**Interfaces:**
- Consumes: Task 2 `prepare_nfl_active_slate(...)` and `install_nfl_date_input_bridge(...)`.
- Consumes/delegates: current protected-main terminal parent `streamlit_memory_lazy_router_monster_cfb_market_completeness_r1` (or its exact forward-ported successor if protected main advances before execution; preserve that same merged ownership chain in this PR).
- Produces: `record_bootstrap_import_ms(value: float) -> None` and `render_app() -> Any` matching the terminal router contract.

- [ ] **Step 1: Write failing terminal-router tests**

Assert:
- exact NFL canonical route prepares the active slate before the prior router renders;
- the date-input bridge is installed only around NFL rendering and restored afterward;
- NFL market switches keep shared MANUAL state;
- CFB/MLB/NBA/WNBA call the prior terminal router without invoking the NFL resolver;
- current MONSTER CFB Game Total ownership remains behavior-preserved;
- `app.py` rewrites the preserved legacy import to exactly the new API 2 NFL terminal successor and still contains one legacy-import replacement only.

- [ ] **Step 2: Run router tests and verify RED**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_router_v1.py`

Expected: FAIL because the terminal successor is not created/activated.

- [ ] **Step 3: Implement the additive terminal successor**

Detect NFL from canonical universal route/session/query using the same normalization policy as current terminal route owners. For NFL only, prepare shared slate state, install the date bridge, and delegate to the current parent. For all other sports, delegate directly. Do not modify model/source/page routing.

- [ ] **Step 4: Advance the app's single terminal import rewrite**

Change only the current `_LEGACY_ROUTER_IMPORT_*` replacement target so the preserved entrypoint imports `streamlit_memory_lazy_router_api2_nfl_active_slate_v1`. The new successor's parent must be the exact current-main terminal route owner, preserving MONSTER CFB market-completeness behavior underneath it.

- [ ] **Step 5: Run route/navigation regression suite**

Run:
`python -m pytest -q tests/test_api2_nfl_active_slate_router_v1.py tests/test_api2_universal_shell_route_top_live_handoff_v2.py tests/test_api2_route_transition_mask_v1.py tests/test_api2_public_module_identity_collision_v1.py tests/test_monster_cfb_game_total_v4_route_ownership_r1.py tests/test_monster_cfb_game_total_slate_market_completeness_r1.py tests/test_monster_cfb_game_total_public_latency_r1.py`

Expected: PASS.

- [ ] **Step 6: Compile changed runtime files**

Run:
`python -m py_compile nfl_active_slate_controller_v1.py nfl_active_slate_runtime_v1.py streamlit_memory_lazy_router_api2_nfl_active_slate_v1.py nfl_spread_autodate_repair_v1.py nfl_passing_yards_hub_v37.py nfl_receiving_yards_hub_v11.py nfl_game_totals_hub_v8_1.py app.py`

Expected: exit 0.

- [ ] **Step 7: Commit Task 4**

Commit message: `API2: activate universal NFL active slate owner`

---

### Task 5: Prove all NFL markets, exact-head Runless, production, and freeze

**Files:**
- Create: `devsystem/api2_nfl_active_slate_public_cert_v1.py`
- Create: `tests/test_api2_nfl_active_slate_public_cert_v1.py`
- Create: `devsystem/runless_proof_plans/api2-nfl-active-slate-v1.json`
- Create/update only the exact API 2 task ledger / frozen-registry artifact required by the current Runless/freeze contract.
- Do not add a GitHub Actions fallback proof workflow.

**Interfaces:**
- Consumes: Tasks 1-4 runtime.
- Produces: deterministic proof tokens for current-date active slate, all-final rollover, cross-market consistency, manual override, navigation regression, exact-head check, merged-main read-back, and final freeze token `API2_NFL_ACTIVE_SLATE_V1_FROZEN`.

- [ ] **Step 1: Write the failing certification contract test**

Require the cert/proof plan to cover all registered NFL markets from `universal_sports_nav_registry_v1`: `slate`, `moneyline`, `spread`, `game-total`, `passing-yards`, `rushing-yards`, `receiving-yards`, `receptions`, `passing-tds`, `anytime-td`, `daily-picks`.

Require assertions for:
- automatic landing on the nearest actionable NFL date;
- same shared date across every NFL market;
- completed current slate rolling forward;
- manual override remaining fixed across at least Slate → Spread → Passing Yards → Game Total → Receiving Yards;
- leaving NFL and returning restores AUTO;
- tap-only navigation does not summon a searchable text/keyboard path;
- `KYRE SPORTS AI` header + Top control remain visible;
- no stale other-sport body bleed;
- current MONSTER CFB market-completeness route still passes;
- projection/sportsbook/model invariants are unchanged.

- [ ] **Step 2: Run cert contract and verify RED**

Run: `python -m pytest -q tests/test_api2_nfl_active_slate_public_cert_v1.py`

Expected: FAIL because cert/proof artifacts do not exist.

- [ ] **Step 3: Implement certification + one Runless proof plan**

The Runless plan must compile changed files and run Tasks 1-5 focused tests plus the existing Universal Navigation, module-identity, route-transition, and MONSTER CFB ownership/latency regressions. Use one proof request only for the exact candidate head.

- [ ] **Step 4: Run the full focused local gate once**

Run the combined Tasks 1-5 tests, inherited smart-slate tests, Universal Navigation/route-transition/module-identity tests, and current MONSTER CFB ownership/market-completeness/latency tests.

Expected: all PASS.

- [ ] **Step 5: Verify branch scope against the exact current-main merge base**

Confirm the diff contains only the approved spec/plan, new NFL active-slate controller/runtime/router/cert/proof artifacts, the four MANUAL-mode compatibility guards, `app.py` activation, and required current control-plane ledger/freeze metadata. Confirm zero model/projection/probability/ranking/sportsbook mutations.

- [ ] **Step 6: Request exactly one Runless exact-head proof**

Use the repository's privileged Runless transport. Record candidate SHA, proof ID, `runless-final-gate` check/run identity, and receipt. Wait for that authoritative proof to reach a terminal result; do not poll-loop or create a second request.

Expected: exact candidate receives terminal SUCCESS / merge authorization.

- [ ] **Step 7: Merge only the certified exact head through PR #1638**

Before merge, verify PR head still equals the proved SHA and protected-main base has not invalidated the proof. If main advanced, classify/reconcile once and obtain a new exact-head proof on the successor candidate instead of merging stale proof.

- [ ] **Step 8: Run merged-main read-back and production proof**

Verify protected `main` contains the exact active terminal successor and the deployed Streamlit app exhibits the approved behavior on the next real NFL slate. Confirm all NFL markets agree on the same automatic date and a manual date remains stable across market taps.

- [ ] **Step 9: Freeze/read back and release authority**

Write/read back `API2_NFL_ACTIVE_SLATE_V1_FROZEN`, confirm zero active task leases/thaws for this workstream, and retain exact merged-main SHA + proof receipt.

Expected: only now report **🟢 GREEN + 🧊 FROZEN — 100%**.
