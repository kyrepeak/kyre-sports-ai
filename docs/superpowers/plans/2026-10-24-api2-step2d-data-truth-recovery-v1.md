# API 2 Step 2D Data-Truth Recovery V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Step 2D recovery gap so a technical FanDuel NFL rushing failure cannot become a false blank and Kyre Sports API can recover the field through one approved field-specific fallback.

**Architecture:** Keep FanDuel direct as the primary NFL rushing source. Add a backend-only The Odds API adapter for `player_rush_yds`, invoked only after the primary returns a technical/unverified-empty state. Preserve exact source state, never fabricate team/position/value, and keep the frontend dependent only on Kyre Sports API.

**Tech Stack:** Python 3.11, requests, FastAPI/Kyre Sports API, pytest, GitHub Actions.

**Spec:** User-approved permanent API 2 Step 2D contract in this execution.

## Global Constraints

- API 2 only; do not consult or depend on MONSTER state.
- Kyre Sports API is the only application-facing data gateway.
- No SGO, ESPN, or ESPN BET.
- Empty/timeout/parser/mapping failures are never genuine not-posted proof.
- `VERIFIED_NOT_POSTED` requires successful source/event/market verification.
- Failed ingestion is never negative-cached as genuine absence.
- No sportsbook/stat/injury/projection data may be fabricated.

## Review Focus

- FanDuel returns an empty legacy list while another approved source has a posted rushing line.
- The Odds API key is missing or provider fetch fails.
- The Odds API returns the event but no `player_rush_yds` market.
- Multiple sportsbooks expose the same player and must not be averaged or treated as a conflict.
- A fallback row lacks team/position metadata and must only match by exact player name inside the already exact-matched event.

---

### Task 1: Regression proof for field-specific recovery

**Files:**
- Create: `tests/test_api2_step2d_nfl_rushing_fallback_recovery_v1.py`
- Modify: `.github/workflows/api2-step2d-data-truth-v1.yml`

- [ ] Write failing tests proving an unverified FanDuel empty result triggers exactly one approved The Odds API fallback and that fallback values survive to the final market state.
- [ ] Add the test to the Step 2D certification workflow.
- [ ] Run the authoritative workflow and confirm RED for the missing fallback implementation.

### Task 2: Backend-only The Odds API rushing adapter

**Files:**
- Create: `sports_api/collectors/nfl_the_odds_api_rushing_yards_v1.py`
- Modify: `sports_api/nfl_rushing_yards_data_truth_v1.py`
- Modify: `sports_api/api/nfl_rushing_yards_slate_v1/__init__.py`

- [ ] Implement exact-event matching against home/away teams and query only `player_rush_yds`.
- [ ] Return structured AVAILABLE / VERIFIED_NOT_POSTED / technical failure states.
- [ ] Choose one sportsbook quote per player by approved priority; never average lines.
- [ ] Register it as the field-specific fallback after FanDuel direct.
- [ ] Preserve exact-name fallback mapping inside the already matched event when team/position metadata is absent; reject ambiguity.
- [ ] Run Step 2D certification and related NFL rushing regression tests GREEN.

### Task 3: Exact-head merge and re-freeze

**Files:**
- Update API 2 frozen registry only after merged-state verification.

- [ ] Open one corrective PR from the authoritative Step 2D branch to `api2-main`.
- [ ] Verify exact-head CI success.
- [ ] Merge with expected-head protection.
- [ ] Verify merged `api2-main` SHA and post-merge Step 2D workflow.
- [ ] Write a new API 2 frozen-registry checkpoint containing candidate SHA, merged SHA, evidence digest, and artifact hashes.
- [ ] Read the frozen registry back and verify every recorded value before declaring FROZEN.
