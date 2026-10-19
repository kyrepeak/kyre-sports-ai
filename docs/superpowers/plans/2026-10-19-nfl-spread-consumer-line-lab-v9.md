# NFL Spread Consumer Line Lab V9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the engineering-first NFL Spread screen with a consumer-first matchup page whose centerpiece is an interactive spread Line Lab.

**Architecture:** Preserve NFL Spread V8/V3/V1 analytical ownership and Kyre Sports API sportsbook transport. V9 directly composes the frozen slate, market and certified 5M Monte Carlo outputs into a new consumer surface; Line Lab re-grades the already-certified margin distribution at any selected spread without rerunning or changing the football model.

**Tech Stack:** Python, Streamlit, pandas, existing NFL Spread V1/V3/V8 modules, Universal Runtime V5, pytest.

**Spec:** Approved chat design on 2026-10-19: matchup hero → market/model summary → Line Lab → cover probability → why/model context → line movement/history → compact availability → collapsed diagnostics.

## Global Constraints

- One active workstream / branch / PR / Runless proof chain.
- Spread slider range: -30.5 through +30.5 in 0.5-point increments, no text/keyboard input.
- Line Lab is settlement/regrading only; sportsbook projection influence remains exactly 0.0%.
- Existing model, calibration, certified 5M Monte Carlo distribution, market transport, ranking/stake/wager rules remain frozen.
- No visible manual date picker; use verified current/next NFL slate resolution.
- Mobile/tablet uses one-column consumer flow; advanced engineering evidence stays collapsed.

## Review Focus

- Half-point vs whole-number line settlement and push handling.
- Missing/stale sportsbook line: model stays visible, market comparison fails closed.
- Empty/no-game date: automatic next verified NFL slate, no fake game.
- Missing history or injury detail: hide/compact gracefully, no fabricated data.
- Slider interaction must not rerun the 5M model or alter model fair spread.

---

### Task 1: Pure Line Lab re-grader

**Files:**
- Create: `nfl_spread_line_lab_v1.py`
- Test: `tests/test_nfl_spread_consumer_line_lab_v9.py`

**Interfaces:**
- Consumes: `analytics["margin_distribution"]`, selected away spread, optional American price.
- Produces: `settle_line(analytics, away_spread, price=None) -> dict` with away/home cover, push, non-push cover, break-even, probability edge and immutable projected margin.

- [ ] Write tests for half-point, whole-number push, invalid/missing distribution, and model-output invariance.
- [ ] Run tests and confirm RED because module/function does not exist.
- [ ] Implement minimal pure re-grader over the saved certified margin distribution.
- [ ] Run tests and confirm GREEN.

### Task 2: Consumer-first Spread V9 surface

**Files:**
- Create: `nfl_spread_hub_v9.py`
- Test: `tests/test_nfl_spread_consumer_line_lab_v9.py`

**Interfaces:**
- Consumes: V8 smart-slate resolver, V1 verified schedule/market transport, V3 frozen analytics, V8 history loader.
- Produces: `render_nfl_hub("Spread")` with one matchup-first page and per-game Line Lab.

- [ ] Add RED source/render contract: no visible `st.date_input`, Line Lab uses `st.slider`, 0.5 step and ±30.5 range, Advanced Diagnostics collapsed, no Step 1/2/3/4 engineering copy.
- [ ] Implement the compact hero, market-vs-model summary, Line Lab, cover probability, explanation/context cards, history, availability summary and collapsed diagnostics.
- [ ] Verify model/MC/market functions are reused, not replaced.
- [ ] Run focused V8/V7/V4/V3 regression tests plus new V9 tests.

### Task 3: Activate Universal Runtime V5 only for NFL Spread

**Files:**
- Modify: `universal_runtime_v5_loader_v21.py`
- Test: `tests/test_nfl_spread_consumer_line_lab_v9.py`

**Interfaces:**
- Produces: NFL/Spread destination source version `nfl_spread_hub_v9`; all other routes delegate unchanged.

- [ ] Add RED route assertion for NFL/Spread → V9.
- [ ] Add the minimal V21 override using existing `_nfl_adapter`.
- [ ] Run Streamlit AppTest on `?sport=nfl&market=spread` and verify no exception, no visible date input, Line Lab slider present, and legacy step console absent.

### Task 4: Runless proof and freeze

**Files:**
- Create: `devsystem/runless_proof_plans/monster-nfl-spread-consumer-line-lab-v9.json`

- [ ] Compile changed Python files and run exact focused regression suite.
- [ ] Open exactly one PR.
- [ ] Request exactly one exact-head Runless proof and require `MERGE_AUTHORIZED` / `failure_class=NONE` plus `runless-final-gate` success.
- [ ] Merge with exact-head protection.
- [ ] Re-run the real NFL/Spread AppTest from merged main.
- [ ] Append/read back the immutable finalization record + manifest, close out Runless to `GREEN_FROZEN`, release scope lease, verify zero active workstream leases.
