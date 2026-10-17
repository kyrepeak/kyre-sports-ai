# API 2 Universal Tap-Only Selector V1 — Design Specification

**Status:** Design approved in chat; written spec pending user review. Implementation is not yet authorized.

## Goal

Create one universal selector behavior for all active sports pages so ordinary game, team, player, market, sort, simulation, and similar finite-choice selectors can be used by tap/click without focusing a searchable text field or summoning the mobile software keyboard.

The behavior must apply consistently across NFL, CFB, NBA, MLB, and WNBA without rewriting each sports page individually.

## User-visible success criteria

1. Tapping a normal finite-choice selector opens tap-only choices and does not summon the iPhone keyboard.
2. Choosing a team, player, game, market, sort option, simulation depth, or comparable finite option works on the first tap.
3. Long player/game lists remain usable without typing by using tap-only pagination.
4. Existing remembered selections, callback behavior, and page navigation continue to work.
5. Intentional text-entry controls still behave normally. `st.text_input`, numeric entry, date controls, and any future selectbox that explicitly enables new free-text options remain typing-capable.
6. No model, projection, probability, sportsbook, data-source, team-ID, player-ID, or game-ID behavior changes.

## Current state and root cause

The current production stack contains many ordinary `st.selectbox` calls across multiple sports pages. On mobile, Streamlit renders/selects these through a focusable searchable control, which can cause iOS to display the software keyboard even when the user only wants to choose an existing option.

NFL Spread already contains a local tap-only compatibility helper that renders a popover plus buttons specifically for the NFL market selector. That proves the desired interaction works, but ownership is too narrow. Other NFL, CFB, NBA, MLB, and WNBA selectors still use ordinary selectboxes.

The repair should therefore move the interaction rule to a shared layer above the nested sports routers rather than duplicate page-specific fixes.

## Architecture

### 1. Shared adapter: `universal_tap_only_selector_v1.py`

Add one focused module that owns the replacement behavior for ordinary `st.selectbox` calls.

Primary interface:

```python
@contextmanager
def install_universal_tap_only_selectboxes():
    ...
```

The context manager temporarily replaces `st.selectbox` with a compatibility bridge for the duration of the sports app render and always restores the original function in `finally`.

The bridge preserves the public behaviors that active sports pages depend on:

- `label`
- `options`
- `index`
- `format_func`
- `key`
- `help`
- `on_change`
- callback `args` / `kwargs`
- `placeholder`
- `disabled`
- `label_visibility`
- width/container-width behavior where supported by the installed Streamlit version

The adapter returns the original raw option value, not its formatted label.

### 2. Tap-only rendering

For ordinary finite-choice selectboxes, the adapter renders:

- the normal selector label according to `label_visibility`;
- a popover trigger showing the current formatted value or placeholder;
- tap/click choices implemented with non-text buttons;
- no text field, combobox, search input, or keyboard-focusable editable element.

Selecting an option uses a button callback that:

1. writes the raw option to the caller's session-state key;
2. updates internal pagination state if needed;
3. invokes the caller's original `on_change(*args, **kwargs)` exactly once when supplied.

The selection relies on Streamlit's normal widget rerun. The adapter must not call `st.rerun()` merely to apply a selection.

### 3. Long-list behavior

Large player/game lists cannot become a wall of hundreds of buttons.

Use adaptive rendering:

- up to 20 options: show all choices;
- more than 20 options: show a tap-only page of 20 choices plus Previous / Next controls and a compact `items X–Y of N` indicator;
- when the current selection exists, open on the page containing that selection;
- page controls never modify the caller's selected value;
- no search field is introduced automatically.

This keeps the keyboard closed while keeping long lists practical.

### 4. Intentional typing exception

If a future call explicitly uses `accept_new_options=True`, it is intentionally asking for free-text entry. In that case the bridge delegates to the original Streamlit selectbox unchanged.

This is the only selectbox-level typing exception in V1.

Existing explicit text-entry widgets such as `st.text_input`, `st.text_area`, and numeric/date entry are outside this architecture and remain untouched.

### 5. Stable identity and state

If a caller supplies `key`, that key remains authoritative.

If no explicit key is supplied, the adapter derives a deterministic internal key from the source callsite plus label. This avoids collisions between repeated labels while remaining stable across Streamlit reruns.

The adapter validates the stored session-state value against the current options on every render:

- if valid, preserve it;
- if invalid and `index` points to a valid option, select that option;
- if `index is None`, preserve an unselected state and show the placeholder;
- if options are empty, show a disabled placeholder and return `None`.

Duplicate formatted labels are allowed because selection identity is based on option position/raw option, not display text.

### 6. Production router ownership

Add a thin production overlay:

`streamlit_memory_lazy_router_universal_tap_only_v1.py`

Its responsibility is only:

```text
install universal tap-only selector bridge
    -> delegate to current Universal Nav V2 / existing router stack
    -> restore original Streamlit selectbox
```

The existing Universal Navigation V2 remains responsible for sport/market route authority. This new layer does not resolve routes, clear query parameters, load sports data, or choose page content.

`app.py` will forward-port to the new overlay through the repository's normal frozen-artifact thaw/forward-port process because `app.py` is already frozen by older certified workstreams.

### 7. Existing NFL-specific helper

Do not delete or rewrite the existing NFL Spread tap-only market helper in this workstream. It remains as frozen compatibility underneath the new layer.

During nested rendering it may still own its exact NFL market control, while all other selectboxes delegate through the universal bridge. A future cleanup can remove duplication only after independent proof that no frozen caller depends on the local helper.

## Data flow

```text
app.py
  -> Universal Tap-Only Overlay V1
      -> install_universal_tap_only_selectboxes()
          -> Universal Navigation V2
              -> existing nested NFL / CFB / NBA / MLB / WNBA routers
                  -> page calls st.selectbox(...)
                      -> universal tap-only bridge
                          -> popover + tap buttons
                          -> update caller key in callback
                          -> optional caller on_change
                  -> page receives selected raw option
      -> restore original st.selectbox in finally
```

No new network request, data provider, background job, model calculation, or sportsbook call is introduced by the selector layer.

## Performance requirements

1. Selector installation must be O(1).
2. Short lists render only their finite options.
3. Long lists render at most 20 option buttons plus navigation controls per open selector page.
4. No manual extra rerun after a selection.
5. No network request is performed to render or change a selector.
6. The adapter must not import sports page modules eagerly; it sits above the router and remains data-agnostic.

## Accessibility and mobile behavior

- All choices are native Streamlit button/popover interactions with normal keyboard/touch accessibility.
- Touch targets should remain large enough for mobile use through Streamlit's standard button layout.
- Disabled selectors remain disabled.
- Help text and label visibility are preserved where the Streamlit API supports them.
- The adapter must not use CSS or JavaScript tricks to suppress the iOS keyboard. The keyboard stays closed because no editable input is rendered for ordinary selectors.

## Error handling

The layer fails closed around application integrity:

- the original `st.selectbox` is always restored in `finally`;
- callback exceptions propagate normally rather than being swallowed;
- invalid stored values are reconciled to the requested index/placeholder instead of crashing;
- unsupported intentional free-text behavior delegates to the original selectbox;
- malformed option iterables raise a clear adapter error before mutating caller state;
- internal pagination keys are namespaced and never overwrite caller keys.

The adapter must not silently fall back to a searchable selectbox for an ordinary finite selector, because that would reintroduce the mobile keyboard bug without visibility.

## Testing and proof

### Unit contract

Create focused tests for:

1. short-list tap-only rendering;
2. long-list pagination and page boundaries;
3. current-selection page restoration;
4. raw option return with `format_func`;
5. explicit key state preservation;
6. deterministic no-key callsite identity;
7. `index=None` and placeholder behavior;
8. empty options;
9. disabled behavior;
10. callback called exactly once with args/kwargs;
11. no manual `st.rerun()`;
12. `accept_new_options=True` delegates to original typing-capable selectbox;
13. bridge restoration after normal render and after exception;
14. duplicate formatted labels do not change identity.

### Cross-sport regression

Representative active selector paths must be proven for every sport:

- NFL: matchup/game or player selector;
- CFB: matchup selector;
- NBA: game/player selector;
- MLB: matchup/game selector;
- WNBA: game/player/team selector.

The proof does not require live provider calls. Tests may use fakes/fixtures while asserting that those page-level `st.selectbox` calls are intercepted by the universal bridge and return the expected raw value.

### Mobile DOM contract

Add a browser/AppTest-level contract where practical that opens a representative selector and verifies the ordinary tap-only selector surface contains no editable `input`/search/combobox element. Because software-keyboard visibility itself is platform-owned and is not reliably observable in headless automation, absence of an editable selector element is the deterministic proof target.

### Regression

Run the existing Universal Navigation V1/V2 suites, active sports selector tests, and compilation checks. Existing model/projection/data tests must remain unchanged.

## Frozen-state and finalization contract

Implementation must use the existing API 2 control-plane rules:

- one active problem and one authoritative branch/PR/proof chain;
- acquire a scope-aware execution lease before implementation writes;
- preserve frozen artifacts and use a legal thaw/forward-port for `app.py` if its blob changes;
- exact-head Runless proof with required `runless-final-gate` from GitHub App 5204253;
- GitHub Actions fallback 0;
- exact candidate merge only;
- merged-main regression;
- frozen-registry read-back;
- finalization-ledger transaction;
- durable Runless closeout to `GREEN_FROZEN`;
- lease release and independent final read-back before claiming 100%.

Proposed freeze token:

`API2_UNIVERSAL_TAP_ONLY_SELECTOR_V1_FROZEN`

## Expected implementation surfaces

Create:

- `universal_tap_only_selector_v1.py`
- `streamlit_memory_lazy_router_universal_tap_only_v1.py`
- `tests/test_universal_tap_only_selector_v1.py`
- `tests/test_api2_universal_tap_only_selector_cross_sport_v1.py`
- `devsystem/runless_proof_plans/api2-universal-tap-only-selector-v1.json`

Modify:

- `app.py` only for the production overlay activation / compatibility marker required by frozen tests.

Do not mass-edit individual sports pages in V1.

## Non-goals

- No redesign of player, game, or team cards.
- No sports data/provider changes.
- No model or probability changes.
- No URL/router authority changes beyond installing the selector layer around the already-certified Universal Navigation V2 stack.
- No custom JavaScript keyboard suppression.
- No CSS hacks targeting iOS keyboard behavior.
- No automatic free-text search feature.
- No deletion of frozen NFL-specific compatibility code.

## Rollout order

1. Add tests first and confirm RED.
2. Implement the shared adapter.
3. Add the thin production overlay.
4. Prove cross-sport interception with fixtures.
5. Forward-port `app.py` through the legal frozen-registry path.
6. Run exact branch tests/compile.
7. Open/reuse one PR and issue one exact-head Runless proof.
8. Merge the exact authorized candidate.
9. Verify merged `main`.
10. Freeze/read back the artifact registry and finalization ledger.
11. Close Runless to `GREEN_FROZEN` and release the scope lease.

## Completion definition

The workstream is complete only when ordinary finite-choice selectors across active NFL, CFB, NBA, MLB, and WNBA routes are owned by the universal tap-only layer, representative cross-sport tests prove that behavior, merged-main verification passes, the frozen registry is reconciled, and the durable Runless proof reads back `GREEN_FROZEN` with no live execution lease.
