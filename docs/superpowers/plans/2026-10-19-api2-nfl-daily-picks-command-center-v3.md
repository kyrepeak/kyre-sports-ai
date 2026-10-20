# NFL Daily Picks Command Center V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an isolated S-tier NFL Daily Picks command center for Moneyline, Spread, Game Total and correlation-safe parlays without mutating frozen NFL model truth.

**Architecture:** Add pure V3 market/parlay/board modules and bind them through a workstream-unique Runtime V5 overlay that delegates every unrelated route to the currently frozen upstream runtime. Reuse existing certified source candidates and verified sportsbook transports; fail closed when a source-owned probability or verified current book is unavailable.

**Tech Stack:** Python, Streamlit, Universal Runtime V5, pytest, Runless V2, Vercel Sandbox preflight.

**Spec:** `docs/superpowers/specs/2026-10-19-api2-nfl-daily-picks-command-center-v3-design.md`

## Global Constraints

- Authoritative branch: `api2-nfl-daily-picks-command-center-v3`.
- Source main SHA: `575a83867da2c7bb9817a0cd9082b98270905da3`.
- Markets in V3: Moneyline, Spread, Game Total only. No player props.
- Existing NFL source-model files remain read-only.
- Sportsbook projection influence stays exactly 0.0%.
- Balanced is the default risk mode.
- No synthetic source probability: Game Total cannot enter probability-based ranking/parlays unless a certified source-owned probability contract exists.
- One branch, one PR, one Vercel preflight sandbox, one Runless proof path, exact-head proof before merge.
- Workstream-unique loader/router paths only; do not claim a shared numbered runtime-loader path.

## Review Focus

- A stale or unverified sportsbook quote must never become `best_book`.
- A pregame-only model candidate must never silently become a live recommendation.
- Same-game contradictory legs must be blocked rather than merely penalized.
- A Game Total without source-owned probability must remain visible but non-parlay-eligible.
- The runtime overlay must alter only NFL Daily Picks and preserve current NBA Spread and every unrelated route.

---

### Task 1: Lock the V3 contract with RED tests

**Files:**
- Create: `tests/test_api2_nfl_daily_picks_command_center_v3.py`

**Interfaces:**
- Consumes: frozen `DailyPickCandidate`, existing Runtime V5 route contract.
- Produces: executable contract for all V3 modules and terminal handoff.

- [ ] **Step 1:** Add tests for the three-market scope, Balanced default, parlay conflict rules, LOW/MEDIUM/HIGH penalties, Game Total probability fail-closed behavior, verified-best-book selection, game-state buckets, and isolated route binding.
- [ ] **Step 2:** Run the focused test in the single named Vercel preflight sandbox and record RED caused only by missing V3 modules.
- [ ] **Step 3:** Commit the RED contract and record the evidence in the task ledger.

### Task 2: Implement pure parlay intelligence

**Files:**
- Create: `nfl_daily_picks_parlay_v3.py`
- Test: `tests/test_api2_nfl_daily_picks_command_center_v3.py`

**Interfaces:**
- Consumes: `DailyPickCandidate` leg records with source-owned probabilities.
- Produces: `validate_parlay_legs(legs)`, `estimate_parlay_probability(legs)`, `build_parlay(candidates, risk_mode)`.

- [ ] **Step 1:** Make the contract's parlay tests fail for missing implementation.
- [ ] **Step 2:** Implement hard conflicts, correlation grade, conservative probability penalties, deterministic risk-mode leg bounds, and the explicit `estimated parlay probability` label.
- [ ] **Step 3:** Run focused tests GREEN; no stale/unqualified/no-probability leg may enter a generated parlay.

### Task 3: Implement verified multi-book market aggregation

**Files:**
- Create: `nfl_daily_picks_market_v3.py`
- Test: `tests/test_api2_nfl_daily_picks_command_center_v3.py`

**Interfaces:**
- Consumes: normalized observations from existing NFL sportsbook transports and candidate metadata.
- Produces: `normalize_market_observations(...)`, `best_verified_book(...)`, `line_movement(...)`.

- [ ] **Step 1:** Verify RED for best-book/freshness behavior.
- [ ] **Step 2:** Implement deterministic verified/fresh filtering, best-price selection by market/side, opening-to-current movement only with timestamped evidence, and `No verified current book` fail-closed state.
- [ ] **Step 3:** Run focused tests GREEN and confirm market data never mutates model probability/projection.

### Task 4: Build Command Center board and S-tier presentation

**Files:**
- Create: `nfl_daily_picks_command_center_v3.py`
- Test: `tests/test_api2_nfl_daily_picks_command_center_v3.py`

**Interfaces:**
- Consumes: frozen Daily Picks loaders/candidates, V3 market aggregation, V3 parlay intelligence.
- Produces: `build_command_center_board(...)` and `render_nfl_daily_picks_command_center()`.

- [ ] **Step 1:** Verify RED for scope, game-state buckets, default mode and Game Total fail-closed state.
- [ ] **Step 2:** Implement three-market board, LIVE NOW / NEXT GAMES / ALL NFL payloads, featured picks, best-book/movement context, source freshness, why/risk text, and parlay-slip payload.
- [ ] **Step 3:** Render the professional Command Center hierarchy with responsive mobile cards and sticky parlay panel.
- [ ] **Step 4:** Run focused contract GREEN.

### Task 5: Bind isolated Runtime V5 route

**Files:**
- Create: `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py`
- Modify: `app.py`
- Test: `tests/test_api2_nfl_daily_picks_command_center_v3.py`

**Interfaces:**
- Consumes: current frozen NBA Spread terminal/runtime overlay.
- Produces: current production route where only `nfl/daily-picks` resolves to V3.

- [ ] **Step 1:** Verify RED for V3 route ownership and app terminal handoff.
- [ ] **Step 2:** Implement a unique loader delegating non-Daily-Picks routes to `universal_runtime_v5_loader_nba_spread_stier_v2` and override only NFL Daily Picks.
- [ ] **Step 3:** Implement a terminal router wrapping the current NBA Spread terminal and inject the V3 loader functions.
- [ ] **Step 4:** Change only the `app.py` terminal import to the V3 terminal.
- [ ] **Step 5:** Run focused route and universal-navigation tests GREEN.

### Task 6: Durable control plane, preflight and exact-head proof

**Files:**
- Create: `devsystem/task_ledgers/api2-nfl-daily-picks-command-center-v3.json`
- Create: `devsystem/runless_proof_plans/api2-nfl-daily-picks-command-center-v3.json`

**Interfaces:**
- Consumes: final candidate head and all V3/frozen regression tests.
- Produces: one auditable Runless proof path and freeze token `API2_NFL_DAILY_PICKS_COMMAND_CENTER_V3_FROZEN`.

- [ ] **Step 1:** Run py_compile + focused V3 contract in the same named Vercel sandbox.
- [ ] **Step 2:** Run existing NFL Daily Picks V1/V2 tests, universal navigation tests and Universal Runtime V5 certification in that same sandbox.
- [ ] **Step 3:** Re-read protected main. If main moved, reconcile once before candidate lock; do not prove stale head.
- [ ] **Step 4:** Record exact final candidate SHA, preflight outputs, Step 2A state and proof plan in the ledger.
- [ ] **Step 5:** Create/reuse exactly one PR and submit exactly one authoritative Runless proof request for the exact candidate head.
- [ ] **Step 6:** Merge only after `runless-final-gate` from GitHub App 5204253 is successful for exact head.
- [ ] **Step 7:** Read back merged main, production route, frozen registry/receipt and freeze token before declaring 100% GREEN + FROZEN.

## Failure policy

Classify an authoritative failure once, repair the root cause on this same branch/PR, invalidate stale candidate identity after any mutation, rerun only the necessary preflight proof, and continue the same authority chain. No duplicate branch, PR, sandbox, Runless request, deployment, lease or polling loop.