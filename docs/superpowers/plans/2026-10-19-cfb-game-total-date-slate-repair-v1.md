# CFB Game Total Date + Slate Repair V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore truthful next-active-slate discovery and exact selected-game handoff on the Universal Runtime V5 CFB Game Total route.

**Architecture:** Add a V5-only repair layer instead of rewriting frozen Game Total pages. The repair reuses the certified Daily Slate router context so an empty hosted primary is cross-checked against the existing ESPN FBS/FCS fallback, and it upgrades Page-1 game links to include canonical `sport/market/date/game_id` alongside the legacy Game Total keys. A new additive Runtime V5 loader/terminal overlay routes only `cfb/game-total` through this repair and delegates every other route unchanged.

**Tech Stack:** Python, Streamlit, Universal Runtime V5, existing CFB Daily Slate fallback, pytest, Runless proof/finalization.

**Spec:** Current user request in API 2: Game Total must show the real next CFB slate, all actual games must render, and tapping a game must open that exact matchup.

## Global Constraints

- One authoritative API 2 workstream/branch/PR/proof path only.
- Preserve all frozen model/projection/probability/ranking/selection behavior.
- Sportsbook projection influence remains 0.0%.
- Reuse existing ESPN FBS/FCS runtime fallback; do not create a duplicate schedule provider stack.
- Selected-game Page 2 remains owned by the existing frozen Page-2 route.
- No other sport or CFB market may change.

## Review Focus

- Hosted primary returns HTTP 200 with zero games while ESPN has games: fallback must win.
- Phoenix day has no games: bounded resolver must continue to the next date with games.
- Page-1 link must preserve exact event identity through Universal Runtime V5 canonical parameters.
- Selected `game_id` must route to Page 2, while no selected game must route to Page 1.
- Legacy Game Total query keys must remain present for frozen downstream compatibility.

---

### Task 1: Lock regression contract

**Files:**
- Create: `tests/test_api2_cfb_game_total_v5_date_slate_repair_v1.py`

- [ ] Write failing tests for V21/V5 route ownership, canonical game links, selected-game identity, and use of the certified Daily Slate fallback context.
- [ ] Run the focused test and confirm RED because the new repair modules do not exist.

### Task 2: Implement bounded V5 Game Total repair

**Files:**
- Create: `cfb_game_total_v5_date_slate_repair_v1.py`
- Create: `universal_runtime_v5_loader_v21.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_cfb_gt_v5.py`
- Modify: `app.py`

- [ ] Implement canonical+legacy `View Game` URLs with exact `game_id` and selected Phoenix date.
- [ ] Install the existing `install_daily_slate_page1()` context for unselected Page 1 only.
- [ ] Route selected `game_id` directly to existing Page 2 unchanged.
- [ ] Delegate every route except `cfb/game-total` to loader V20.
- [ ] Advance only the production loader handoff through an additive terminal overlay.
- [ ] Run focused tests to GREEN.

### Task 3: Full regression and proof

**Files:**
- Create: `devsystem/runless_proof_plans/api2-cfb-game-total-date-slate-repair-v1.json`

- [ ] Run Game Total Page-1 fallback/date/filter/handoff tests plus Page-2 selected-game tests.
- [ ] Run Universal Runtime V5 navigation certification.
- [ ] Verify live ESPN data for the current next slate returns concrete games and IDs.
- [ ] Open one authoritative PR, exact-head Runless proof, merge, merged-main verification, registry forward-port, immutable freeze record/read-back, and lease release.
