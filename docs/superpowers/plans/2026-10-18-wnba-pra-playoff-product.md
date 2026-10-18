# WNBA PRA Playoff Product V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current developer-facing WNBA PRA page with a playoff-aware, PRA-first customer product while preserving the existing validated projection, qualification, Monte Carlo, ranking, and final-selection behavior.

**Architecture:** Keep Universal Runtime V5 and the existing WNBA PRA engine intact. Add read-only successor modules that resolve playoff slate context, normalize multi-source evidence, summarize multi-book PRA markets, compose player decision view-models, and render a clean product surface; activate them by advancing the existing `wnba_pra_hub_v3612` compatibility boundary to a new successor wrapper. The product layer reads preserved engine outputs through existing entrypoints and delegates Final Card selection to `wnba_pra_final_v32.select_master_card()` instead of re-implementing selection math.

**Tech Stack:** Python 3, Streamlit, pandas, pytest, existing WNBA PRA engine modules, Universal Runtime V5, Runless proof plane.

**Spec:** `docs/superpowers/specs/2026-10-18-wnba-pra-playoff-product-design.md`

## Global Constraints

- Preserve existing validated PRA projection, qualification, no-vig, Monte Carlo, ranking, and selection math.
- Sportsbook prices remain read-only grading/context and never move the model projection.
- Multi-source is mandatory for slate, availability, statistics, and market context whenever additional independent sources are available.
- Never fabricate a line, starter, injury status, player identity, schedule event, statistic, or market quote.
- Source conflicts must remain visible internally and must lower confidence or block finalization when material.
- PRA is the top-level product; Points/Rebounds/Assists are detail components, not equal top-level tabs on this page.
- Internal Step 6/7/8/9 language, raw Monte Carlo controls, and provider-health machinery stay out of the normal customer flow.
- Advanced Diagnostics remains available, collapsed by default.
- Mobile-first layout; no horizontal overflow at narrow widths.
- Universal Runtime V5 is not rewritten.
- Existing one-authoritative-lane, proof-before-merge, exact-head verification, freeze, and lease-release controls remain mandatory.

## Review Focus

1. **Verified off-day with a future playoff game:** the page must surface the next verified game without pretending today has a game. Covered in Task 3.
2. **Official schedule conflicts with corroborating schedule:** official WNBA identity wins, but the conflict remains recorded and visible in diagnostics. Covered in Tasks 2-3.
3. **Only one current sportsbook quote exists:** show the quote as `SINGLE_SOURCE`; never label it consensus. Covered in Task 4.
4. **Availability is unresolved while projections exist:** preliminary player research stays visible, but Final Card eligibility is blocked/marked unresolved using preserved integrity state. Covered in Tasks 5-6.
5. **No PRA market exists but a valid model projection exists:** keep the projection/player board visible and omit market-based final action instead of fabricating a line. Covered in Tasks 1, 5, and 6.

---

### Task 1: Freeze a read-only product snapshot boundary over the existing PRA engine

**Files:**
- Create: `wnba_pra_product_snapshot_v1.py`
- Create: `tests/test_wnba_pra_product_snapshot_v1.py`

**Interfaces:**
- Consumes:
  - `wnba_pra_market_v29._projection_frame(day)`
  - `wnba_pra_market_v29.grade_pra_markets(day)`
  - `wnba_pra_matchup_v30.grade_matchup_pra(day)`
  - `wnba_pra_final_v32._stored_rows(day)`
  - `wnba_pra_final_v32.select_master_card(rows, limit=wnba_pra_final_v32.MAX_CARD)`
  - `wnba_schedule_v25.schedule_diagnostics(day)`
  - `wnba_pra_hub_v27.availability.availability_diagnostics(day)`
  - `wnba_role_v28.role_diagnostics(day)`
- Produces:
  - `PRAProductSnapshot` dataclass with fields:
    - `day: str`
    - `schedule: pd.DataFrame`
    - `schedule_diag: Mapping[str, Any]`
    - `projections: pd.DataFrame`
    - `market_rows: pd.DataFrame`
    - `market_meta: Mapping[str, Any]`
    - `matchup_rows: pd.DataFrame`
    - `matchup_meta: Mapping[str, Any]`
    - `stored_mc_rows: pd.DataFrame`
    - `stored_mc_meta: Mapping[str, Any]`
    - `final_card: pd.DataFrame`
    - `availability_diag: Mapping[str, Any]`
    - `role_diag: Mapping[str, Any]`
  - `build_product_snapshot(day: str) -> PRAProductSnapshot`

- [ ] **Step 1: Write failing snapshot characterization tests**

Cover that `build_product_snapshot()` delegates to the exact preserved engine functions above, copies their returned frames/mappings without mutating them, and obtains Final Card rows only from `select_master_card()`.

- [ ] **Step 2: Run the snapshot tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_snapshot_v1.py`
Expected: FAIL because `wnba_pra_product_snapshot_v1` does not exist.

- [ ] **Step 3: Implement `PRAProductSnapshot` and `build_product_snapshot(day: str)`**

Do not calculate new projections, edges, qualifications, probabilities, ranks, or Final Card selections. Normalize only empty/None return values into empty DataFrames or empty mappings so the view layer can fail closed.

- [ ] **Step 4: Run the snapshot tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_snapshot_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_product_snapshot_v1.py tests/test_wnba_pra_product_snapshot_v1.py
git commit -m "feat: add read-only WNBA PRA product snapshot"
```

---

### Task 2: Add reusable multi-source evidence fusion

**Files:**
- Create: `wnba_pra_source_fusion_v1.py`
- Create: `tests/test_wnba_pra_source_fusion_v1.py`

**Interfaces:**
- Produces:
  - `SourceObservation` dataclass:
    - `source: str`
    - `category: str`
    - `identity: str`
    - `value: Any`
    - `observed_at: str | None`
    - `freshness: str`
    - `priority: int`
    - `authoritative: bool`
  - `EvidenceSummary` dataclass:
    - `state: str`
    - `value: Any`
    - `sources: tuple[str, ...]`
    - `conflicts: tuple[str, ...]`
    - `freshness: str`
  - `fuse_observations(observations: Sequence[SourceObservation]) -> EvidenceSummary`
- Evidence states are exactly:
  - `VERIFIED_MULTI_SOURCE`
  - `VERIFIED_PRIMARY`
  - `SINGLE_SOURCE`
  - `CONFLICT`
  - `STALE`
  - `UNAVAILABLE`

- [ ] **Step 1: Write failing fusion tests**

Test: two agreeing independent sources -> `VERIFIED_MULTI_SOURCE`; one authoritative source -> `VERIFIED_PRIMARY`; one non-authoritative source -> `SINGLE_SOURCE`; conflicting observations -> `CONFLICT` while retaining the authoritative value when one exists; all stale -> `STALE`; empty input -> `UNAVAILABLE`.

- [ ] **Step 2: Run the fusion tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_source_fusion_v1.py`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the dataclasses and `fuse_observations()`**

Use identity equality plus value equality for agreement. Never synthesize a third value to resolve a conflict.

- [ ] **Step 4: Run the fusion tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_source_fusion_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_source_fusion_v1.py tests/test_wnba_pra_source_fusion_v1.py
git commit -m "feat: add WNBA PRA multi-source evidence fusion"
```

---

### Task 3: Resolve playoff/off-day context and the next verified game

**Files:**
- Create: `wnba_pra_playoff_context_v1.py`
- Create: `tests/test_wnba_pra_playoff_context_v1.py`

**Interfaces:**
- Consumes:
  - primary official schedule/competition payload from `wnba_api_client_v1.KyreWNBAAPIClient.games_for_date(day, SUPPORTED_SEASON)`
  - corroborating schedule from the original multi-source `wnba_schedule_v25` transport; when the API bridge has patched V2.5, use `_kyre_step7f_original_schedule_for_date` / `_kyre_step7f_original_schedule_diagnostics` if present, otherwise use `schedule_for_date` / `schedule_diagnostics`
  - Task 2 `SourceObservation` / `fuse_observations`
- Produces:
  - `PlayoffContext` dataclass:
    - `selected_date: str`
    - `effective_date: str`
    - `today_has_game: bool`
    - `games: pd.DataFrame`
    - `next_game: Mapping[str, Any] | None`
    - `competition_label: str`
    - `series_label: str`
    - `evidence_state: str`
    - `sources: tuple[str, ...]`
    - `off_day_message: str`
  - `resolve_playoff_context(selected_date: str, *, api_client: KyreWNBAAPIClient | None = None, lookahead_days: int = 14) -> PlayoffContext`

- [ ] **Step 1: Write failing context tests**

Required cases:
- selected date has a verified game -> `effective_date == selected_date`
- selected date is verified empty and next verified game is within 14 days -> `effective_date` advances and `today_has_game is False`
- no verified future game -> remain on selected date with honest empty state
- official API and WNBA/ESPN consensus agree -> multi-source verified state
- official API conflicts with corroborating matchup -> official game identity is retained but evidence is `CONFLICT`
- competition label uses verified `competition.game_label` / `competition.game_sub_label` data when present and never hard-codes `Finals`

- [ ] **Step 2: Run the context tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_playoff_context_v1.py`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement `resolve_playoff_context()`**

Look ahead one calendar day at a time, maximum 14 days. Stop at the first verified future slate with at least one WNBA game. Keep the user's selected date separately from the effective research date so the UI can say “No game today” and still prepare the next game.

- [ ] **Step 4: Run the context tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_playoff_context_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_playoff_context_v1.py tests/test_wnba_pra_playoff_context_v1.py
git commit -m "feat: add WNBA playoff slate resolver"
```

---

### Task 4: Build multi-book PRA market consensus without changing model truth

**Files:**
- Create: `wnba_pra_market_consensus_v1.py`
- Create: `tests/test_wnba_pra_market_consensus_v1.py`

**Interfaces:**
- Consumes: Task 1 `snapshot.market_rows`; expected existing columns include player identity, sportsbook/book, line, over price, freshness, projection, model probability, no-vig probability, and edge when available.
- Produces:
  - `build_market_consensus(graded: pd.DataFrame) -> pd.DataFrame`
  - one row per player identity with canonical columns:
    - `player_key`
    - `player`
    - `book_count`
    - `books`
    - `consensus_line`
    - `min_line`
    - `max_line`
    - `best_over_odds`
    - `evidence_state`
    - `current_quote_count`
- This module is presentation-only and must never write back into the projection/market/final-selection engine.

- [ ] **Step 1: Write failing consensus tests**

Cases: three current books agreeing; books with different lines; one current book -> `SINGLE_SOURCE`; stale quotes excluded from current consensus but countable in diagnostics; no rows -> empty output.

- [ ] **Step 2: Run the consensus tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_market_consensus_v1.py`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement `build_market_consensus()`**

Use the median of current independent book lines as `consensus_line`; preserve line range and source names. Never use consensus to alter `projection`, `model_over`, `edge`, qualification, or the Final Card.

- [ ] **Step 4: Run the consensus tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_market_consensus_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_market_consensus_v1.py tests/test_wnba_pra_market_consensus_v1.py
git commit -m "feat: add WNBA PRA multi-book consensus"
```

---

### Task 5: Compose player decision view-models from preserved outputs

**Files:**
- Create: `wnba_pra_product_view_model_v1.py`
- Create: `tests/test_wnba_pra_product_view_model_v1.py`

**Interfaces:**
- Consumes:
  - Task 1 `PRAProductSnapshot`
  - Task 3 `PlayoffContext`
  - Task 4 consensus DataFrame
- Produces:
  - `PlayerDecisionView` dataclass with:
    - `player_key: str`
    - `player: str`
    - `team: str`
    - `opponent: str`
    - `game_id: str`
    - `headshot_url: str`
    - `team_logo_url: str`
    - `projected_minutes: float | None`
    - `role_label: str`
    - `availability_label: str`
    - `proj_pts: float | None`
    - `proj_reb: float | None`
    - `proj_ast: float | None`
    - `proj_pra: float | None`
    - `market_line: float | None`
    - `book_count: int`
    - `over_probability: float | None`
    - `under_probability: float | None`
    - `edge: float | None`
    - `decision_label: str`
    - `decision_strength: float | None`
    - `final_card_selected: bool`
    - `evidence_state: str`
  - `build_player_views(snapshot: PRAProductSnapshot, context: PlayoffContext, consensus: pd.DataFrame) -> tuple[PlayerDecisionView, ...]`

- [ ] **Step 1: Write failing view-model tests**

Pin the following behavior:
- valid projection with no market still creates a player card with `market_line=None`
- P/R/A/PRA come from preserved projection/matchup rows; do not recalculate a replacement projection
- when stored Monte Carlo/final rows exist, probabilities/decision labels come from those rows
- Final Card membership is determined only by Task 1 `snapshot.final_card`
- unresolved availability returns `UNRESOLVED`/monitor-style evidence and does not erase the player's preliminary projection
- confirmed OUT/INACTIVE players are not marked final-card selected even if stale data exists

- [ ] **Step 2: Run the view-model tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_view_model_v1.py`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement `build_player_views()`**

Join on `game_id` + `player_key` first; only use normalized player name as a guarded fallback when identity-safe. Prefer matchup-adjusted preserved projection rows when available; otherwise use preserved raw projection rows. Never invent missing probability, market, image, or availability fields.

- [ ] **Step 4: Run the view-model tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_view_model_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_product_view_model_v1.py tests/test_wnba_pra_product_view_model_v1.py
git commit -m "feat: compose WNBA PRA player decision views"
```

---

### Task 6: Render the playoff-first PRA customer surface and collapsed diagnostics

**Files:**
- Create: `wnba_pra_product_view_v1.py`
- Create: `wnba_pra_advanced_diagnostics_v1.py`
- Create: `tests/test_wnba_pra_product_view_v1.py`

**Interfaces:**
- Consumes:
  - Task 1 snapshot
  - Task 3 playoff context
  - Task 5 player views
  - Task 4 consensus
- Produces:
  - `render_pra_product(snapshot, context, player_views, consensus) -> None`
  - `render_advanced_diagnostics(snapshot, context, consensus) -> None`

- [ ] **Step 1: Write failing presentation-contract tests**

Test source/HTML/Streamlit-call contracts that guarantee:
- customer surface contains `WNBA PRA`, playoff/next-game context, player board, P/R/A detail, market source count, and Final PRA Card
- normal surface does not render headings `Step 6`, `Step 7`, `Step 8`, `Step 9`
- normal surface does not render `RUN PRA 5,000,000 STANDARD SIMS`, `PRA production HOLD`, or `Monte Carlo restore DISABLED`
- diagnostics expander exists and is collapsed by default
- off-day + next verified game renders both “no game today” context and the next matchup
- no market rows shows projection research with a plain-language market-unavailable message
- unresolved availability keeps preliminary research visible and displays “Final PRA decisions are waiting for verified availability.”
- Final PRA Card renders only rows already selected in `snapshot.final_card`, max five, with no new sorting/selection algorithm
- CSS contains narrow-screen rules and no fixed-width horizontal board that overflows mobile

- [ ] **Step 2: Run presentation tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_view_v1.py`
Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement customer rendering**

Order:
1. playoff header / selected-vs-effective slate context
2. compact freshness/evidence badges
3. PRA player board
4. per-player expandable detail: Decision Snapshot, P/R/A, Minutes + Role, Recent Form, Opponent Context, Matchup History, Market Comparison, Why This Side, Sources + Freshness
5. clean Final PRA Card
6. collapsed Advanced Diagnostics

Use existing identity/headshot/logo helpers where already available; do not introduce a new identity provider in this task.

- [ ] **Step 4: Implement `render_advanced_diagnostics()`**

Expose raw schedule/source diagnostics, availability/role diagnostics, market consensus details, raw Step/Monte Carlo states, provider failures, and conflict evidence only under the collapsed expander.

- [ ] **Step 5: Run presentation tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_product_view_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wnba_pra_product_view_v1.py wnba_pra_advanced_diagnostics_v1.py tests/test_wnba_pra_product_view_v1.py
git commit -m "feat: render playoff-first WNBA PRA product"
```

---

### Task 7: Activate the successor behind the existing WNBA PRA compatibility boundary

**Files:**
- Create: `wnba_pra_hub_v3615.py`
- Modify: `wnba_pra_hub_v3612.py`
- Create: `tests/test_wnba_pra_playoff_product_route_v1.py`

**Interfaces:**
- `wnba_pra_hub_v3615.render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None`
- `wnba_pra_hub_v3612` remains the historical compatibility import used by `streamlit_memory_lazy_router_v1._render_wnba("PRA")`, but changes only its `active` successor from `wnba_pra_hub_v3614` to `wnba_pra_hub_v3615`.
- Universal Runtime V5 adapter stays unchanged.

- [ ] **Step 1: Write failing route tests**

Assert:
- `wnba_pra_hub_v3612` forwards to `wnba_pra_hub_v3615`
- `universal_runtime_v5_loader.resolve_destination(RuntimeRoute("wnba", "pra", ...))` still returns the existing WNBA PRA Step-9 adapter rather than a new parallel route
- the successor installs the existing `wnba_pra_api_market_bridge_v1` ownership before taking the snapshot
- the successor calls Tasks 1-6 and does not call the legacy full page renderer
- date/player interactions keep the WNBA/PRA route state rather than falling back to home/another sport

- [ ] **Step 2: Run route tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_playoff_product_route_v1.py`
Expected: FAIL because V3.6.15 is not active.

- [ ] **Step 3: Implement `wnba_pra_hub_v3615.py`**

Sequence:
1. install existing API market bridge
2. read the selected slate date from existing WNBA PRA session state/date control
3. resolve playoff context
4. build the product snapshot for `context.effective_date`
5. build market consensus and player views
6. render the product

Export existing baseline constants through the predecessor wrapper for compatibility. Do not call `previous.render_wnba_pra_hub()` because that would re-render the legacy Step 6-9 customer surface.

- [ ] **Step 4: Advance `wnba_pra_hub_v3612.py` to the V3.6.15 successor**

Change only the active import/compatibility metadata required for the successor. Keep the historical module name intact.

- [ ] **Step 5: Run route + existing compatibility tests**

Run:
`python -m pytest --noconftest -q tests/test_wnba_pra_playoff_product_route_v1.py tests/test_wnba_pra_page_cleanup_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wnba_pra_hub_v3615.py wnba_pra_hub_v3612.py tests/test_wnba_pra_playoff_product_route_v1.py
git commit -m "feat: activate WNBA PRA playoff product successor"
```

---

### Task 8: End-to-end regression, Runless proof, merge, and GREEN + FROZEN closeout

**Files:**
- Create: `tests/test_wnba_pra_playoff_product_e2e_v1.py`
- Create: `devsystem/runless_proof_plans/monster-wnba-pra-playoff-product-v1.json`

**Interfaces:**
- No new product interfaces.
- Proof plan owns only this WNBA PRA redesign's files/tests plus required existing WNBA PRA and universal-navigation regressions.

- [ ] **Step 1: Write failing end-to-end tests before route finalization**

Use Streamlit/app test coverage or the repo's existing route harness to pin:
- WNBA -> PRA opens the new product surface
- verified off-day auto-surfaces the next playoff game
- player expand/collapse stays on WNBA/PRA
- no raw Step 6-9 UI is visible
- Final Card rows equal `wnba_pra_final_v32.select_master_card()` output for the same stored Monte Carlo fixture
- fixed projection/market/matchup fixtures are value-equivalent before and after the presentation successor
- universal navigation remains unchanged

- [ ] **Step 2: Run all new tests plus existing PRA regressions**

Run:
`python -m pytest --noconftest -q tests/test_wnba_pra_product_snapshot_v1.py tests/test_wnba_pra_source_fusion_v1.py tests/test_wnba_pra_playoff_context_v1.py tests/test_wnba_pra_market_consensus_v1.py tests/test_wnba_pra_product_view_model_v1.py tests/test_wnba_pra_product_view_v1.py tests/test_wnba_pra_playoff_product_route_v1.py tests/test_wnba_pra_playoff_product_e2e_v1.py tests/test_wnba_pra_page_cleanup_v1.py`
Expected: PASS.

Run the existing successor-compatible production regressions used by the Universal Runtime V5 proof plan, including the WNBA PRA Step-9 speed/duplicate-key coverage with the same established exclusions already present in `devsystem/runless_proof_plans/api2-universal-runtime-v5.json`.
Expected: PASS for the authoritative focused regression bundle.

- [ ] **Step 3: Create the focused Runless proof plan**

The proof plan must compile all new modules and run the exact tests from Step 2. It must not include stale historical tests that assert an intentionally superseded WNBA PRA presentation version is still active.

- [ ] **Step 4: Commit the E2E test and proof plan**

```bash
git add tests/test_wnba_pra_playoff_product_e2e_v1.py devsystem/runless_proof_plans/monster-wnba-pra-playoff-product-v1.json
git commit -m "test: prove WNBA PRA playoff product"
```

- [ ] **Step 5: Acquire one scope lease and open one authoritative PR**

Write paths must include only the new WNBA PRA product modules, the `wnba_pra_hub_v3612.py` compatibility change, tests, proof plan, and docs already on this lane. Reuse the same lease/PR through finalization.

- [ ] **Step 6: Run one exact-head authoritative Runless proof**

Required result: `failure_class = NONE`, terminal merge authority on the exact candidate SHA, and GitHub `runless-final-gate` success from the required Runless Proof Plane app.

If proof fails, classify the exact failure once before any patch/retry. Do not create a duplicate PR, proof request, deployment, or branch.

- [ ] **Step 7: Handle base drift with successor proof rather than force-merging stale authority**

If `main` advances, forward-port the same verified tree onto current main, preserve ancestry required by Runless, and issue one base-drift successor proof on the same PR/lease.

- [ ] **Step 8: Merge exact proven head and verify merged main**

Expected: PR merge succeeds only when the required gate is green on the exact current candidate. Fresh read-back must show the merge commit on `main`.

- [ ] **Step 9: Write the certified finalization-ledger freeze**

Freeze token: `MONSTER_WNBA_PRA_PLAYOFF_PRODUCT_V1_FROZEN`

Record exact candidate SHA, merged-main SHA, proof digest, artifact blob SHAs, and legacy-registry read-only bridge. Do not mutate unrelated active thaws or another workstream's frozen state.

- [ ] **Step 10: Close Runless terminal state and release the scope lease**

Required terminal state: `GREEN_FROZEN`, `failure_class = NONE`.

Release the same lease with compare-and-swap, then verify the holder is absent.

- [ ] **Step 11: Final evidence read-back**

Freshly verify:
- authoritative PR merged
- exact main SHA
- exact required Runless check success
- finalization ledger token/revision/hash
- exact artifact record
- legacy registry unchanged/read-only bridge intact
- scope lease released

Only then report **🟢 100% GREEN + FROZEN**.

---

## Plan Self-Review Results

- **Spec coverage:** All approved spec sections map to Tasks 1-8: preserved model boundary, playoff/off-day behavior, multi-source evidence, multi-book consensus, PRA-first player details, Final Card, diagnostics, routing, performance-safe reuse, mobile presentation, testing, rollback-compatible successor activation, and GREEN + FROZEN finalization.
- **Step scan:** Each implementation step has one checkable outcome; no task asks an implementer to redesign the PRA math or choose an undefined product behavior.
- **Type consistency:** `PRAProductSnapshot`, `PlayoffContext`, consensus DataFrame, and `PlayerDecisionView` are defined once and consumed by later tasks with matching names.
- **Review Focus:** The five highest-risk uncovered conditions are explicitly assigned to Tasks 1-6 and included in their tests.
- **Proportion:** The plan defines interfaces/tests/commands but leaves function bodies to implementation; it does not duplicate the design spec or transcribe the code.
