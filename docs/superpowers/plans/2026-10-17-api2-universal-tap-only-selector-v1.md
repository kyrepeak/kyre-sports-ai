# API 2 Universal Tap-Only Selector V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ordinary finite-choice selectors across active NFL, CFB, NBA, MLB, and WNBA pages tap-only so mobile users can switch games, teams, players, markets, sort options, and similar choices without summoning the software keyboard.

**Architecture:** Add one shared `st.selectbox` compatibility adapter that renders popover + button choices and paginates long lists without editable inputs. Install it through one thin production overlay above the already-certified Universal Navigation V2 stack, preserving existing route ownership and frozen page code beneath it.

**Tech Stack:** Python 3.13, Streamlit 1.66-compatible widget APIs, pytest, Streamlit/AppTest where practical, Runless V2 proof plane, GitHub App 5204253.

**Spec:** `docs/superpowers/specs/2026-10-17-api2-universal-tap-only-selector-v1-design.md`

## Global Constraints

- Ordinary finite-choice selectors must not render an editable search/text input and must not summon the mobile software keyboard.
- Intentional typing widgets remain unchanged; `accept_new_options=True` must delegate to native Streamlit behavior.
- The adapter must return the original raw option value and preserve `format_func`, `key`, `index`, `placeholder`, `disabled`, `label_visibility`, `help`, `on_change`, callback `args`, callback `kwargs`, and supported width/container behavior.
- Long lists render at most 20 selectable options per selector page, with tap-only Previous/Next controls.
- No manual `st.rerun()` is used merely to apply a selection.
- No network request, sports-data load, model calculation, probability change, sportsbook call, or route-authority change is introduced by the selector layer.
- Existing NFL-specific tap-only compatibility code stays intact in V1.
- `app.py` changes only through the repository's legal frozen-artifact thaw/forward-port process.
- One authoritative branch/PR/proof chain only.
- Required merge gate: `runless-final-gate` from GitHub App `5204253`; GitHub Actions fallback `0`.
- Completion requires exact-head proof, exact-candidate merge, merged-main regression, frozen-registry read-back, finalization-ledger transaction, durable `GREEN_FROZEN`, and scope-lease release.
- Freeze token: `API2_UNIVERSAL_TAP_ONLY_SELECTOR_V1_FROZEN`.

## Review Focus

- Generator/iterator options must be materialized exactly once so rendering and return identity cannot drift between passes; Task 1 tests this.
- Unhashable or equality-sensitive raw options must remain position-identified rather than being used as dictionary/set keys; Task 1 tests this.
- A caller `on_change` that itself mutates session state must still run exactly once without the adapter overwriting the callback's later state; Task 2 tests this.
- Nested installation with the existing NFL-specific selectbox bridge must not recurse, double-render, or restore the wrong function; Task 3 tests this.
- Two no-key selectboxes with the same label at different callsites must receive distinct deterministic internal state keys across reruns; Task 2 tests this.

---

### Task 1: Core tap-only selector adapter

**Files:**
- Create: `universal_tap_only_selector_v1.py`
- Create: `tests/test_universal_tap_only_selector_v1.py`

**Interfaces:**
- Produces: `install_universal_tap_only_selectboxes() -> ContextManager[None]`
- Produces: `_tap_only_selectbox(label, options, *args, **kwargs) -> Any`
- Produces: `_materialize_options(options: Iterable[Any]) -> list[Any]`
- Produces: `_resolve_selection(values: list[Any], *, stored: Any, index: int | None) -> tuple[int | None, Any | None]`
- Produces: `_page_for_index(selected_index: int | None, total: int, page_size: int = 20) -> int`
- Produces: constant `PAGE_SIZE = 20`

- [ ] **Step 1: Write the failing unit contract**

Add focused tests asserting: short-list rendering uses a popover plus buttons; no editable-input API is called; raw values survive `format_func`; explicit key state persists; invalid stored state falls back to `index`; `index=None` stays unselected; empty options return `None`; disabled selectors cannot mutate state; duplicate formatted labels remain position-distinct; generators are consumed exactly once; and unhashable raw values work.

- [ ] **Step 2: Run the focused unit contract and confirm RED**

Run: `python -m pytest -q tests/test_universal_tap_only_selector_v1.py`

Expected: FAIL because `universal_tap_only_selector_v1` does not exist.

- [ ] **Step 3: Implement materialization and selection helpers**

Implement the exact helper signatures above. Materialize the incoming iterable once, track selection by position/raw object rather than hash identity, and reconcile stored state to `index`/placeholder rules from the spec.

- [ ] **Step 4: Implement the short-list tap-only renderer**

Implement `_tap_only_selectbox(...)` for 0–20 options using `st.popover` + `st.button`, preserving caller-visible label/help/disabled/placeholder behavior and returning the raw option. Do not call `st.rerun()`.

- [ ] **Step 5: Implement the installation context manager**

`install_universal_tap_only_selectboxes()` must capture the currently installed `st.selectbox`, install one bridge, delegate `accept_new_options=True` to the captured native function, and restore the captured function in `finally` after normal return or exception.

- [ ] **Step 6: Run Task-1 tests to GREEN**

Run: `python -m pytest -q tests/test_universal_tap_only_selector_v1.py`

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add universal_tap_only_selector_v1.py tests/test_universal_tap_only_selector_v1.py
git commit -m "feat: add universal tap-only selectbox adapter"
```

### Task 2: Pagination, callbacks, and deterministic no-key state

**Files:**
- Modify: `universal_tap_only_selector_v1.py`
- Modify: `tests/test_universal_tap_only_selector_v1.py`

**Interfaces:**
- Consumes: Task 1 adapter interfaces.
- Produces: `_selector_identity(label: str, explicit_key: str | None, *, frame) -> str`
- Produces: `_pagination_key(selector_id: str) -> str`
- Produces: long-list Previous/Next page behavior with `PAGE_SIZE == 20`.

- [ ] **Step 1: Add RED tests for long lists and callbacks**

Add tests asserting: 21 options render only 20 choices plus navigation; 41 options page correctly; current selection opens on its containing page; Previous/Next do not alter caller value; caller `on_change(*args, **kwargs)` fires exactly once after a selection; a callback mutation of the same key is not overwritten afterward; two no-key selectors sharing a label at different callsites get distinct stable IDs; and the same callsite keeps its ID across reruns.

- [ ] **Step 2: Run the new tests and confirm RED**

Run: `python -m pytest -q tests/test_universal_tap_only_selector_v1.py`

Expected: new pagination/callback/identity cases FAIL.

- [ ] **Step 3: Implement deterministic selector identity**

Use explicit caller key unchanged when provided. Otherwise derive a stable internal identity from source filename + line/callsite + label; namespace only the adapter's internal pagination/button keys and never overwrite unrelated caller state.

- [ ] **Step 4: Implement paginated tap-only rendering**

For more than 20 options, render the page containing the current selection or stored page, at most 20 option buttons, Previous/Next buttons, and `items X–Y of N`; page navigation changes only internal page state.

- [ ] **Step 5: Implement exact callback ordering**

When an option button fires, set the caller key to the chosen raw option, invoke `on_change(*args, **kwargs)` once, and perform no post-callback write to the caller key.

- [ ] **Step 6: Run Task-2 tests to GREEN**

Run: `python -m pytest -q tests/test_universal_tap_only_selector_v1.py`

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add universal_tap_only_selector_v1.py tests/test_universal_tap_only_selector_v1.py
git commit -m "feat: paginate tap-only selectors safely"
```

### Task 3: Production overlay and cross-sport interception

**Files:**
- Create: `streamlit_memory_lazy_router_universal_tap_only_v1.py`
- Create: `tests/test_api2_universal_tap_only_selector_cross_sport_v1.py`
- Test/inspect: existing NFL-specific `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`
- Delegate to: existing `streamlit_memory_lazy_router_universal_nav_v2.py`

**Interfaces:**
- Consumes: `install_universal_tap_only_selectboxes()` from Task 1.
- Produces: `record_bootstrap_import_ms(value: float) -> None`
- Produces: `render_app() -> Any`
- Produces: `MODEL_VERSION = "API2 UNIVERSAL TAP-ONLY SELECTOR V1"`

- [ ] **Step 1: Write RED overlay/cross-sport tests**

Create tests proving the overlay installs the universal bridge around the current Universal Nav V2 parent and restores it afterward. Add representative fake selector paths for NFL, CFB, NBA, MLB, and WNBA and assert each ordinary finite `st.selectbox` is intercepted and returns the raw selected option without calling an editable-input API.

- [ ] **Step 2: Add nested-bridge compatibility RED tests**

Simulate the existing NFL-specific market bridge being installed beneath/inside the universal layer and prove: no recursion, exactly one selector surface renders, the current captured parent is restored, and the NFL helper remains callable/frozen without code changes.

- [ ] **Step 3: Run Task-3 tests and confirm RED**

Run: `python -m pytest -q tests/test_api2_universal_tap_only_selector_cross_sport_v1.py`

Expected: FAIL because the production overlay does not exist.

- [ ] **Step 4: Implement the thin overlay**

`render_app()` must enter `install_universal_tap_only_selectboxes()`, delegate to Universal Navigation V2, and leave route/state/data ownership entirely to the existing parent. `record_bootstrap_import_ms()` delegates to the current parent.

- [ ] **Step 5: Run cross-sport and existing Universal Nav regressions**

Run:
`python -m pytest -q tests/test_api2_universal_tap_only_selector_cross_sport_v1.py tests/test_api2_universal_nav_tap_first_handoff_v1.py tests/test_universal_sports_nav_registry_v1.py tests/test_universal_sports_nav_controller_v1.py tests/test_universal_sports_nav_url_v1.py tests/test_universal_sports_nav_compat_v1.py tests/test_universal_sports_nav_ui_v1.py tests/test_streamlit_memory_lazy_router_universal_nav_v1.py tests/test_api2_universal_nav_single_owner_speed_v1.py`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add streamlit_memory_lazy_router_universal_tap_only_v1.py tests/test_api2_universal_tap_only_selector_cross_sport_v1.py
git commit -m "feat: install tap-only selectors across sports"
```

### Task 4: Mobile DOM contract and production activation

**Files:**
- Create or extend: `tests/test_api2_universal_tap_only_selector_mobile_v1.py`
- Modify: `app.py`
- Test: existing frozen activation/navigation tests that reference `app.py`

**Interfaces:**
- Consumes: production overlay from Task 3.
- Produces: production `app.py` import of `streamlit_memory_lazy_router_universal_tap_only_v1` while preserving required frozen compatibility markers.

- [ ] **Step 1: Write the mobile no-editable-element contract**

Use Streamlit/AppTest where practical, otherwise the closest deterministic rendered-surface contract available in-repo, to open a representative ordinary selector and assert the selector path exposes buttons/popover controls but no editable text/search/combobox input. Add a companion assertion that intentional `st.text_input` or `accept_new_options=True` remains typing-capable.

- [ ] **Step 2: Run the mobile contract and confirm RED**

Run: `python -m pytest -q tests/test_api2_universal_tap_only_selector_mobile_v1.py`

Expected: FAIL until the universal overlay is the production entrypoint.

- [ ] **Step 3: Preflight frozen `app.py` ownership**

Read the frozen artifact registry, identify every frozen checkpoint owning the current `app.py` blob, compute current-main and candidate `app.py` blobs, and acquire one legal thaw for this exact workstream/path before publishing the activation change. Do not mutate any unrelated frozen artifact.

- [ ] **Step 4: Activate the universal overlay in `app.py`**

Change only the production bootstrap import to the Task-3 overlay and preserve any compatibility import marker required by existing frozen tests. No page-specific sports files are modified.

- [ ] **Step 5: Run mobile + activation + navigation regression**

Run:
`python -m py_compile app.py universal_tap_only_selector_v1.py streamlit_memory_lazy_router_universal_tap_only_v1.py`

Then run Task 1–4 focused tests plus the Universal Nav regression suite. Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add app.py tests/test_api2_universal_tap_only_selector_mobile_v1.py
git commit -m "feat: activate universal tap-only selectors"
```

### Task 5: Exact-head proof contract, merge, refreeze, and durable closeout

**Files:**
- Create: `devsystem/runless_proof_plans/api2-universal-tap-only-selector-v1.json`
- Finalize through existing frozen registry and finalization ledger; no new product files beyond Tasks 1–4.

**Interfaces:**
- Consumes: final candidate from Tasks 1–4.
- Produces: exact Runless proof/receipt/gate, exact-candidate merge, frozen-registry forward-port, finalization-ledger record, and durable `GREEN_FROZEN` read-back.

- [ ] **Step 1: Write the proof plan**

Bind `source_main_sha` to the then-current main; include py_compile for the adapter/overlay/app, Task 1–4 tests, Universal Nav regressions, required check `runless-final-gate`, required app `5204253`, `github_actions_fallback: 0`, and freeze token `API2_UNIVERSAL_TAP_ONLY_SELECTOR_V1_FROZEN`.

- [ ] **Step 2: Reconcile to current main exactly once before proof if needed**

If main advanced, merge current main into the same workstream branch once, rerun the proof-plan commands, and update only the proof plan's `source_main_sha`. Do not create a second branch/PR/proof lane.

- [ ] **Step 3: Open/reuse one PR and run one exact-head Runless proof**

Require proof state `MERGE_AUTHORIZED`, a fresh receipt digest, and a successful `runless-final-gate` on the exact candidate from GitHub App `5204253` before merge.

- [ ] **Step 4: Merge only the authorized candidate**

Use expected-head merge protection. Read `main` back and prove the authorized candidate is an ancestor of the returned merge commit.

- [ ] **Step 5: Run merged-main regression**

Run the exact Task 1–4 focused suites and compile commands from `main`. Expected: PASS.

- [ ] **Step 6: Forward-port and retire the `app.py` thaw**

Use the existing registry forward-port transport with the exact old/new `app.py` blobs and merged-main SHA. Read back zero active thaw matches for this workstream and confirm all protected `app.py` registry entries point to the merged blob.

- [ ] **Step 7: Write the finalization-ledger record**

Create one immutable record for `API2_UNIVERSAL_TAP_ONLY_SELECTOR_V1_FROZEN`, advance the ledger by one valid revision, and validate the manifest transition against the prior state hash before closeout.

- [ ] **Step 8: Close Runless to durable `GREEN_FROZEN`**

Submit exact candidate, merged-main SHA, freeze token, receipt/gate evidence, and manifest state hash through the existing closeout transport. Expected: `GREEN_FROZEN`, `failure_class=NONE`.

- [ ] **Step 9: Release the scope-aware execution lease and perform independent final read-back**

Verify: PR merged; `main` exact; proof `GREEN_FROZEN`; final ledger token/hash exact; no active thaw for this workstream; live Runless execution leases `0`; this API 2 scope lease absent; unrelated workstream leases preserved.

- [ ] **Step 10: Final completion report**

Only after Step 9, report exact candidate SHA, merged-main SHA, proof ID, receipt digest, gate run ID, freeze token, ledger revision/hash, merged-main test counts, and `🟢 100% GREEN + ❄️ FROZEN`.
