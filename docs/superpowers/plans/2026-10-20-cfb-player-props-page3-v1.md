# CFB Player Props Page 3 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Page 3 of CFB Player Props as an exact-player, exact-market intelligence lab with a custom Line Lab, multi-book market evidence, recent production, matchup/opportunity context, deterministic reasoning, and reliable Back/TOP navigation.

**Architecture:** Add an isolated `cfb_player_props_runtime_v3.py` selector that delegates to frozen Page 1 and Page 2 and renders a new Page 3 only when canonical `game_id + player_id + prop` are complete. Reuse the existing Page-2 context, roster, market, matchup, handoff, history, and frozen model owners; Page 3 may evaluate the frozen projection at a user-selected threshold but may not modify projection math or feed sportsbook lines into the projection.

**Tech Stack:** Python 3, Streamlit, Universal Runtime V5 + Atomic Navigation, existing CFB Player Props identity/market/history/model owners, existing CFB matchup/team-data owners, pytest, Runless V2, Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-20-cfb-player-props-page3-v1-design.md`

## Global Constraints

- Canonical Page-3 identity is `date + official game_id + official player_id + canonical prop market key`.
- Provider event/player/market IDs are provenance only.
- Runtime routing is exclusive: no game -> Page 1; game only/incomplete player+prop -> Page 2; complete game+player+prop -> Page 3.
- **← Back to Game Props** must clear only Page-3 selection/local state and return to Page 2 for the same game.
- A floating **↑ TOP** control must remain reachable on long screens without mutating route state or opening the keyboard.
- Reuse frozen `cfb_player_props_model_v1` constants unchanged: `MIN_SAMPLE=4`, `MAX_SAMPLE=8`, `DECAY=0.85`, `SPORTSBOOK_PROJECTION_INFLUENCE=0.0`.
- User-selected Line Lab values change only the evaluated threshold, never the projection mean/uncertainty.
- Current sportsbook rows stay book-specific; missing/null is never converted to `0`.
- Opening movement is display-only and unavailable unless true opening evidence exists.
- Opponent, availability, environment, opportunity, recent-hit-rate, and reasoning evidence are presentation-only in V1 and cannot modify the frozen projection.
- Player-vs-opponent history fails closed when exact opponent metadata is unavailable.
- No keyboard-triggering free-text/number input for primary navigation; market switch and slider are touch-friendly controls.
- Do not modify `app.py` or unrelated sport pages.
- Prefer no mutation to frozen Page 2; use its existing handoff contract.
- Final freeze token: `MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN`.

## Review Focus

1. **Incomplete or stale Page-3 query state:** `game_id` exists but `player_id` or `prop` is absent/mismatched -> Runtime V3 must render Page 2 or an explicit invalid Page-3 state, never another player.
2. **Market disappears after Page-2 selection:** Page 3 preserves canonical player/market identity, shows current evidence as unavailable, and never silently substitutes another market.
3. **Slider boundary/state refresh:** selected line is clamped to the market-specific 0.5-step range and persists across live refreshes only for the same game/player/prop identity.
4. **Model not ready or zero uncertainty:** no custom-line probability is emitted; descriptive history/market sections may still render.
5. **Back/market-switch race:** Back clears Page-3 state without clearing game identity, and a market switch cannot change game/player identity or resurrect stale local slider state.

---

### Task 0: Step-2A authority, freeze ownership, and Page-3 scope lease

**Files:**
- Read/claim only: `devsystem/scope_aware_execution_lease_state_v1.json` on `monster-scope-aware-execution-leases`
- Read only: current finalization/frozen ownership for shared runtime/Page-2 artifacts

**Interfaces:**
- Consumes: current `main`, branch `monster-cfb-player-props-page3-v1`, current PR/proof state, active scope leases, existing Page-2/finalization ownership.
- Produces: exactly one authoritative Page-3 mutation chain and one non-overlapping scope lease.

- [ ] **Step 1: Read authority once**

Confirm current `main`, Page-3 branch head, no duplicate Page-3 PR/proof lane, current live lease holders, and frozen ownership for any shared runtime file that must change.

- [ ] **Step 2: Claim one Page-3 write scope**

Lease only the planned new Page-3 files/tests/control files plus `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py` and any runtime wrapper file proven necessary. Do not lease Page-2 product files unless a failing compatibility test proves a mutation is required.

Dependency/shared tokens: `domain:cfb`, `route:cfb:player-props`, `runtime:universal-v5`, `data:cfb-player-props-frozen-v1`.

- [ ] **Step 3: Persist/read back once**

If overlap exists, classify it and stop rather than spawning a second lane. Otherwise persist one lease with CAS and read back that holder once.

---

### Task 1: Runtime V3 selector, exact Page-3 context, and Back contract

**Files:**
- Create: `cfb_player_props_runtime_v3.py`
- Create: `cfb_player_props_page3_context_v1.py`
- Modify: `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- Test: `tests/test_cfb_player_props_page3_context_v1.py`
- Test: `tests/test_cfb_player_props_runtime_v3.py`

**Interfaces:**
- Consumes: `cfb_player_props_page2_context_v1.resolve_page2_context`, `cfb_player_props_page2_roster_v1.load_offensive_roster`, `cfb_player_props_page2_handoff_v1.SESSION_HANDOFF_KEY`, existing `SUPPORTED_MARKETS`, frozen Page-1/Page-2 renderers.
- Produces:
  - `resolve_page3_context(session: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]`
  - `clear_page3_selection(session: MutableMapping[str, Any], query: MutableMapping[str, Any]) -> None`
  - `switch_page3_market(session: MutableMapping[str, Any], query: MutableMapping[str, Any], market_key: str) -> bool`
  - `render_cfb_player_props_runtime() -> None` in Runtime V3.

- [ ] **Step 1: Write RED runtime/context tests**

Pin: no game -> Page 1 exactly once; game without complete `player_id+prop` -> Page 2 exactly once; complete canonical identity -> Page 3 exactly once; stale player ID or unsupported market never resolves to a different player/market; provider IDs cannot become canonical route identity.

- [ ] **Step 2: Write RED Back + market-switch tests**

Assert Back removes `player_id`, `prop`, Page-3 slider/local-market keys, preserves `sport=cfb`, `market=player-props`, valid date and exact `game_id`; switching market changes only canonical `prop` and clears market-specific local line state.

- [ ] **Step 3: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_context_v1.py tests/test_cfb_player_props_runtime_v3.py`

Expected: missing Runtime V3/Page-3 context functions.

- [ ] **Step 4: Implement exact context + state helpers**

`resolve_page3_context` must reconstruct Page 2 first, exact-match the official player from that game's verified roster, validate canonical market, preserve Page-2 handoff as provenance only, and emit explicit states `ready`, `market_unavailable`, `player_unavailable`, `invalid`, or `unavailable`.

- [ ] **Step 5: Implement Runtime V3 + loader overlay**

Runtime V3 lazily imports Page 3 and delegates frozen Page 1/Page 2 without background rendering. Update only the existing CFB Player Props destination adapter to source version `CFB_PLAYER_PROPS_RUNTIME_V3`.

- [ ] **Step 6: Run GREEN + navigation regressions**

Run Task-1 tests plus current Universal Atomic Navigation/terminal-inheritance tests that apply to the current V4/V5 entrypoint. Expected PASS.

- [ ] **Step 7: Commit**

Commit: `feat: add CFB player props Page 3 runtime context`

---

### Task 2: Frozen-projection Line Lab engine

**Files:**
- Create: `cfb_player_props_page3_line_lab_v1.py`
- Test: `tests/test_cfb_player_props_page3_line_lab_v1.py`

**Interfaces:**
- Consumes: projection dict from `cfb_player_props_model_v1.build_prop_projection` or equivalent frozen signal fields.
- Produces:
  - `market_line_bounds(market_key: str) -> tuple[float, float, float]`
  - `normalize_selected_line(market_key: str, value: Any, *, fallback: float | None = None) -> float`
  - `evaluate_line(projection: Mapping[str, Any], line: float) -> dict[str, Any]`
  - `build_probability_curve(projection: Mapping[str, Any], market_key: str, *, center_line: float, points: int = 21) -> tuple[dict[str, float], ...]`

- [ ] **Step 1: Write RED bounds/normalization tests**

Pin exact 0.5-step ranges: passing yards `0.5–500.5`; rushing/receiving yards `0.5–250.5`; receptions `0.5–20.5`; passing TD `0.5–6.5`; touchdowns `0.5–4.5`. Values clamp and round to legal 0.5 increments.

- [ ] **Step 2: Write RED probability tests**

For a ready projection, Over/Under probabilities sum to 1 within floating tolerance, projection-minus-line margin is exact, and increasing the line monotonically decreases Over probability. For model-not-ready or uncertainty `<=0`, probabilities remain `None`.

- [ ] **Step 3: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_line_lab_v1.py`

- [ ] **Step 4: Implement using frozen Normal-distribution semantics**

Use `statistics.NormalDist(mu=projection, sigma=uncertainty)` only after frozen readiness checks. Do not read sportsbook observations inside this module.

- [ ] **Step 5: Run GREEN + direct frozen-model equivalence tests**

At the consensus line, Page-3 probability must match frozen `grade_market_line` semantics for the same projection/line.

- [ ] **Step 6: Commit**

Commit: `feat: add CFB player props Page 3 line lab`

---

### Task 3: Recent production, hit-rate windows, opportunity, and prior-opponent evidence

**Files:**
- Create: `cfb_player_props_page3_history_v1.py`
- Test: `tests/test_cfb_player_props_page3_history_v1.py`

**Interfaces:**
- Consumes: verified rows from `cfb_player_props_history_v1.load_verified_player_history` plus explicitly available gamelog/event metadata.
- Produces:
  - `build_history_windows(history: Sequence[Mapping[str, Any]], selected_line: float) -> dict[str, Any]`
  - `build_opportunity_evidence(history: Sequence[Mapping[str, Any]], market_key: str) -> dict[str, Any]`
  - `build_prior_opponent_sample(history: Sequence[Mapping[str, Any]], opponent_team_id: str) -> dict[str, Any]`

- [ ] **Step 1: Write RED history-window tests**

Assert L5/L8 values preserve verified order, averages use only finite verified values, hit rates compare against the current selected line, each hit rate includes `hits`, `sample_count`, `rate`, and no empty sample becomes 0%.

- [ ] **Step 2: Write RED opportunity/prior-opponent tests**

Only explicitly present attempts/completions/carries/receptions or other verified fields may render. Missing fields remain unavailable. Prior-opponent section requires exact opponent metadata; otherwise state is `unavailable` with `No verified prior matchup sample.`

- [ ] **Step 3: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_history_v1.py`

- [ ] **Step 4: Implement descriptive-only history helpers**

Do not alter or extend frozen model inputs; these outputs are presentation evidence only.

- [ ] **Step 5: Run GREEN and commit**

Commit: `feat: add CFB Page 3 production evidence`

---

### Task 4: Page-3 analysis composition, market board, matchup, movement, and reasoning

**Files:**
- Create: `cfb_player_props_page3_analysis_v1.py`
- Test: `tests/test_cfb_player_props_page3_analysis_v1.py`

**Interfaces:**
- Consumes: Page-3 context, current `cfb_player_props_page2_market_v1` market views/observations, frozen history/model, Page-2 matchup owner, Page-3 Line Lab/history helpers, explicit availability/environment evidence.
- Produces:
  - `build_page3_analysis(context: Mapping[str, Any], *, selected_line: float | None = None) -> dict[str, Any]`
  - `build_reasoning_panel(analysis: Mapping[str, Any]) -> dict[str, Any]`
  - `build_evidence_quality(analysis: Mapping[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write RED current-market tests**

Assert book-specific rows remain separate, consensus/best lines reuse Page-2 market semantics, one provider failure cannot erase other verified rows, newest valid quote wins within existing freshness rules, and missing/null never becomes 0.

- [ ] **Step 2: Write RED projection-independence tests**

`build_page3_analysis` must produce the same frozen projection mean/uncertainty regardless of sportsbook line changes, opponent grade changes, availability labels, or selected Line Lab line. Assert `sportsbook_projection_influence == 0.0`.

- [ ] **Step 3: Write RED movement/matchup/reasoning tests**

Movement without trusted opening evidence is unavailable. Opponent context is presentation-only. Reasoning/Bull/Bear statements are deterministic from verified facts and omit unsupported claims. Evidence quality exposes components rather than a synthetic HIGH/MEDIUM/LOW score.

- [ ] **Step 4: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_analysis_v1.py`

- [ ] **Step 5: Implement one orchestration read per owner**

Load exact current market/history/matchup/availability evidence once per render/cache cycle, then compose locally. Reuse Page-2 market and matchup logic instead of duplicating formulas.

- [ ] **Step 6: Run GREEN and commit**

Commit: `feat: compose CFB Page 3 player prop analysis`

---

### Task 5: Professional Page-3 Streamlit UI, slider, charts, Back, TOP, and market switch

**Files:**
- Create: `cfb_player_props_page3_v1.py`
- Test: `tests/test_cfb_player_props_page3_v1.py`

**Interfaces:**
- Consumes: `resolve_page3_context`, `clear_page3_selection`, `switch_page3_market`, `build_page3_analysis`, Line Lab outputs.
- Produces: `render_cfb_player_props_page3() -> None`.

- [ ] **Step 1: Write RED shell/navigation tests**

Pin visible `← Back to Game Props`, fixed `↑ TOP`, player/team/prop hero, no keyboard text/number inputs, and Back calling only the Page-3 clear helper before rerun.

- [ ] **Step 2: Write RED Line Lab/market-switch tests**

Slider uses the Task-2 market bounds/0.5 step; default line order is current consensus -> Page-2 handoff line -> clearly labeled UI-only midpoint. Same-player market switch preserves game/player and resets only market-specific line state.

- [ ] **Step 3: Write RED section/copy tests**

Pin sections: Kyre Projection vs Market; Over/Under probability; probability curve; Sportsbook Board; movement or `Verified opening movement unavailable.`; L5/L8/season production; opportunity; opponent defense; prior matchup or exact unavailable copy; game environment; Why/Bull/Bear; evidence quality.

- [ ] **Step 4: Run RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_v1.py`

- [ ] **Step 5: Implement mobile-first UI**

Use touch-friendly slider/select controls, compact sportsbook cards on narrow screens, responsive charts without horizontal overflow, and a TOP control positioned so it does not obscure slider or Streamlit management controls.

- [ ] **Step 6: Preserve live refresh state**

Use the current Page-2 refresh pattern, but key slider state by exact `(game_id, player_id, prop)` identity so same-identity refresh preserves the chosen line and any identity change resets it.

- [ ] **Step 7: Run GREEN and commit**

Commit: `feat: add CFB player props Page 3 intelligence lab`

---

### Task 6: Full integration/regression, Runless proof plan, merge, and GREEN + FROZEN closeout

**Files:**
- Create: `tests/test_cfb_player_props_page3_integration_v1.py`
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page3-v1.json`
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page3-v1.json`
- Modify only if required by exact route contract: current CFB Player Props destination overlay test pins.

**Interfaces:**
- Consumes: all Page-3 modules plus frozen Page 1/Page 2/runtime/model/navigation contracts.
- Produces: exact candidate SHA, authoritative Runless receipt, merged-main SHA, immutable finalization-ledger record/manifest, released lease, terminal `GREEN_FROZEN`.

- [ ] **Step 1: Write RED integration tests**

Pin exclusive Page1/Page2/Page3 routing; no Page-2 mutation unless explicitly justified; Page-3 Back returns to Page 2 same game; TOP present; frozen model constants unchanged; provider IDs remain provenance; app.py untouched; Page-1/Page-2 tests remain valid.

- [ ] **Step 2: Run full CFB Player Props regression**

Run all `tests/test_cfb_player_props_*.py` with `--noconftest`, plus current Universal Atomic Navigation and current terminal-inheritance regression. Expected PASS after Task 1–5 are complete.

- [ ] **Step 3: Run compile + runtime certificate**

Compile all new/modified Page-3/runtime modules and run `python -m devsystem.api2_universal_runtime_v5_cert`. Expected GREEN.

- [ ] **Step 4: Seal proof plan + ledger**

Proof commands must use Runless-supported grammar only; no `pip install` command in the proof plan. Record broader local regression evidence separately if managed Runless bootstrap excludes a UI-only dependency.

- [ ] **Step 5: Exact-head authority read**

Verify current main, lease, PR uniqueness, and exact branch head before proof. If main drifted, classify/rebase/reconcile before proof; never certify stale head.

- [ ] **Step 6: Submit one authoritative Runless proof**

On failure, classify first and patch the root cause on the same lane; never retry the same failed SHA blindly. On PASS require `MERGE_AUTHORIZED` bound to the exact candidate.

- [ ] **Step 7: Merge exact head and verify main**

Merge the single authoritative PR with expected-head protection, then verify merged main contains the exact candidate and expected Page-3 blobs.

- [ ] **Step 8: Publish immutable finalization-ledger freeze record**

Use freeze token `MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN`, exact candidate, merged-main SHA, proof digest, and merged-main artifact blob IDs. Advance manifest with CAS and independently read back record + manifest.

- [ ] **Step 9: Transition Runless to GREEN_FROZEN**

Bind exact candidate, merged main, freeze token, proof digest, and manifest state hash through the existing closeout state machine. Read back terminal state and require failure class `NONE`.

- [ ] **Step 10: Release/read back the Page-3 scope lease**

Remove only the Page-3 holder; leave unrelated parallel lanes untouched. Require lease absence before completion claim.

- [ ] **Step 11: Fresh final verification**

Run a final merged-main route/context/Line-Lab smoke verification after closeout. Only then report **100% GREEN + FROZEN**.
