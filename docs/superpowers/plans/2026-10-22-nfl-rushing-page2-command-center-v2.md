# NFL Rushing Yards Page 2 Command Center V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an S-tier decision-first NFL Rushing Yards Page 2 that explains the Kyre projection with verified workload, recent-form, matchup, advanced-efficiency, market, and game-script evidence.

**Architecture:** Keep the current Kyre Sports API Rushing Yards slate schema and Page 1 route unchanged. Add verified/derived Page 2 analytics inside each card's existing `detail` payload in `sports_api/api/nfl_rushing_yards_slate_v1.py`, then upgrade `nfl_rushing_yards_professional_v1.py` to render a decision cockpit and evidence hierarchy from those additive fields. Missing unsupported inputs remain semantic states, never fake values.

**Tech Stack:** Python, FastAPI payload assembly, pandas, Streamlit HTML/CSS, pytest, existing Runless V2 proof plane.

**Spec:** `docs/superpowers/specs/2026-10-22-nfl-rushing-page2-command-center-v2-design.md`

## Global Constraints
- Kyre Sports API is the only application-facing NFL data gateway.
- Do not use SGO, ESPN, or ESPN BET.
- Do not change Page 1, RB1/RB2 selection, upcoming-game filtering, sportsbook selection, canonical IDs, or the market-blind projection model.
- Never average sportsbook records into a fake line.
- Never convert missing/unknown/not-posted data into zero.
- Preserve source lineage and semantic empty states.
- Page 2 additions must be backward compatible inside the existing `detail` object.

## Review Focus
- Optional play-by-play columns may be absent; advanced metrics must degrade to semantic states instead of crashing.
- Players with fewer than three/five games must compute L3/L5 from available qualifying games without fabricating samples.
- Hit rate must not be calculated when the current market line is unverified.
- Comparable matchups must join by canonical opponent/team context and never by display-name similarity.
- Mobile Page 2 must not introduce horizontal page overflow; data tables may scroll internally.

---

### Task 1: RED contract for Page 2 analytics

**Files:**
- Create: `tests/test_api2_nfl_rushing_page2_command_center_v2.py`

**Interfaces:**
- Consumes: `sports_api.api.nfl_rushing_yards_slate_v1` and `nfl_rushing_yards_professional_v1`.
- Produces: acceptance contract for additive `detail` analytics and decision-first rendering.

- [ ] **Step 1: Write failing tests**
  - Assert optional play-by-play columns include `epa`, `success`, `yardline_100`, `qtr`, and `score_differential`.
  - Assert player game rows can expose explosive/stuffed attempts, success rate, EPA, red-zone, goal-line, fourth-quarter, leading, and trailing usage without converting missing columns to zero.
  - Assert helper summaries compute L3/L5 workload, trend, team rush share, recent median/floor/ceiling/hit rate, comparable matchups, and advanced efficiency.
  - Assert a detail payload contains `decision`, `workload_intelligence`, `recent_form`, `game_script`, `comparable_matchups`, `advanced_efficiency`, `market_intelligence`, `personnel`, and `final_read`.
  - Assert renderer contains the eight command-center sections and never renders `N/A` or generic `Unavailable`.

- [ ] **Step 2: Run focused test and verify RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page2_command_center_v2.py`
  - Expected: FAIL because V2 analytics/sections do not exist yet.

- [ ] **Step 3: Commit RED test**
  - Commit message: `test: define rushing Page 2 command center v2`

---

### Task 2: Kyre Sports API Page 2 analytics enrichment

**Files:**
- Modify: `sports_api/api/nfl_rushing_yards_slate_v1.py`
- Test: `tests/test_api2_nfl_rushing_page2_command_center_v2.py`

**Interfaces:**
- Consumes: verified canonical play-by-play rows, roster rows, existing projection/market/defense/history data.
- Produces: additive Page 2 dictionaries in each card's `detail` object.

- [ ] **Step 1: Extend optional play-by-play extraction**
  - Add optional fields for EPA, success, yardline, quarter, and score differential.
  - Preserve fail-closed behavior when columns are absent.

- [ ] **Step 2: Add per-game derived rushing context**
  - Calculate explosive runs (`>=10` yards), stuffed runs (`<=0` yards), success rate, EPA/attempt, red-zone carries (`yardline_100 <= 20`), goal-line carries (`yardline_100 <= 5`), fourth-quarter carries, and leading/trailing carries only from verified rows.

- [ ] **Step 3: Add pure summary helpers**
  - `build_workload_intelligence(...)` → season/L3/L5 carries, rush share, trend, red-zone/goal-line/4Q/leading/trailing usage.
  - `build_recent_form(...)` → L3/L5/season average, median, floor, ceiling, current-line hit rate only when market verified.
  - `build_comparable_matchups(...)` → recent verified games against opponents sharing the target defense grade.
  - `build_advanced_efficiency(...)` → explosive/stuff/success/EPA rates and usage shares with semantic status when inputs are absent.
  - `build_game_script(...)` → team/player rushing-volume context plus semantic spread/total/weather states when not verified.
  - `build_final_read(...)` → deterministic evidence, risks, and unresolved items from verified fields only.

- [ ] **Step 4: Attach additive Page 2 blocks to `detail`**
  - Preserve all existing detail fields for backward compatibility.
  - Add source-lineage entries for each derived block.

- [ ] **Step 5: Run focused tests to GREEN**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page2_command_center_v2.py`
  - Expected: analytics tests pass; renderer section tests may remain RED until Task 3.

- [ ] **Step 6: Commit**
  - Commit message: `feat: enrich rushing Page 2 analytics`

---

### Task 3: S-tier Page 2 decision cockpit renderer

**Files:**
- Modify: `nfl_rushing_yards_professional_v1.py`
- Test: `tests/test_api2_nfl_rushing_page2_command_center_v2.py`

**Interfaces:**
- Consumes: additive Page 2 `detail` analytics from Task 2.
- Produces: professional decision-first Page 2 HTML.

- [ ] **Step 1: Implement Decision Cockpit**
  - Show player/team/role/opponent/kickoff, current line/book, Kyre projection, edge, model side, side probability, confidence, expected carries, expected YPC.
  - Use `WAIT`/semantic market state when no verified line exists.

- [ ] **Step 2: Implement evidence sections**
  - Workload Intelligence.
  - Recent Form with internal-scroll game log.
  - Opponent Run Defense.
  - Game Script Intelligence.
  - Matchup + Comparable History.
  - Advanced Efficiency.
  - Market Intelligence + Personnel/Availability.
  - Final Kyre Read + Source Lineage.

- [ ] **Step 3: Add responsive CSS**
  - Preserve dark Kyre presentation, strong information hierarchy, compact comparison strips, and internal-only table scrolling on mobile.

- [ ] **Step 4: Run focused tests to GREEN**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page2_command_center_v2.py`
  - Expected: PASS.

- [ ] **Step 5: Commit**
  - Commit message: `feat: build rushing Page 2 decision cockpit`

---

### Task 4: Frozen architecture regression + exact-head proof

**Files:**
- Reuse: `tests/test_api2_nfl_rushing_yards_simple_rb_grid_v1.py`
- Reuse: `tests/test_api2_nfl_rushing_page1_cleanup_v1.py`
- Create: `devsystem/runless_proof_plans/api2-nfl-rushing-page2-command-center-v2.json`
- Create: `devsystem/task_ledgers/api2-nfl-rushing-page2-command-center-v2.json`

**Interfaces:**
- Consumes: final API + Page 2 renderer.
- Produces: exact-head Runless proof inputs and freeze token `API2_NFL_RUSHING_PAGE2_COMMAND_CENTER_V2_FROZEN`.

- [ ] **Step 1: Run Page 2 + inherited Rushing Yards regression suite**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page2_command_center_v2.py tests/test_api2_nfl_rushing_yards_simple_rb_grid_v1.py tests/test_api2_nfl_rushing_page1_cleanup_v1.py`
  - Expected: all PASS.

- [ ] **Step 2: Add Runless proof plan + task ledger**
  - Bind exact source main SHA, scope lease, commands, artifacts, App 5204253 check, no GitHub Actions fallback, and freeze token.

- [ ] **Step 3: Verify no base drift and request one Runless proof**
  - If main moved, reconcile this same branch/PR once and rerun the exact suite before proof.
  - Require `runless-final-gate` success from App 5204253 on the exact candidate SHA.

- [ ] **Step 4: Merge only the proven exact head**
  - Use expected-head protection.

- [ ] **Step 5: Verify merged main**
  - Run the same regression suite on the merge commit and inspect source ownership.

- [ ] **Step 6: Finalize and freeze**
  - Append Finalization Ledger V2 record/manifest/bridge, close out Runless to durable `GREEN_FROZEN`, independently read it back, then release only this workstream's scope lease.