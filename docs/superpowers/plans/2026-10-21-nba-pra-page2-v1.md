# NBA PRA Page 2 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first NBA PRA Player Intelligence Deep Dive that opens from the exact Page-1 player/quote selection, explains the current PRA decision with verified evidence, and preserves the frozen Page-1 model and source contract.

**Architecture:** Add an isolated NBA PRA runtime selector that renders frozen Page 1 when no valid player selection exists and Page 2 when a verified selection exists. Page 2 gets selected-player context through Kyre Sports API owners, keeps sportsbook quotes separate, evaluates custom Line Lab thresholds without altering projection math, and presents opponent ranking/matchup grade as contextual evidence only.

**Tech Stack:** Python, Streamlit, existing Kyre Sports API client/Runless V2 modules, existing NBA PRA model/UI helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-nba-pra-page2-v1-design.md`

## Global Constraints

- Kyre Sports API is the only application-facing API/data gateway.
- Never use SGO / SportsGameOdds.
- Never use ESPN or ESPN BET in request, fallback, enrichment, verification, or production paths.
- Preserve sportsbook, line, over price, under price, and timestamp separately; never average conflicting sportsbook lines.
- Sportsbook projection influence remains exactly `0.0`.
- Frozen Page-1 projection math must not change.
- Missing or unverified source values remain unavailable; never fabricate or coerce them to `0`.
- Opponent ranking semantics: rank `1` means toughest/stingiest; `1–10 = TOUGH`, `11–21 = MEDIUM`, `22–30 = FAVORABLE`; no verified rank means matchup grade unavailable.
- A moved live quote must be labeled `LINE MOVED SINCE SELECTION`; never silently replace the tapped quote identity.
- One authoritative branch, one PR, one Runless proof path, one merge/freeze chain.

## Review Focus

1. **Stale selected player/quote:** Page 2 must fail closed or explicitly report line movement; it must never silently resolve another player or quote.
2. **Missing matchup data:** Page 2 must still render player/history/market evidence while showing matchup grade unavailable.
3. **Mobile navigation state:** Back must return to NBA PRA Page 1 only; TOP must scroll without changing route/session state or opening the keyboard.
4. **Partial provider degradation:** one source failure must not erase verified quotes/history from other approved sources or trigger shotgun provider fanout.
5. **No-variance players:** Line Lab may show projection-minus-line edge, but model probability/score must remain unavailable when sigma is unavailable.

---

### Task 1: Canonical Page-2 Selection + Runtime Routing

**Files:**
- Create: `nba_pra_runtime_v2.py`
- Create: `tests/test_api2_nba_pra_page2_runtime_v1.py`
- Modify only if required by the failing integration test: `streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py`

**Interfaces:**
- Consumes: `nba_pra_page1_ui_v2.SESSION_PLAYER == "ks_nba_pra_selected_player"` and existing NBA PRA Page-1 snapshot loader.
- Produces: `render_nba_pra_runtime_v2() -> None`, `selected_player_key(session_state: Mapping[str, Any]) -> str | None`, and exact Page-1/Page-2 exclusive routing.

- [ ] **Step 1: Write failing runtime tests** asserting no selection renders Page 1 only, a valid selected key routes Page 2 only, invalid selection fails closed, Back clears only Page-2 selection state, and Page 1 never background-renders while Page 2 is active.
- [ ] **Step 2: Run** `pytest tests/test_api2_nba_pra_page2_runtime_v1.py -q` and verify the new tests fail for missing Page-2 runtime behavior.
- [ ] **Step 3: Implement** `nba_pra_runtime_v2.py` with exact exclusive routing around the existing `SESSION_PLAYER`; do not duplicate Page-1 analytics.
- [ ] **Step 4: If the Universal Runtime destination cannot call the selector without a compatibility change, make the smallest overlay-only modification** to `streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py`; otherwise leave it untouched.
- [ ] **Step 5: Run** the runtime test plus existing `tests/test_api2_nba_pra_page1_v2_ui_contract.py`; both must pass.
- [ ] **Step 6: Commit** runtime routing and tests.

### Task 2: Selected Player Context + Exact Quote Identity

**Files:**
- Create: `nba_pra_page2_context_v1.py`
- Create: `tests/test_api2_nba_pra_page2_context_v1.py`

**Interfaces:**
- Consumes: `load_page1_snapshot_v2(now=...)`, canonical selected player key, current Page-1 market/profile/game owners.
- Produces: `build_page2_context(snapshot: Mapping[str, Any], selected_player_key: str, *, selected_quote: Mapping[str, Any] | None = None) -> dict[str, Any]` with states `ready`, `line_moved`, `player_unavailable`, `market_unavailable`, `invalid`.

- [ ] **Step 1: Write failing context tests** for canonical player resolution, headshot/team logo identity, opponent/game identity, exact tapped quote preservation, `LINE MOVED SINCE SELECTION`, stale/wrong player rejection, and null values staying null.
- [ ] **Step 2: Run** `pytest tests/test_api2_nba_pra_page2_context_v1.py -q`; verify failures are only missing context behavior.
- [ ] **Step 3: Implement** `build_page2_context(...)` by filtering the current Kyre Sports API snapshot to the selected player; do not add new direct app-facing providers.
- [ ] **Step 4: Run** context tests and the Page-1 history-coverage regression `tests/test_api2_nba_pra_history_coverage_v1.py`.
- [ ] **Step 5: Commit** context owner and tests.

### Task 3: Line Lab + Decision Math

**Files:**
- Create: `nba_pra_page2_line_lab_v1.py`
- Create: `tests/test_api2_nba_pra_page2_line_lab_v1.py`

**Interfaces:**
- Consumes: frozen `projection: float | None`, `sigma: float | None`, selected/test PRA line.
- Produces: `evaluate_line(projection: float | None, sigma: float | None, line: float | None) -> dict[str, Any]` and `line_steps(center: float, *, width: float = 10.0) -> tuple[float, ...]` in 0.5 increments.

- [ ] **Step 1: Write failing tests** for 0.5-step slider lines, probability monotonicity, over/under probability complement, edge/lean changes when line moves, no probability when sigma is missing, and `SPORTSBOOK_PROJECTION_INFLUENCE == 0.0`.
- [ ] **Step 2: Run** `pytest tests/test_api2_nba_pra_page2_line_lab_v1.py -q`; verify RED.
- [ ] **Step 3: Implement** Line Lab using the same Normal-distribution semantics as the frozen Page-1 model; only the threshold changes.
- [ ] **Step 4: Run** Line Lab tests plus Page-1 model regression tests.
- [ ] **Step 5: Commit** Line Lab and tests.

### Task 4: Opponent Ranking + Matchup Grade

**Files:**
- Create: `nba_pra_page2_matchup_v1.py`
- Create: `tests/test_api2_nba_pra_page2_matchup_v1.py`

**Interfaces:**
- Consumes: verified opponent/team stat rows delivered through Kyre Sports API for points, rebounds, assists and PRA/positional allowance where legitimately available.
- Produces: `grade_rank(rank: int | None) -> str`, `build_matchup_summary(rows: Mapping[str, Any]) -> dict[str, Any]` with explicit rank semantics and `TOUGH | MEDIUM | FAVORABLE | UNAVAILABLE`.

- [ ] **Step 1: Write failing tests** pinning ranks `1, 10 -> TOUGH`, `11, 21 -> MEDIUM`, `22, 30 -> FAVORABLE`, missing/out-of-range -> `UNAVAILABLE`, and explicit `1 = toughest` wording.
- [ ] **Step 2: Add failing tests** proving points/rebounds/assists/PRA ranks remain separate, missing one component does not fabricate it, and matchup context never changes the frozen projection value.
- [ ] **Step 3: Run** `pytest tests/test_api2_nba_pra_page2_matchup_v1.py -q`; verify RED.
- [ ] **Step 4: Implement** deterministic rank normalization/grade mapping and approved-source context handling only; do not add model adjustments.
- [ ] **Step 5: Run** matchup tests and existing Page-1 model/history tests.
- [ ] **Step 6: Commit** matchup owner and tests.

### Task 5: Page-2 Hybrid S-Tier UI

**Files:**
- Create: `nba_pra_page2_v1.py`
- Create: `tests/test_api2_nba_pra_page2_ui_v1.py`

**Interfaces:**
- Consumes: Task-2 context, Task-3 Line Lab, Task-4 matchup summary, existing Page-1 identity/team-logo/model helpers.
- Produces: `render_nba_pra_page2_v1(context: Mapping[str, Any] | None = None) -> None` and the complete mobile-first Page-2 experience.

- [ ] **Step 1: Write failing UI contract tests** for visible Back, fixed TOP, player headshot/team logo/opponent logo, current quote + moved-line warning, Kyre Verdict, Line Lab, sportsbook quote rows, L5/L10/MIN, opponent rank cards, matchup badge, prior-matchup fail-closed copy, risk panel, and expandable full game log.
- [ ] **Step 2: Add navigation tests** proving Back preserves `sport=nba`, `market=pra` while clearing Page-2-local state, and TOP does not mutate route/session identity or create a text input.
- [ ] **Step 3: Run** `pytest tests/test_api2_nba_pra_page2_ui_v1.py -q`; verify RED.
- [ ] **Step 4: Implement** the Page-2 layout in this order: Back/hero → Verdict → Line Lab → books/movement → Recent Form → opponent rank + grade → matchup intelligence → prior meetings → role/minutes → injury/lineup → projection evidence → risk factors → full game log; use progressive disclosure for deep sections.
- [ ] **Step 5: Verify** book rows remain separate, missing evidence says unavailable, no synthetic opening line appears, and player/team picture IDs use verified current identity.
- [ ] **Step 6: Run** UI tests plus Page-1 UI/history regression tests.
- [ ] **Step 7: Commit** Page-2 UI and tests.

### Task 6: Full Integration, Source Guards, Performance, and Runtime Isolation

**Files:**
- Create: `tests/test_api2_nba_pra_page2_integration_v1.py`
- Modify only if proven necessary: NBA PRA terminal runtime overlay from Task 1.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: one integrated Page-1 → Page-2 → Back flow and exact-source-policy regression evidence.

- [ ] **Step 1: Write integration tests** covering Page-1 selected player handoff, Page-2 exact identity, Back return, no background Page-1 render, partial provider degradation, no-variance player behavior, and opponent-ranking unavailability.
- [ ] **Step 2: Add forbidden-provider scan test** asserting active NBA PRA Page-2/runtime/context/matchup files contain no SGO/SportsGameOdds/ESPN/ESPN BET integration and no direct application-facing provider client outside Kyre Sports API owners.
- [ ] **Step 3: Add performance contract tests** that Page 2 loads/filter deep-dive data for the selected player/game rather than iterating deep provider enrichment for all 110 players.
- [ ] **Step 4: Run focused Page-2 suite**: `pytest tests/test_api2_nba_pra_page2_* -q`.
- [ ] **Step 5: Run NBA PRA regression suite**, including Page-1 model/UI/history/API-only tests and Universal Runtime V5 navigation/isolation tests.
- [ ] **Step 6: Run `python -m py_compile`** on all new/modified Page-2/runtime modules.
- [ ] **Step 7: Commit** integration and guard tests.

### Task 7: Authority Binding, Exact-Head Proof, Merge, Production, Freeze

**Files:**
- Create: `devsystem/execution_plans/api2-nba-pra-page2-v1.json`
- Create: `devsystem/runless_proof_plans/api2-nba-pra-page2-v1.json`
- Create: `devsystem/task_ledgers/api2-nba-pra-page2-v1.json`
- Finalization ledger sidecar record/bridge/manifest update after merge.

**Interfaces:**
- Consumes: exact tested branch head from Tasks 1–6 and the existing Runless V2/finalization infrastructure.
- Produces: `API2_NBA_PRA_PAGE2_V1_FROZEN` and durable `GREEN_FROZEN` state.

- [ ] **Step 1: Bind** one scope lease, one branch, one PR, one Runless proof plan, expected protected-main SHA, write paths, regression commands, and forbidden-provider checks.
- [ ] **Step 2: Verify exact candidate head** with the complete focused + regression + compile + provider-ban gate; zero failures required.
- [ ] **Step 3: Open/use one authoritative PR** and submit exactly one Runless proof request for the exact candidate.
- [ ] **Step 4: Read back** `runless-final-gate` success on the same exact SHA and receipt digest.
- [ ] **Step 5: Merge** with expected-head lock; verify protected main contains the exact candidate as merged parent.
- [ ] **Step 6: Verify production** deployment/read-back on the exact merge SHA; do not create a duplicate deployment if Git integration already produced READY.
- [ ] **Step 7: Finalize** one ledger CAS write with freeze token `API2_NBA_PRA_PAGE2_V1_FROZEN`, preserve legacy registry read-only state, then read back record/bridge/manifest.
- [ ] **Step 8: Close out** Runless once, verify durable `GREEN_FROZEN`, `failure_class = NONE`, release/read back the scope lease, and only then report 100% GREEN + FROZEN.
