# CFB Player Props Page 2 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Page 2 of the three-page CFB Player Props experience as an exact-game, player-first command board with verified offensive rosters, multi-book prop coverage, compact matchup intelligence, frozen Kyre signal previews, and a stable future Page-3 handoff.

**Architecture:** Preserve frozen Page 1 behind a new `cfb_player_props_runtime_v2.py` terminal wrapper. Reconstruct one exact selected game from the existing Page-1 handoff and Schedule V4, then compose new Page-2 orchestration modules over frozen player identity, sportsbook, history, model, logo, and CFB team-stat/matchup owners. Do not fork model math or create a second game/player identity system.

**Tech Stack:** Python 3, Streamlit, Universal Runtime V5 + Atomic Navigation, `cfb_schedule_v4`, ESPN CFB roster/event data, frozen CFB player-prop transports/identity/history/model, NCAA/CFB team-data + matchup engines, pytest, Runless V2, Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-20-cfb-player-props-page2-v1-design.md`

## Global Constraints

- Page 2 only. Do not implement the Page-3 Line Lab, slider, simulations, editable user lines, or deep charts.
- Preserve frozen Page 1 behavior when no canonical `game_id` exists.
- Canonical game authority is the exact official CFB game ID. Sportsbook event IDs are aliases only.
- Canonical player authority is `cfb_player_props_identity_v1.CanonicalPlayerIdentity`; fuzzy similarity never certifies a player.
- Use `cfb_schedule_v4.games_for_date(date)` for exact-game reconstruction.
- Reuse frozen prop transports: `cfb_player_props_sportsgameodds_v1.fetch_sgo_cfb_player_props` and `cfb_player_props_fanduel_v1.fetch_fanduel_cfb_player_props`.
- Reuse frozen normalization/merge: `cfb_player_props_market_v1.PropObservation`, `normalize_prop_observation`, and `merge_prop_observations`.
- Reuse frozen history/model math unchanged: minimum 4 verified completed games, maximum 8, decay 0.85, sportsbook projection influence `0.0`.
- Availability is `OUT`, `DOUBTFUL`, `QUESTIONABLE`, explicit `AVAILABLE`, or `UNVERIFIED`; missing status must never become healthy/available by inference.
- Opening/current movement is display-only and may be shown only from true provider opening evidence; first-seen-in-session is not an opening line.
- Reuse existing CFB logo owners; do not create a new logo authority.
- Reuse `cfb_team_data_v2.load_matchup_team_data` and `cfb_over_under_matchup_engine_v1.build_matchup_engine` for defensive context; Page-2 matchup labels are presentation-only and must not modify the frozen player projection.
- `app.py` remains untouched. Do not modify NFL Daily Picks V4 product files.
- No background Page-1 slate render while Page 2 is selected; no unrelated sport/market prefetch.
- Final freeze token: `MONSTER_CFB_PLAYER_PROPS_PAGE2_V1_FROZEN`.

## Review Focus

1. **Valid `game_id` but wrong/stale Page-1 team IDs:** Page 2 must reject the mismatch rather than silently display another matchup. Task 1 pins this.
2. **Verified roster player has zero posted props:** player remains visible with `No verified props posted yet.` Task 5 pins this.
3. **Sportsbook partial outage or one stale provider:** remaining verified books render and stale rows cannot overwrite fresher observations. Task 3 pins this.
4. **No explicit injury status:** availability must be `UNVERIFIED`, never `AVAILABLE`. Task 2 pins this.
5. **Tap Analyze on selection A after route generation advances to selection B:** stale selection A cannot replace B; sportsbook IDs remain provenance only. Task 5 pins this.

---

### Task 0: Step-2A authority and narrow Page-2 scope lease

**Files:**
- Read/claim only: `devsystem/scope_aware_execution_lease_state_v1.json` on `monster-scope-aware-execution-leases`

**Interfaces:**
- Consumes: current `main`, branch `monster-cfb-player-props-page2-v1`, current PR/proof state, current live leases, frozen registry/finalization ownership.
- Produces: one authoritative mutation chain and one non-overlapping lease before the first test/product mutation.

- [ ] **Step 1: Read authority once**

Confirm current `main`, current Page-2 branch head, no duplicate Page-2 PR/proof path, and current lease holders.

- [ ] **Step 2: Claim the Page-2 write scope**

Lease these paths only:
- `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- `cfb_player_props_runtime_v2.py`
- `cfb_player_props_page2_context_v1.py`
- `cfb_player_props_page2_roster_v1.py`
- `cfb_player_props_page2_availability_v1.py`
- `cfb_player_props_page2_market_v1.py`
- `cfb_player_props_page2_matchup_v1.py`
- `cfb_player_props_page2_handoff_v1.py`
- `cfb_player_props_page2_v1.py`
- `tests/test_cfb_player_props_page2_context_v1.py`
- `tests/test_cfb_player_props_page2_roster_v1.py`
- `tests/test_cfb_player_props_page2_market_v1.py`
- `tests/test_cfb_player_props_page2_matchup_v1.py`
- `tests/test_cfb_player_props_page2_handoff_v1.py`
- `tests/test_cfb_player_props_page2_v1.py`
- `tests/test_cfb_player_props_page2_integration_v1.py`
- Page-1 route/integration tests only if their frozen exact adapter assertion must be updated to the runtime wrapper contract
- `devsystem/task_ledgers/monster-cfb-player-props-page2-v1.json`
- `devsystem/runless_proof_plans/monster-cfb-player-props-page2-v1.json`

Dependency/shared tokens: `domain:cfb`, `route:cfb:player-props`, `runtime:universal-v5`, `data:cfb-player-props-frozen-v1`.

- [ ] **Step 3: Persist and read back once**

If overlap exists, classify the conflict and do not spawn another lane. Otherwise persist one lease with CAS and read back that lease once.

---

### Task 1: Runtime wrapper, exact selected-game context, and Back contract

**Files:**
- Create: `cfb_player_props_runtime_v2.py`
- Create: `cfb_player_props_page2_context_v1.py`
- Modify: `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- Test: `tests/test_cfb_player_props_page2_context_v1.py`
- Test/update only if needed: `tests/test_cfb_player_props_page1_route_v1.py`, `tests/test_cfb_player_props_page1_integration_v1.py`

**Interfaces:**
- Consumes: `cfb_player_props_page1_handoff_v1.SESSION_HANDOFF_KEY`, query/session `date` + `game_id`, `cfb_schedule_v4.games_for_date`, frozen Page-1 renderer.
- Produces:
  - `resolve_page2_context(session: Mapping[str, Any], query: Mapping[str, Any], *, schedule_reader: Callable[[Any], list[dict[str, Any]]] = cfb_schedule_v4.games_for_date) -> dict[str, Any]`
  - `clear_page2_selection(session: MutableMapping[str, Any], query: MutableMapping[str, Any]) -> None`
  - `render_cfb_player_props_runtime() -> None`

- [ ] **Step 1: Write RED context/runtime tests**

Assert:
- no `game_id` delegates to `cfb_player_props_page1_v1.render_cfb_player_props_page1()` exactly once;
- `date` + official `game_id` loads exactly that date and exactly one matching official game;
- provider event IDs cannot match navigation identity;
- stale Page-1 team IDs conflicting with the reconstructed game produce `state="invalid"`;
- missing selected game produces `state="unavailable"` and never substitutes another game;
- `clear_page2_selection` removes only `game_id`, `player_id`, `prop`, Page-2 filter/handoff state and preserves `sport=cfb`, `market=player-props`, valid `date`;
- CFB player-props destination adapter now imports `cfb_player_props_runtime_v2` with source version `CFB_PLAYER_PROPS_RUNTIME_V2`; all other routes delegate unchanged.

- [ ] **Step 2: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page2_context_v1.py tests/test_cfb_player_props_page1_route_v1.py tests/test_cfb_player_props_page1_integration_v1.py`

Expected: Page-2 module/wrapper assertions fail while existing Page-1 behavior remains green except exact old adapter-source pins.

- [ ] **Step 3: Implement exact context**

`resolve_page2_context` requires canonical date/game ID, reads Schedule V4 once, exact-matches `game_id`/official identity, validates handoff team IDs when present, normalizes Page-2 context including team IDs/names, records/ranks, kickoff/status, venue/broadcast, and retains canonical kickoff timestamp plus Phoenix-local presentation time.

- [ ] **Step 4: Implement wrapper + Back state helper**

`render_cfb_player_props_runtime()` decides Page 1 vs Page 2 from canonical `game_id`; it must not render Page 1 in the background when Page 2 is active. Update only the existing CFB player-props destination adapter to import the wrapper.

- [ ] **Step 5: Run GREEN**

Run the Task-1 tests plus current Universal Atomic Navigation tests. Expected PASS.

- [ ] **Step 6: Commit**

Commit: `feat: add CFB player props Page 2 runtime context`

---

### Task 2: Verified offensive roster + fail-closed availability

**Files:**
- Create: `cfb_player_props_page2_roster_v1.py`
- Create: `cfb_player_props_page2_availability_v1.py`
- Test: `tests/test_cfb_player_props_page2_roster_v1.py`

**Interfaces:**
- Consumes: exact Page-2 context team IDs, ESPN CFB roster endpoint, optional exact event/roster status payload, `CanonicalPlayerIdentity`, `player_identity_from_roster_row`.
- Produces:
  - `Page2Player` frozen dataclass containing canonical identity + jersey/headshot/class metadata
  - `load_offensive_roster(context: Mapping[str, Any]) -> dict[str, list[Page2Player]]`
  - `normalize_availability(*payloads: Mapping[str, Any], player_id: str) -> dict[str, Any]`
  - `load_game_availability(context: Mapping[str, Any], players: Sequence[Page2Player]) -> dict[str, dict[str, Any]]`

- [ ] **Step 1: Write RED roster tests**

Assert only QB/RB/WR/TE survive the primary board, ESPN athlete ID/team ID remain canonical, jersey/class/headshot are optional verified metadata, duplicate roster rows collapse by official player ID, and missing headshot becomes empty metadata rather than a fabricated URL.

- [ ] **Step 2: Write RED availability tests**

Assert explicit OUT/DOUBTFUL/QUESTIONABLE states normalize correctly; explicit active/available may become `AVAILABLE`; missing/ambiguous status becomes `UNVERIFIED`; recent stats, sportsbook prices, or roster presence alone can never produce `AVAILABLE`; OUT players remain in the roster.

- [ ] **Step 3: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page2_roster_v1.py`

Expected: missing Page-2 roster/availability modules.

- [ ] **Step 4: Implement cached roster owner**

Fetch each official team roster at most once per cache TTL, walk ESPN roster shapes defensively, call frozen identity normalization, and enrich the resulting Page2Player without changing `CanonicalPlayerIdentity` itself.

- [ ] **Step 5: Implement fail-closed availability**

Use only exact event/player status evidence. Preserve source/provenance and raw label. Default `UNVERIFIED`.

- [ ] **Step 6: Run GREEN and commit**

Expected PASS. Commit: `feat: add verified CFB Page 2 roster availability`

---

### Task 3: Exact-game multi-book prop aggregation, best lines, and truthful movement

**Files:**
- Create: `cfb_player_props_page2_market_v1.py`
- Test: `tests/test_cfb_player_props_page2_market_v1.py`

**Interfaces:**
- Consumes: selected game/context, Page2Player identities, frozen SGO/FanDuel raw rows, frozen `normalize_prop_observation`, `merge_prop_observations`, `cfb_player_props_model_v1.build_market_consensus`.
- Produces:
  - `load_game_prop_observations(context: Mapping[str, Any], players: Sequence[Page2Player]) -> list[PropObservation]`
  - `build_player_market_view(player: Page2Player, market_key: str, observations: Sequence[PropObservation], *, opening_rows: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]`
  - `group_player_markets(players: Sequence[Page2Player], observations: Sequence[PropObservation]) -> dict[str, list[dict[str, Any]]]`

- [ ] **Step 1: Write RED aggregation tests**

Assert only exact official game + exact canonical player rows survive; all six frozen market keys are supported; partial provider outage still renders other verified rows; stale observations cannot replace fresher book/side rows.

- [ ] **Step 2: Pin best-line rules**

For comparable verified rows:
- Over chooses the lowest line; if tied, choose the better American price for the bettor;
- Under chooses the highest line; if tied, choose the better American price;
- missing/invalid line is never a candidate;
- book count is unique verified sportsbooks;
- consensus line is frozen median consensus output, not recomputed with a new formula.

- [ ] **Step 3: Pin movement fail-closed behavior**

Without explicitly trusted opening/current evidence, movement is `available=False`; first-seen/session snapshots are never promoted to opening. With paired verified opening/current evidence for the same book/player/market, return opening, current, delta, and source provenance.

- [ ] **Step 4: Run RED**

Run Task-3 test; expected missing module/functions.

- [ ] **Step 5: Implement minimal Page-2 aggregation**

Fetch each sportsbook provider once per render/cache cycle, bind through the frozen official game/player identity rules, merge with frozen freshness semantics, then filter/group locally.

- [ ] **Step 6: Run GREEN and commit**

Commit: `feat: add CFB Page 2 multi-book prop aggregation`

---

### Task 4: Recent production, frozen Kyre preview, and opponent-defense context

**Files:**
- Create: `cfb_player_props_page2_matchup_v1.py`
- Test: `tests/test_cfb_player_props_page2_matchup_v1.py`

**Interfaces:**
- Consumes: `cfb_player_props_history_v1.load_verified_player_history`, frozen Page-1 model functions, `cfb_team_data_v2.load_matchup_team_data`, `cfb_over_under_matchup_engine_v1.build_matchup_engine`.
- Produces:
  - `build_recent_production(player: Page2Player, market_key: str, *, season: int) -> dict[str, Any]`
  - `build_page2_signal(player: Page2Player, market_key: str, history: Sequence[Mapping[str, Any]], observations: Sequence[PropObservation]) -> dict[str, Any]`
  - `load_game_matchup_context(context: Mapping[str, Any]) -> dict[str, Any]`
  - `grade_player_matchup(player: Page2Player, market_key: str, matchup_context: Mapping[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write RED recent/model reuse tests**

Assert recent preview exposes at most the frozen 8-game verified window and last-3 values when available; 0–3 verified games keep probability unavailable; model projection, uncertainty, probability, and edge match direct frozen Page-1 model calls exactly; sportsbook projection influence remains `0.0`.

- [ ] **Step 2: Write RED defensive mapping tests**

Pin mapping:
- passing yards / passing TD QB -> opponent passing defense;
- RB rushing yards -> opponent rushing defense;
- WR/TE receiving yards/receptions -> opponent passing defense;
- touchdown market -> only supported rushing/receiving context;
- missing opponent evidence -> `CHECK` with `Defense data unavailable`.

Assert matchup grade is presentation-only and does not modify projection/probability.

- [ ] **Step 3: Run RED**

Run Task-4 tests; expected missing Page-2 matchup functions.

- [ ] **Step 4: Implement matchup evidence reuse**

Call `cfb_team_data_v2.load_matchup_team_data(context, context["game_date"])`, pass away/home profiles to `cfb_over_under_matchup_engine_v1.build_matchup_engine`, and reduce only the relevant verified defensive dimension into `FAVORABLE`, `NEUTRAL`, `TOUGH`, or `CHECK`. Do not call `apply_to_raw` and do not feed this label into the player-prop model.

- [ ] **Step 5: Implement recent/signal wrappers as pure delegation**

Do not copy model formulas. Delegate to frozen history/model functions and attach Page-2 presentation metadata only.

- [ ] **Step 6: Run GREEN and commit**

Commit: `feat: add CFB Page 2 player matchup intelligence`

---

### Task 5: Professional player-first Page 2 + future Page-3 handoff

**Files:**
- Create: `cfb_player_props_page2_handoff_v1.py`
- Create: `cfb_player_props_page2_v1.py`
- Test: `tests/test_cfb_player_props_page2_handoff_v1.py`
- Test: `tests/test_cfb_player_props_page2_v1.py`

**Interfaces:**
- Consumes: Tasks 1–4 outputs, existing CFB logo resolvers.
- Produces:
  - `build_selected_prop_handoff(context: Mapping[str, Any], player: Page2Player, market: Mapping[str, Any], *, generation: int) -> dict[str, Any]`
  - `commit_selected_prop_handoff(session: MutableMapping[str, Any], query: MutableMapping[str, Any], payload: Mapping[str, Any]) -> None`
  - `render_cfb_player_props_page2() -> None`

- [ ] **Step 1: Write RED handoff tests**

Assert payload contains route version, date, official game ID, away/home team IDs, canonical player ID/name/team ID, canonical market key, optional consensus line, generation, selection timestamp/state. Provider sportsbook IDs may appear only under provenance metadata and never replace canonical IDs. Newer generation wins; stale generation cannot overwrite.

- [ ] **Step 2: Write RED Page-2 presentation tests**

Assert the rendered contract contains:
- one Page-2 selected-matchup hero and one Back action;
- exact selected game only;
- ALL/QB/RB/WR/TE tap-only filter;
- away/home team sections with logos;
- verified headshot or neutral monogram per displayed player;
- truthful availability state;
- player with zero props remains visible with exact copy `No verified props posted yet.`;
- supported prop rows show consensus, best Over, best Under, verified book count, movement only when available, recent production, matchup badge, Kyre signal or truthful readiness copy;
- one `Analyze` action per displayed prop that commits the Page-3 handoff but does not implement the Line Lab;
- invalid-game shell says `Selected game is unavailable. Return to Player Props.`;
- roster outage shell says `Verified roster temporarily unavailable.`;
- responsive CSS includes stack-to-one-column behavior at mobile width and no keyboard/text-input controls.

- [ ] **Step 3: Run RED**

Run Task-5 tests; expected missing Page-2 UI/handoff.

- [ ] **Step 4: Implement Page-2 orchestration**

Render hero first, then position filter, two-team player board (stacked on mobile), compact prop rows, and compact game matchup intelligence. History calls are lazy: only verified players with displayed markets get player-history requests. Page 1 must not render while Page 2 is active.

- [ ] **Step 5: Implement Back + Analyze actions**

Back calls Task-1 state clearer and reruns to frozen Page 1. Analyze commits only the future Page-3 handoff/session/query selection; Page 2 remains the current implemented screen until Page 3 is separately built.

- [ ] **Step 6: Run GREEN and commit**

Commit: `feat: build CFB Player Props Page 2 command board`

---

### Task 6: Integration/regression, control-plane seal, exact-head proof, merge, freeze

**Files:**
- Create: `tests/test_cfb_player_props_page2_integration_v1.py`
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page2-v1.json`
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page2-v1.json`
- Modify only stale exact assertions in Page-1 route/integration tests if required by the new wrapper; do not weaken behavioral assertions.

**Interfaces:**
- Consumes: Tasks 1–5 exact product surface, current Universal Runtime V5/Atomic Navigation, Runless V2, Finalization Ledger V2.
- Produces: one exact candidate, one PR, one proof chain, merged-main verification, freeze/read-back, lease release, terminal `GREEN_FROZEN`.

- [ ] **Step 1: Write integration RED/GREEN assertions**

Pin:
- CFB `player-props` still has one canonical destination and now loads runtime V2;
- no `game_id` preserves frozen Page 1 behavior;
- `game_id` renders Page 2 only;
- `app.py` remains unchanged;
- Page-3 Line Lab module does not exist in this scope;
- `SPORTSBOOK_PROJECTION_INFLUENCE == 0.0` remains frozen;
- no non-selected destination prefetch is introduced;
- control-plane files bind `MONSTER_CFB_PLAYER_PROPS_PAGE2_V1_FROZEN`.

- [ ] **Step 2: Run the focused Page-2 + frozen Page-1 regression bundle**

At minimum:
`python -m pytest --noconftest -q tests/test_cfb_player_props_page2_context_v1.py tests/test_cfb_player_props_page2_roster_v1.py tests/test_cfb_player_props_page2_market_v1.py tests/test_cfb_player_props_page2_matchup_v1.py tests/test_cfb_player_props_page2_handoff_v1.py tests/test_cfb_player_props_page2_v1.py tests/test_cfb_player_props_page2_integration_v1.py tests/test_cfb_player_props_page1_route_v1.py tests/test_cfb_player_props_page1_slate_v1.py tests/test_cfb_player_props_page1_handoff_v1.py tests/test_cfb_player_props_identity_v1.py tests/test_cfb_player_props_market_v1.py tests/test_cfb_player_props_model_v1.py tests/test_cfb_player_props_page1_v1.py tests/test_cfb_player_props_page1_integration_v1.py tests/test_universal_atomic_navigation_v1.py tests/test_universal_atomic_navigation_terminal_inheritance_v1.py tests/test_api2_nfl_daily_picks_v4_atomic_inheritance.py`

Document only genuinely obsolete baseline pins; never roll current production backward to satisfy stale exact-version assertions.

- [ ] **Step 3: Compile + runtime cert**

Compile all new Page-2 modules and run `python -m devsystem.api2_universal_runtime_v5_cert`. Expected GREEN.

- [ ] **Step 4: Seal Runless plan**

Runless commands must use approved shapes only: `python -m py_compile`, `python -m pytest`, and `python -m devsystem.api2_universal_runtime_v5_cert`. `public_runtime_required=false` unless a separately approved public probe becomes necessary.

- [ ] **Step 5: Exact-head Step 2A closeout**

Read current `main`/lease/PR/proof state once. If base drift exists, classify and reconcile the same branch; do not create a parallel branch/PR. Verify the final remote SHA once, open/reuse exactly one PR, lookup durable proof state, and submit one proof only if none exists.

- [ ] **Step 6: Merge and freeze**

After `runless-final-gate` from App ID `5204253` succeeds on the exact candidate, merge with expected-head guard. Verify merged-main parents. Create Finalization Ledger V2 record + monotonic manifest for `MONSTER_CFB_PLAYER_PROPS_PAGE2_V1_FROZEN`, read it back, call secret-safe Runless closeout, retire any required thaw/forward-port, release the Page-2 lease, read back lease absence, and stop only at terminal `GREEN_FROZEN` / failure `NONE`.
