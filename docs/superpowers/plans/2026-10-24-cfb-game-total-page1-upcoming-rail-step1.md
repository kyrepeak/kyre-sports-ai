# CFB Game Total Page 1 Upcoming Rail Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CFB Game Total Page 1 upcoming-only and replace the long multi-game scan with one compact horizontal matchup rail plus one selected existing analytics card.

**Architecture:** Keep Kyre Sports API as the sole application-facing gateway and filter dead games there before sportsbook routing. Add an additive V4 Streamlit successor that reuses V3 card logic, owns only the rail/selection composition, and activates through the existing bootstrap seam.

**Tech Stack:** Python, FastAPI, Streamlit, pytest

**Spec:** `docs/superpowers/specs/2026-10-24-cfb-game-total-page1-upcoming-rail-step1-design.md`

## Global Constraints

- Kyre Sports API only.
- Do NOT use SGO, ESPN, or ESPN BET.
- No provider-wide fan-out; keep existing field-first market routing.
- No sportsbook line averaging.
- No null-to-zero conversion or fabricated values.
- Sportsbook projection influence stays `0.0`.
- Page 2, model, projection, probability, ranking, and selection behavior remain unchanged.
- Started/final games must not appear on pregame Page 1.

## Review Focus

- Explicit-date requests must still remove games once kickoff is reached.
- A stale `scheduled` state cannot keep a game visible after its verified kickoff timestamp.
- Live/final/completed semantic states must be excluded even if kickoff is missing.
- Missing kickoff with a non-terminal state must not be falsely converted to started/final.
- Selecting a rail chip must stay on Page 1; only OPEN ANALYSIS may hand off to Page 2.

---

### Task 1: Upcoming-only API contract

**Files:**
- Modify: `sports_api/api/cfb_game_total_page1_v1.py`
- Test: `tests/test_api2_cfb_game_total_page1_upcoming_rail_step1_r1.py`

**Interfaces:**
- Consumes: existing NCAA canonical schedule rows and `build_page1_payload(...)`.
- Produces: `_is_upcoming_game(game: Mapping[str, Any], now: datetime) -> bool`; `build_page1_payload` returns only actionable pregame games.

- [ ] **Step 1: Write failing tests** covering future kickoff retained, kickoff-at-now removed, live/final/completed states removed, and explicit-date payload filtering before market collection.
- [ ] **Step 2: Run the focused test and confirm RED** because the helper/filter does not exist yet and explicit-date rows still pass through.
- [ ] **Step 3: Implement minimal upcoming predicate and filter** before `_market_state(...)` / consensus collection.
- [ ] **Step 4: Run focused tests and confirm GREEN.**
- [ ] **Step 5: Commit.**

### Task 2: Compact horizontal matchup rail

**Files:**
- Create: `cfb_game_total_page1_atier_v4.py`
- Modify: `cfb_game_total_page1_api_bootstrap_repair_r1.py`
- Test: `tests/test_api2_cfb_game_total_page1_upcoming_rail_step1_r1.py`

**Interfaces:**
- Consumes: V3 CSS/card renderer and V1 API loader/date helpers.
- Produces: `render_game_total_page1()` with a horizontal rail, `cfbgt_game` Page-1 selection key, earliest-upcoming default, and exactly one V3 analytics card below the rail.

- [ ] **Step 1: Extend the failing test** to require V4, horizontal overflow rail CSS, matchup/O-U/kickoff chip content, Page-1-only selection href, one selected card render, and bootstrap V4 activation.
- [ ] **Step 2: Run the focused test and confirm RED** because V4 is absent and wrapper points to V3.
- [ ] **Step 3: Implement the minimal V4 successor** reusing V3/base helpers; do not duplicate provider or analytics logic.
- [ ] **Step 4: Change only the bootstrap successor pointer from V3 to V4.**
- [ ] **Step 5: Run focused tests and confirm GREEN.**
- [ ] **Step 6: Commit.**

### Task 3: Regression and Runless proof artifacts

**Files:**
- Create: `devsystem/execution_plans/api2-cfb-game-total-page1-upcoming-rail-step1-r1.json`
- Create: `devsystem/runless_proof_plans/api2-cfb-game-total-page1-upcoming-rail-step1-r1.json`
- Create: `devsystem/task_ledgers/api2-cfb-game-total-page1-upcoming-rail-step1-r1.json`

**Interfaces:**
- Consumes: exact branch head after Tasks 1–2.
- Produces: one authoritative proof path for compile, focused Step 1 tests, prior CFB Page 1 regression tests, gateway-only/no-forbidden-provider checks, and unchanged Page 2/model boundaries.

- [ ] **Step 1: Add one execution plan** bound to source main `92d3242cdc2a6aedc0568a2e82fc79aaeac79f35` and this branch only.
- [ ] **Step 2: Add one Runless proof plan** with py_compile + focused/regression pytest commands; GitHub Actions fallback remains `0`.
- [ ] **Step 3: Add one task ledger** with GREEN/FROZEN target `API2_CFB_GAME_TOTAL_PAGE1_UPCOMING_RAIL_STEP1_R1_FROZEN`.
- [ ] **Step 4: Verify the exact branch diff is limited to Step 1 scope.**
- [ ] **Step 5: Open one PR and use one exact-head proof/deployment path only.**