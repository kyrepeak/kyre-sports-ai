# API2 NFL Moneyline Page 2 War Room V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved NFL Moneyline selected-matchup War Room Page 2 with verified last-five/full matchup history while preserving frozen Moneyline math.

**Architecture:** Add a Kyre Sports API Page 2 enrichment module, a presentation-only War Room renderer, and a V20 route successor over V19. V20 injects Page-1 navigation and renders one selected game when `view=analysis`; the universal runtime changes only NFL Moneyline V19→V20.

**Tech Stack:** Python 3, Streamlit, pandas, existing Kyre Sports API/nflverse adapters, pytest, Runless V2, Step 2G live browser proof.

**Spec:** `docs/superpowers/specs/2026-10-26-api2-nfl-moneyline-page2-war-room-v1-design.md`

## Global Constraints
- Kyre Sports API is the only application-facing gateway.
- No SGO, ESPN, or ESPN BET.
- History and every Page 2 enrichment are display-only and cannot alter model probability.
- Preserve V8/V7/V6/V5/V4.x/V3/V2 analytical ownership.
- `SPORTSBOOK_MODEL_INFLUENCE = 0.0`; `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`; stake sizing OFF.
- Exactly one selected matchup appears on Page 2.

## Review Focus
- Missing/invalid game ID must fail closed to a clear selected-game-unavailable state.
- nflverse unavailable/history-empty must show semantic empty, never call ESPN.
- Mobile history and comparison grids must not cause horizontal overflow.
- GATED/NO PLAY frozen states must remain GATED/NO PLAY; presentation cannot upgrade them.
- Page-1 navigation must preserve `sport=nfl&market=moneyline` and cannot route to another sport.

---

### Task 1: Lock Page 2 contracts with RED tests
**Files:**
- Create: `tests/test_api2_nfl_moneyline_page2_war_room_v1.py`

**Interfaces:**
- Produces required module names, URL contract, forbidden-provider checks, War Room markers, and history behavior.

- [ ] Write tests for API history normalization, last-five/full-history split, semantic empty, no ESPN/SGO strings, V20 navigation, V21→V20 route ownership, frozen invariants, and War Room section markers.
- [ ] Run focused test and verify RED because Page 2 modules/V20 do not exist and loader still targets V19.

### Task 2: Kyre Sports API Page 2 enrichment
**Files:**
- Create: `sports_api/api/nfl_moneyline_page2_v1.py`
- Test: `tests/test_api2_nfl_moneyline_page2_war_room_v1.py`

**Interfaces:**
- Produces `load_matchup_history(game, limit=5, full_limit=50) -> dict` and `build_page2_context(...) -> dict`.

- [ ] Implement nflverse-only exact-team completed-game history, newest first, default five plus full history, series snapshot, average margin, home-site split, semantic states, display-only metadata.
- [ ] Implement deterministic Page 2 context assembly from frozen game/final/edge/mc/snapshot/profile/context inputs without recalculating probabilities.
- [ ] Run focused tests to GREEN.

### Task 3: War Room presentation
**Files:**
- Create: `nfl_moneyline_page2_war_room_v1.py`
- Test: `tests/test_api2_nfl_moneyline_page2_war_room_v1.py`

**Interfaces:**
- Consumes `build_page2_context` and frozen state.
- Produces `render_selected_matchup(game_id: str) -> None` plus deterministic HTML helpers.

- [ ] Render approved sections: hero, Why Kyre, advantage board, Matchup History + collapsed Full History, game script, availability, recent form, market intelligence, 5M simulation lab, upset radar, final verdict.
- [ ] Use semantic placeholders for missing verified evidence; never fabricate player/status/score data.
- [ ] Add responsive CSS and stable `data-testid` markers for live proof.
- [ ] Run focused tests to GREEN.

### Task 4: V20 selected-game routing and Page-1 navigation
**Files:**
- Create: `nfl_moneyline_hub_v20.py`
- Modify: `universal_runtime_v5_loader_v21.py`
- Test: `tests/test_api2_nfl_moneyline_page2_war_room_v1.py`

**Interfaces:**
- V20 delegates Page 1 to V19 with an injected `VIEW FULL ANALYSIS →` link.
- V20 sends `view=analysis&game=<gid>` to the Page 2 renderer.

- [ ] Implement presentation-only V20 wrapper and exact URL contract.
- [ ] Change only NFL Moneyline loader target V19→V20.
- [ ] Run focused + existing Moneyline regression tests and compile.

### Task 5: Control-plane proof package
**Files:**
- Create: `.github/workflows/api2-nfl-moneyline-page2-war-room-v1.yml`
- Create: `devsystem/runless_proof_plans/api2-nfl-moneyline-page2-war-room-v1.json`
- Create: `devsystem/task_ledgers/api2-nfl-moneyline-page2-war-room-v1.json`

- [ ] Bind exact acceptance tests/compile to one candidate head.
- [ ] Open one protected-main PR, bind one API2 scope lease, obtain Runless `MERGE_AUTHORIZED`, verify App 5204253, merge exact head.

### Task 6: Step 2G dual-main + live Streamlit convergence
**Files:**
- Mirror only Runless-certified feature artifacts to `api2-main` via one sequential PR.
- Create final Step 2G evidence/finalization records through existing control plane.

- [ ] Verify feature-scoped blob parity between `main` and `api2-main`.
- [ ] Use canonical production `?sport=nfl&market=moneyline` Page 1 to discover/select a real upcoming game, then witness `view=analysis&game=<gid>` at ~390px.
- [ ] Require War Room markers including `WHY KYRE LIKES THIS SIDE`, `MATCHUP HISTORY`, `VIEW FULL HISTORY`, `EXPECTED GAME SCRIPT`, `5M SIMULATION LAB`, `RISK / UPSET RADAR`, and final verdict; forbid wrong-sport/runtime-error markers.
- [ ] Durable closeout must return `GREEN_FROZEN` before reporting 100%.
