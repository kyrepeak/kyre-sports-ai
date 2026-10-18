# API 2 NFL Daily Picks V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production NFL Daily Picks page that ranks the strongest fresh pregame candidates across Moneyline, Spread, Game Total, Passing Yards, Rushing Yards, and Receiving Yards without creating a second prediction engine.

**Architecture:** Add a read-only aggregation layer over the existing certified NFL market engines. Normalize source-owned outputs into one common candidate contract, apply pregame/freshness/identity gates, score and de-duplicate correlated exposure, then render a Pure Best 10 board. Runtime V5 receives one explicit `NFL / daily-picks` destination so the route can never fall through to the generic NFL foundation page.

**Tech Stack:** Python 3, Streamlit, pandas, existing Kyre Sports NFL market modules, pytest, Universal Runtime V5, Runless V2 finalization.

**Spec:** `docs/superpowers/specs/2026-10-18-api2-nfl-daily-picks-v1-design.md`

## Global Constraints

- Daily Picks is read-only with respect to source-market projections, probabilities, lines, grades, and recommendations.
- Approved source families are exactly: Moneyline, Spread, Game Total, Passing Yards, Rushing Yards, Receiving Yards.
- Pregame only: in-progress and final games are ineligible.
- Pure Best 10: no forced market quotas and no filler when fewer than 10 qualify.
- Correlation safety removes redundant/conflicting exposure but does not impose one-pick-per-game.
- Exact game/player identity is mandatory; no loose fallback matching.
- Stale, non-finite, unavailable, or source-gated rows fail closed.
- One unhealthy source market may degrade its own status but may not crash the page.
- Daily Picks must not execute six full market UIs behind the scenes.
- Runtime V5 generation ownership remains authoritative; stale Daily Picks work may not repaint another route.
- Existing source models and unrelated NFL/CFB/NBA/WNBA/MLB pages are out of scope.
- Step 2A + anti-loop: one branch, one PR, one candidate at a time, one authoritative proof path.

## Review Focus

1. **Source output exists but has no final actionable grade** — adapter must report `UNAVAILABLE`/`GATED`, not manufacture a pick from model-vs-line arithmetic. Test in Task 2.
2. **Kickoff boundary race** — a candidate whose kickoff is equal to or earlier than `now` must fail closed even if a cached source row still says pregame. Test in Task 1.
3. **Duplicate thesis across different market labels** — same-team ML/spread style overlap must deterministically retain only the higher-ranked redundant candidate. Test in Task 3.
4. **One adapter throws while five succeed** — healthy candidates still rank and UI reports the failed market separately. Test in Tasks 2 and 4.
5. **Late route work after navigation** — Runtime V5 stale generation cannot render Daily Picks after another destination becomes active. Test in Task 5.

---

### Task 1: Common Candidate Contract and Eligibility Gate

**Files:**
- Create: `nfl_daily_picks_core_v1.py`
- Test: `tests/test_api2_nfl_daily_picks_core_v1.py`

**Interfaces:**
- Consumes: source-owned values supplied by Task 2 adapters.
- Produces:
  - `DailyPickCandidate` dataclass.
  - `MarketLoadResult` dataclass.
  - `candidate_is_eligible(candidate: DailyPickCandidate, *, now_utc: datetime) -> tuple[bool, str]`.
  - `market_status_from_results(results: Sequence[MarketLoadResult]) -> dict[str, str]`.

`DailyPickCandidate` fields must match the approved semantic contract: `market_id`, `market_label`, `game_id`, `game_date`, `kickoff_at`, `team_id`, `opponent_team_id`, `athlete_id`, `subject_label`, `matchup_label`, `side`, `market_line`, `model_projection`, `model_probability`, `edge_value`, `source_ready`, `source_fresh_at`, `source_age_seconds`, `data_quality`, `uncertainty`, `source_version`, `reason_components`, plus `source_grade` and `source_state` so Daily Picks can preserve source eligibility instead of re-grading it.

`MarketLoadResult` fields: `market_id`, `status`, `candidates`, `source_version`, `fresh_at`, `diagnostic`.

- [ ] **Step 1: Write failing core-contract tests**

Add tests asserting:
- a ready, fresh, exact-identity, future-kickoff candidate passes;
- kickoff `<= now_utc` fails;
- `source_ready=False` fails;
- `source_state` in `GATED`, `NO PLAY`, `UNAVAILABLE`, or `STALE` fails;
- non-finite `model_probability` or required market line fails;
- player props without exact `athlete_id` fail;
- team markets may leave `athlete_id=None`;
- stale `source_age_seconds` beyond the candidate's approved freshness threshold fails;
- `market_status_from_results` preserves six independent market states.

- [ ] **Step 2: Run the core tests and confirm RED**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_core_v1.py`
Expected: FAIL because the core module/interfaces do not exist yet.

- [ ] **Step 3: Implement the core contract**

Create the dataclasses and `candidate_is_eligible(...)` exactly as declared. Keep this module pure: no Streamlit, network, session state, or market imports.

- [ ] **Step 4: Run the core tests and confirm GREEN**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_core_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nfl_daily_picks_core_v1.py tests/test_api2_nfl_daily_picks_core_v1.py
git commit -m "feat: add NFL Daily Picks candidate contract"
```

---

### Task 2: Six Read-Only Source-Market Adapters

**Files:**
- Create: `nfl_daily_picks_sources_v1.py`
- Test: `tests/test_api2_nfl_daily_picks_sources_v1.py`

**Interfaces:**
- Consumes: `DailyPickCandidate` and `MarketLoadResult` from Task 1.
- Produces:
  - `load_moneyline_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_spread_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_game_total_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_passing_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_rushing_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_receiving_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult`
  - `load_all_market_candidates(day: date, *, now_utc: datetime, loaders: Mapping[str, Callable] | None = None) -> tuple[MarketLoadResult, ...]`

**Source ownership decisions:**
- Moneyline: consume frozen V8 final grade/edge/Monte Carlo outputs; V9/V15 presentation remains display-only. Preserve the source final state from `nfl_moneyline_hub_v8._build_final(...)` and stored V5/V6/V7 outputs; do not rank a side whose frozen grade is not source-eligible.
- Spread: consume the existing Spread analytics payload under the V8 presentation wrapper; do not parse rendered HTML or recompute the spread model.
- Game Total: consume the certified V10 final-read stack (`nfl_game_totals_hub_v9.py` + `nfl_game_totals_hub_v10.py` / certified compact wrapper), not the older Step-8 projection-only layer. If a final Over/Under source opinion is absent, return no candidate rather than infer one.
- Passing Yards: consume the certified exact-ID current Passing Yards output chain; current route/presentation wrappers may not be used as a substitute for an actionable source row.
- Rushing Yards: consume the V18 FanDuel-only exact-ID market-filtered output and its underlying projection/eligibility facts; no non-FanDuel player may enter Daily Picks.
- Receiving Yards: consume the V20/V21 exact-ID multi-source context and current market/projection output; V21 visual identity is display-only.

Adapters may add a narrow compatibility extractor in this new file, but may not call a full page renderer or copy source-model formulas. If a source lacks a safe read-only result contract, that market returns `UNAVAILABLE` and the implementation pauses before modifying a source engine.

- [ ] **Step 1: Write failing adapter tests with deterministic fixtures**

Use monkeypatched source payloads; no network. Assert:
- each of the six adapter names returns the correct `market_id` and `source_version`;
- source probability/projection/line/grade are copied unchanged;
- a source `QUALIFIED`/equivalent actionable row becomes a candidate;
- a source `NO PLAY`, `GATED`, projection-only, missing-market, or stale row produces no candidate;
- Rushing excludes players without a current FanDuel rushing line;
- player adapters require exact athlete IDs;
- Game Total cannot create Over/Under from projection-minus-line when the source final read is missing;
- one adapter exception becomes `MarketLoadResult(status="ERROR", ...)` while the other five still return normally through `load_all_market_candidates`.

- [ ] **Step 2: Run adapter tests and confirm RED**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_sources_v1.py`
Expected: FAIL because adapters do not exist.

- [ ] **Step 3: Implement the six read-only adapters**

Implement the declared functions using the smallest existing data/output surfaces from each certified market chain. Do not call `render_nfl_hub`, `render_nfl_*_hub`, or scrape HTML.

- [ ] **Step 4: Run adapter tests and confirm GREEN**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_sources_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nfl_daily_picks_sources_v1.py tests/test_api2_nfl_daily_picks_sources_v1.py
git commit -m "feat: add NFL Daily Picks source adapters"
```

---

### Task 3: Pure Best 10 Ranking and Correlation Safety

**Files:**
- Create: `nfl_daily_picks_ranking_v1.py`
- Test: `tests/test_api2_nfl_daily_picks_ranking_v1.py`

**Interfaces:**
- Consumes: eligible `DailyPickCandidate` values from Task 1/2.
- Produces:
  - `normalized_pick_score(candidate: DailyPickCandidate) -> float`
  - `correlation_key(candidate: DailyPickCandidate) -> tuple[str, ...]`
  - `picks_conflict(left: DailyPickCandidate, right: DailyPickCandidate) -> bool`
  - `picks_redundant(left: DailyPickCandidate, right: DailyPickCandidate) -> bool`
  - `rank_daily_picks(candidates: Sequence[DailyPickCandidate], *, now_utc: datetime, limit: int = 10) -> tuple[DailyPickCandidate, ...]`

The normalized score is Daily-Picks-only. It must compare existing source facts using model probability, source-owned edge, data quality, freshness, and uncertainty penalties without mutating any source value. Load order must not affect ranking.

- [ ] **Step 1: Write failing ranking tests**

Assert:
- higher probability/edge/freshness/quality wins when otherwise comparable;
- input objects are unchanged after ranking;
- no market quota exists;
- 12 valid candidates return exactly the top 10;
- 7 valid candidates return exactly 7;
- same-side ML/spread near-duplicate exposure collapses to the higher-ranked candidate when `picks_redundant` says they share the same thesis;
- exact contradictory directions on the same market/identity cannot coexist;
- distinct same-game player prop and team pick may coexist;
- ties resolve by data quality, freshness, uncertainty, independent edge, then stable identity order;
- shuffled input produces the same final order.

- [ ] **Step 2: Run ranking tests and confirm RED**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_ranking_v1.py`
Expected: FAIL because ranking module does not exist.

- [ ] **Step 3: Implement ranking and correlation rules**

Implement the declared functions. Keep the module pure and deterministic; no Streamlit/session state/network access.

- [ ] **Step 4: Run ranking tests and confirm GREEN**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_ranking_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nfl_daily_picks_ranking_v1.py tests/test_api2_nfl_daily_picks_ranking_v1.py
git commit -m "feat: rank NFL Daily Picks with correlation safety"
```

---

### Task 4: Daily Picks Page UI, Diagnostics, and Raw-HTML Protection

**Files:**
- Create: `nfl_daily_picks_hub_v1.py`
- Test: `tests/test_api2_nfl_daily_picks_hub_v1.py`

**Interfaces:**
- Consumes: `load_all_market_candidates(...)` and `rank_daily_picks(...)`.
- Produces:
  - `build_daily_picks_board(day: date, *, now_utc: datetime, loaders: Mapping[str, Callable] | None = None) -> dict[str, Any]`
  - `render_nfl_daily_picks_hub() -> None`
  - `render_nfl_hub(market: str = "Daily Picks") -> None`

`build_daily_picks_board` returns a pure presentation payload with `market_statuses`, `ranked_picks`, `healthy_market_count`, `candidate_count`, and `diagnostics`. The renderer may convert that payload to HTML/Streamlit, but source loading/ranking must be testable without UI.

- [ ] **Step 1: Write failing page tests**

Assert:
- six-market status strip is always represented;
- one ERROR market still renders picks from healthy markets;
- zero candidates renders `No qualified pregame picks are currently available.` plus diagnostics;
- fewer than 10 candidates are not padded;
- card payload exposes rank, market, subject, matchup, line, side, probability, projection when applicable, confidence/quality, why text, risk/toughness, freshness, kickoff;
- renderer never calls the old NFL foundation fallback;
- literal `<article class="knfl-game">` is never emitted as visible text;
- page uses one controlled card render path and no six-page hidden rendering.

- [ ] **Step 2: Run page tests and confirm RED**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_hub_v1.py`
Expected: FAIL because page module does not exist.

- [ ] **Step 3: Implement the Daily Picks board and renderer**

Render the page shell first, then statuses and ranked cards from the already-built board payload. Keep the existing Kyre Sports AI dark/glacier style; no unrelated navigation redesign.

- [ ] **Step 4: Run page tests and confirm GREEN**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_hub_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nfl_daily_picks_hub_v1.py tests/test_api2_nfl_daily_picks_hub_v1.py
git commit -m "feat: add NFL Daily Picks Top 10 board"
```

---

### Task 5: Runtime V5 Route Ownership, Regression Gate, and Runless Freeze

**Files:**
- Modify: `universal_runtime_v5_loader_v11.py`
- Create: `tests/test_api2_nfl_daily_picks_route_v1.py`
- Create: `devsystem/runless_proof_plans/api2-nfl-daily-picks-v1.json`

**Interfaces:**
- Consumes: `nfl_daily_picks_hub_v1.render_nfl_hub` from Task 4.
- Produces: explicit `RuntimeRoute(sport_id="nfl", market_id="daily-picks")` resolution to `nfl_daily_picks_hub_v1` using the existing `_nfl_adapter` contract.

Route mutation must be a single narrow clause in the current Runtime V5 overlay. Before changing `universal_runtime_v5_loader_v11.py`, inspect the frozen-artifact registry once; if the path is currently frozen, obtain the authorized thaw/forward-port path rather than bypassing ownership.

- [ ] **Step 1: Write failing route and generation tests**

Assert:
- `NFL / daily-picks` resolves to adapter source version `nfl_daily_picks_hub_v1`;
- Moneyline, Spread, Game Total, Passing Yards, Rushing Yards, Receiving Yards retain their existing destinations;
- the Daily Picks destination never resolves to `nfl_hub_v18`/NFL V1 fallback;
- stale-generation completion cannot render after a later route becomes active;
- switching away from Daily Picks preserves only allowed cache updates.

- [ ] **Step 2: Run route test and confirm RED**

Run: `python -m pytest -q tests/test_api2_nfl_daily_picks_route_v1.py`
Expected: FAIL because `daily-picks` is not explicitly mapped.

- [ ] **Step 3: Add the explicit V5 route**

In `universal_runtime_v5_loader_v11.resolve_destination(route)`, add only:

```python
if route.sport_id == "nfl" and route.market_id == "daily-picks":
    return prior._nfl_adapter(route, "nfl_daily_picks_hub_v1", ttl_ms=20_000)
```

Preserve existing Rushing Yards and CFB Top Picks overlay clauses unchanged.

- [ ] **Step 4: Create the Runless proof plan**

The proof plan must compile the new modules and run exactly the new Daily Picks suites plus the current certified Runtime V5 navigation/regression surface. The frozen V5 proof defines that current runtime surface as:

- `tests/test_universal_sports_nav_controller_v1.py`
- `tests/test_universal_sports_nav_url_v1.py`
- `tests/test_universal_sports_nav_registry_v1.py`
- `tests/test_api2_route_transition_mask_v1.py`
- `tests/test_api2_universal_nav_single_owner_speed_v1.py`
- `tests/test_cfb_top_picks_professional_v11_r1.py`

For NFL/product guard coverage, retain the current focused rushing regression `tests/test_api2_nfl_rushing_cleanup_v1.py`. Do not broaden into historical frozen-era router suites that are no longer part of Runtime V5's certified proof surface.

Artifacts must include only the new Daily Picks modules/tests, the narrow V5 overlay mutation, and the proof plan itself.

- [ ] **Step 5: Run the authoritative local regression gate**

Run:

```bash
python -m py_compile \
  nfl_daily_picks_core_v1.py \
  nfl_daily_picks_sources_v1.py \
  nfl_daily_picks_ranking_v1.py \
  nfl_daily_picks_hub_v1.py \
  universal_runtime_v5_loader_v11.py

python -m pytest --noconftest -q \
  tests/test_api2_nfl_daily_picks_core_v1.py \
  tests/test_api2_nfl_daily_picks_sources_v1.py \
  tests/test_api2_nfl_daily_picks_ranking_v1.py \
  tests/test_api2_nfl_daily_picks_hub_v1.py \
  tests/test_api2_nfl_daily_picks_route_v1.py \
  tests/test_universal_sports_nav_controller_v1.py \
  tests/test_universal_sports_nav_url_v1.py \
  tests/test_universal_sports_nav_registry_v1.py \
  tests/test_api2_route_transition_mask_v1.py \
  tests/test_api2_universal_nav_single_owner_speed_v1.py \
  tests/test_cfb_top_picks_professional_v11_r1.py \
  tests/test_api2_nfl_rushing_cleanup_v1.py
```

Expected: all selected tests PASS and compile exits 0. These Runtime V5 regression filenames are pinned from the existing frozen V5 Runless proof plan rather than guessed at execution time.

- [ ] **Step 6: Commit the route + proof gate**

```bash
git add universal_runtime_v5_loader_v11.py tests/test_api2_nfl_daily_picks_route_v1.py devsystem/runless_proof_plans/api2-nfl-daily-picks-v1.json
git commit -m "feat: route NFL Daily Picks through Runtime V5"
```

- [ ] **Step 7: Lock one candidate and finish through the authority chain**

Execution order is mandatory:

1. re-read current `main` once;
2. forward-port the same branch once only if main drifted;
3. acquire one non-conflicting API 2 scope lease;
4. open/reuse one PR;
5. submit one Runless proof for the exact candidate SHA and expected main SHA;
6. if proof is terminal failure, classify that exact failure before one root-cause patch;
7. after `MERGE_AUTHORIZED`, merge the proven exact head;
8. write immutable finalization ledger record before closeout;
9. call closeout/readback and require `GREEN_FROZEN`, `failure_class=NONE`;
10. release the exact scope lease and read back its absence;
11. fresh-read merged-main route + Daily Picks module + freeze record before claiming completion.

Target freeze token: `API2_NFL_DAILY_PICKS_V1_FROZEN`.

- [ ] **Step 8: Final verification receipt**

Completion evidence must include PR number, candidate SHA, merged-main SHA, proof ID, gate run ID, receipt digest, freeze token, manifest state hash, finalization record hash/blob, and released lease readback.

Terminal state: `🟢 100% — GREEN + 🧊 FROZEN`.
