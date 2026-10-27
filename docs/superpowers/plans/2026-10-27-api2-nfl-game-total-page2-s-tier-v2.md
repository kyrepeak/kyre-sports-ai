# API2 NFL Game Total Page 2 S-Tier V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved premium NFL Game Total Page 2 with matchup history and compact decision hierarchy while preserving Page 1 and all frozen projection owners.

**Architecture:** Add a V12 presentation successor over V11/V8/V9/V10, plus a focused display-context helper for nflverse matchup history and NFL.com official availability. Route only the canonical Game Total adapter to V12. Keep all historical/market/availability context display-only with model influence 0.0%.

**Tech Stack:** Python, Streamlit, pandas, existing Kyre Sports API adapters, nflverse, NFL.com official injury report, pytest.

**Spec:** `docs/superpowers/specs/2026-10-27-api2-nfl-game-total-page2-s-tier-v2-design.md`

## Global Constraints
- API2 only; no MONSTER state dependency.
- Page 1 source and frozen card output are unchanged.
- Existing V8/V9/V10 analytics remain projection authorities.
- No ESPN, ESPN BET, or SGO.
- Matchup history, injuries, and sportsbook context have model influence 0.0%.
- Stake sizing OFF; wager actions OFF.

## Review Focus
- Missing historical `total_line` must show semantic `—`, never fabricate a closing total or O/U result.
- Unavailable injury source must render a compact unavailable state, not break Page 2.
- Unknown/blank game identity must fail closed without cross-team history leakage.
- Page 1 handoff and visual owner must remain unchanged.
- Mobile layout must avoid raw IDs, STEP labels, and oversized debug/certification sections.

---

### Task 1: RED presentation + context contract
**Files:**
- Create: `tests/test_api2_nfl_game_total_page2_s_tier_v2.py`

**Interfaces:**
- Consumes existing V11 route helpers and certified V8/V9/V10 payload shapes.
- Defines expected V12 symbols and HTML markers.

- [ ] Write failing tests requiring V12, `MATCHUP HISTORY`, `WHY THIS READ`, `KEY AVAILABILITY`, `GAME PROFILE`, `PROJECTION RANGE`, `BOTTOM LINE`, and no visible `STEP 3`-`STEP 10`/raw event ID debug copy.
- [ ] Add failing history tests for exact-team filtering, latest-three ordering, verified `total_line`, O/U outcome, and semantic missing-line behavior.
- [ ] Add failing availability tests for compact official NFL injury summaries and unavailable-source fallback.
- [ ] Run focused tests and confirm RED because V12/context helper do not exist.

### Task 2: Display-context helper
**Files:**
- Create: `nfl_game_totals_page2_context_v2.py`
- Test: `tests/test_api2_nfl_game_total_page2_s_tier_v2.py`

**Interfaces:**
- Produces `normalize_matchup_history(frame, away_abbr, home_abbr, limit=3) -> dict`.
- Produces `load_matchup_history(row, limit=3) -> dict`.
- Produces `normalize_availability(report, away_abbr, home_abbr, limit_per_team=2) -> dict`.
- Produces `load_availability(row) -> dict`.

- [ ] Implement exact-team nflverse history with `combined_score`, verified closing `total_line`, and `OVER`/`UNDER`/`PUSH` only when the line exists.
- [ ] Implement NFL.com official availability using existing `collect_official_nfl_injury_report`, prioritizing QB/RB/WR/TE/OL and meaningful statuses.
- [ ] Run focused tests to GREEN.

### Task 3: V12 S-tier Page 2 presentation
**Files:**
- Create: `nfl_game_totals_hub_v12.py`
- Test: `tests/test_api2_nfl_game_total_page2_s_tier_v2.py`

**Interfaces:**
- Reuses V11 Page 1 by delegation.
- Produces `build_page2_html(item, history, availability, day_str) -> str`.
- Produces `render_nfl_game_totals_hub()` / `render_nfl_hub()`.

- [ ] Build compact hero with Market Total, Kyre Total, Edge, Final Read and one integrity strip.
- [ ] Build 3-driver Why This Read from certified pace/red-zone/environment/market-range context.
- [ ] Build compact Market Context and Matchup History cards.
- [ ] Build Key Availability and compact Game Profile rows.
- [ ] Build projection-range centerpiece and Bottom Line; move provenance to collapsed Data & Sources.
- [ ] Preserve back link and selected-game identity; remove giant certification/debug UI.
- [ ] Run focused tests to GREEN.

### Task 4: Canonical route promotion
**Files:**
- Modify: `universal_runtime_v5_loader.py`
- Test: `tests/test_api2_nfl_game_total_page2_s_tier_v2.py`

**Interfaces:**
- Game Total adapter imports `nfl_game_totals_hub_v12` and reports source version `nfl_game_totals_hub_v12`.

- [ ] Update only `_nfl_game_total_adapter` successor target.
- [ ] Prove frozen Page 1 owner import remains explicit.
- [ ] Run focused + existing Game Total regression suites.

### Task 5: Control-plane proof package
**Files:**
- Create: `devsystem/runless_proof_plans/api2-nfl-game-total-page2-s-tier-v2.json`
- Create: `devsystem/task_ledgers/api2-nfl-game-total-page2-s-tier-v2.json`

- [ ] Seal one authoritative candidate, scope, acceptance commands, 0.0% influence constraints, and freeze token `API2_NFL_GAME_TOTAL_PAGE2_S_TIER_V2_FROZEN`.
- [ ] Compile + focused regressions + broad relevant Game Total tests.
- [ ] Open exactly one PR and submit/reuse exactly one Runless proof.
- [ ] Exact-head merge after terminal proof.
- [ ] Step 2G: mirror approved artifacts to `api2-main`, certify live Streamlit Page 2 markers, write immutable convergence sidecar, close out `GREEN_FROZEN`, and verify lease release.
