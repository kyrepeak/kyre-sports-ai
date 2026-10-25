# NBA PRA Page 2 Insights V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a detailed, evidence-backed Insights analyst report to NBA PRA Page 2 without changing frozen projection/provider behavior or adding provider calls.

**Architecture:** A new pure `nba_pra_page2_insights_v1.py` module composes structured narrative sections from already-loaded Page 2 context/model/matchup data. `nba_pra_page2_v1.py` renders those sections immediately after Kyre AI Verdict and before Fast Line Lab. Threshold-dependent text recalculates inside the existing provider-free Line Lab fragment.

**Tech Stack:** Python 3.12, Streamlit, pytest, existing Kyre Sports API Page 2 data contracts.

**Spec:** `docs/superpowers/specs/2026-10-25-nba-pra-page2-insights-v1-design.md`

## Global Constraints

- API 2 only; MONSTER state is not evidence and is not modified.
- One authoritative branch: `api2-nba-pra-page2-insights-v1` from `api2-main@372c4313aaab390c1d8fd7c72de9563dba666f93`.
- One PR and one proof/deployment path; no blind retries or duplicate runs.
- Kyre Sports API remains the only application-facing gateway.
- No SGO / SportsGameOdds / ESPN / ESPN BET.
- No direct provider access from the Insights module.
- Sportsbook projection influence remains exactly `0.0`.
- No sportsbook line averaging or fabricated data.
- Page 1/Page 2 exact handoff, S-tier Page 2, and Line Lab provider-free behavior remain protected.

## Review Focus

- Sparse player/context data must omit unsupported claims instead of inventing them — Task 1 sparse-evidence test.
- Under picks must express probability/edge in the correct direction — Task 1 UNDER final-insight test.
- Exact-opponent history must not accidentally include other opponents — Task 1 matchup-history test.
- Slider threshold changes must not create provider I/O — Task 2 source/fragment test.
- Existing Page 2 hierarchy must keep Insights between Verdict and Line Lab on desktop/mobile — Task 2 integration-order test.

---

### Task 1: Pure NBA PRA Insights evidence composer

**Files:**
- Create: `nba_pra_page2_insights_v1.py`
- Create: `tests/test_api2_nba_pra_page2_insights_v1.py`

**Interfaces:**
- Consumes: `context: Mapping[str, Any]`, `model: Mapping[str, Any]`, `line_result: Mapping[str, Any]`, `matchup: Mapping[str, Any]`, `active_line: float | None`.
- Produces: `build_nba_pra_insights(...) -> dict[str, Any]` with `sections: list[dict[str, str]]`, `final_title: str`, `final_body: str`, and `evidence_count: int`.

- [ ] **Step 1: Write failing rich-evidence test**

Assert rich verified fixtures produce sections titled `RECENT FORM`, `ROLE & USAGE`, `MATCHUP`, `PLAYER VS OPPONENT`, `MARKET & MODEL EDGE`, `AVAILABILITY & RISK`, and `GAME SITUATION`, with concrete PRA/usage/rank/projection/line/history values and a multi-sentence `KYRE FINAL INSIGHT` body.

- [ ] **Step 2: Run RED**

Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_insights_v1.py`
Expected: FAIL because `nba_pra_page2_insights_v1` does not exist.

- [ ] **Step 3: Add sparse/UNDER/history-isolation tests**

Assert missing usage/history/probability does not create those claims, UNDER direction is worded correctly, only exact-opponent games enter matchup history, and no unsupported pace/home-performance claim appears.

- [ ] **Step 4: Implement `build_nba_pra_insights`**

Use only stdlib and supplied mappings. Derive PRA from verified PTS/REB/AST game rows, derive venue from verified home/away tricodes, compose only evidence-backed sentences, and keep final text deterministic.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_insights_v1.py`
Expected: PASS.

### Task 2: Page 2 Insights presentation and regression protection

**Files:**
- Modify: `nba_pra_page2_v1.py`
- Modify: `tests/test_api2_nba_pra_page2_insights_v1.py`
- Create: `.github/workflows/api2-nba-pra-page2-insights-v1.yml`
- Create: `devsystem/execution_plans/api2-nba-pra-page2-insights-v1.json`
- Create: `devsystem/runless_proof_plans/api2-nba-pra-page2-insights-v1.json`
- Create: `devsystem/task_ledgers/api2-nba-pra-page2-insights-v1.json`

**Interfaces:**
- Consumes: Task 1 `build_nba_pra_insights` output.
- Produces: `_insights_html(report: Mapping[str, Any]) -> str` and Page 2 `INSIGHTS` panel located after `KYRE AI VERDICT` and before `FAST LINE LAB`.

- [ ] **Step 1: Write failing integration-order/render test**

Assert rendered Page 2 HTML includes `INSIGHTS`, the detailed section headings, `KYRE FINAL INSIGHT`, and `KYRE AI VERDICT` index < `INSIGHTS` index < `FAST LINE LAB` index.

- [ ] **Step 2: Run RED**

Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_insights_v1.py`
Expected: FAIL because Page 2 does not render Insights.

- [ ] **Step 3: Integrate and style Insights**

Import the pure composer, render section cards and final analyst conclusion, add responsive `.p2-insights-*` CSS, and call the composer only with data already present inside the Line Lab fragment.

- [ ] **Step 4: Run focused GREEN + protected NBA PRA regression lane**

Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_insights_v1.py tests/test_api2_nba_pra_page2_s_tier_v2.py tests/test_api2_nba_pra_page2_source_guard_v2.py tests/test_api2_nba_pra_page1_page2_sync_v1.py tests/test_api2_nba_pra_page2_handoff_repair_r1.py tests/test_api2_nba_pra_page2_runtime_v1.py tests/test_api2_nba_pra_page2_context_v1.py tests/test_api2_nba_pra_page2_integration_v1.py tests/test_api2_nba_pra_page2_line_lab_v1.py tests/test_api2_nba_pra_page2_matchup_v1.py tests/test_api2_nba_pra_gateway_only_v1.py tests/test_api2_nba_pra_model_behavior_v1.py`
Expected: PASS.

Run: `python -m py_compile nba_pra_page2_insights_v1.py nba_pra_page2_v1.py`
Expected: PASS.

- [ ] **Step 5: Exact-head closeout**

Require one terminal CI/proof result on the exact candidate, expected-head merge into `api2-main`, exact merged-head production deployment, stable alias parity, `/health` 200, then freeze/read-back under token `API2_NBA_PRA_PAGE2_INSIGHTS_V1_FROZEN`.
