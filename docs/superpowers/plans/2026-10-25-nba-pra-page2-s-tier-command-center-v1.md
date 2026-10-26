# NBA PRA Page 2 S-Tier Command Center V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the live NBA PRA Page 2 card-stack presentation with the approved visual analytics command center while preserving all frozen model, provider, Insights, and Line Lab behavior.

**Architecture:** Add a pure presentation successor module that consumes the exact existing Page 2 context/model/result/matchup mappings and performs no I/O. Activate it only through `nba_pra_page2_sync_v1.py`; keep the frozen `nba_pra_page2_v1.py`, `nba_pra_page2_core_v2.py`, and `nba_pra_page2_insights_v1.py` byte-identical.

**Tech Stack:** Python 3.12, Streamlit, server-rendered HTML/CSS/SVG, pytest, Runless V2 proof authority.

**Spec:** `docs/superpowers/specs/2026-10-25-nba-pra-page2-s-tier-command-center-v1-design.md`

## Global Constraints
- API 2 only. MONSTER state is never evidence or authority.
- Kyre Sports API remains the only application-facing gateway. Do not add SGO, ESPN, or ESPN BET.
- Sportsbook projection influence remains `0.0`.
- No new external provider calls.
- No synthetic PTS/REB/AST projections; only verified recent-history component composition may be shown.
- No averaging of conflicting sportsbook lines.
- Line Lab must remain local threshold re-evaluation with zero external fetches per slider move.
- Frozen prior Page 2 artifacts must remain byte-identical.
- One authoritative branch/PR/proof/freeze path only.

## Review Focus
- Sparse history: charts fail closed without invented games or fake component values.
- Missing sigma: distribution renders an explicit unavailable state rather than a fabricated curve.
- Multiple sportsbook quotes: every quote remains independent; no consensus averaging.
- Missing usage/injury/history: evidence is summarized as compact data gaps instead of large empty cards.
- Mobile/tablet width: charts/cards collapse cleanly without horizontal overflow.

---

### Task 1: Command-center presentation contract

**Files:**
- Create: `tests/test_api2_nba_pra_page2_command_center_v1.py`
- Create: `nba_pra_page2_command_center_v1.py`

**Interfaces:**
- Consumes: `context: Mapping[str, Any]`, `model: Mapping[str, Any]`, `line_result: Mapping[str, Any]`, `matchup: Mapping[str, Any]`, `active_line: float | None`.
- Produces: `build_page2_html(...) -> str` and `_css() -> str` for the live sync renderer.

- [ ] **Step 1: Write failing tests**
  - Assert hierarchy includes `PLAYER COMMAND CENTER`, `PROJECTION DISTRIBUTION`, `KYRE INSIGHTS`, `RECENT PERFORMANCE`, `VERIFIED PRA COMPOSITION`, `MATCHUP INTELLIGENCE`, `MARKET INTELLIGENCE`, `RISK & EVIDENCE QUALITY`, `FULL GAME LOG` in order.
  - Assert legacy duplicate HTML panels `KYRE AI VERDICT` and `FAST LINE LAB` are absent from the successor HTML.
  - Assert distribution SVG uses verified `projection` and `sigma`, and shows the active threshold separately.
  - Assert recent-performance chart renders only verified game rows and a threshold marker.
  - Assert PTS/REB/AST display is labeled `VERIFIED PRA COMPOSITION`, not component projection.
  - Assert matchup ranks render as 1-to-30 visual bars.
  - Assert multiple sportsbook quotes remain separate and no `CONSENSUS LINE` is emitted.
  - Assert sparse/unverified data creates compact `DATA GAPS` output and never invents usage/injury/history.
  - Assert mobile CSS contains a <=760px single-column contract.

- [ ] **Step 2: Run focused test and verify RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_command_center_v1.py`
  - Expected: FAIL because `nba_pra_page2_command_center_v1` does not exist.

- [ ] **Step 3: Implement pure presentation module**
  - Build hero with player identity, matchup, lean, threshold, projection, side probability, edge, score/tier, book line, and evidence coverage.
  - Build SVG projection distribution only when projection + sigma are verified.
  - Build SVG recent PRA chart from verified `current_games` or `prior_games`.
  - Build verified PTS/REB/AST composition from the same verified history sample.
  - Build rank bars from verified opponent ranks.
  - Build independent sportsbook quote rows and selected-vs-current movement context.
  - Reuse `build_nba_pra_insights` for the written analyst layer.
  - Build compact role/availability/history/data-gap and risk sections.
  - Build full game log with active-line result recalculation.
  - No network imports or provider calls.

- [ ] **Step 4: Run focused test and verify GREEN**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_command_center_v1.py`
  - Expected: all tests pass.

### Task 2: Live sync activation + frozen regression protection

**Files:**
- Modify: `nba_pra_page2_sync_v1.py`
- Create: `tests/test_api2_nba_pra_page2_command_center_activation_v1.py`

**Interfaces:**
- Consumes: Task 1 `build_page2_html` and `_css`.
- Produces: live Streamlit Page 2 rendering through the command-center module while leaving model/default-line ownership on frozen Page 2 V1.

- [ ] **Step 1: Write failing activation tests**
  - Assert sync imports presentation HTML/CSS from `nba_pra_page2_command_center_v1`.
  - Assert `_baseline_model` and `default_line_for_context` still come from frozen `nba_pra_page2_v1`.
  - Assert the Line Lab fragment still contains local `evaluate_line(...)` and no snapshot/matchup provider fetch.
  - Assert Git blob hashes for frozen `nba_pra_page2_v1.py`, `nba_pra_page2_core_v2.py`, and `nba_pra_page2_insights_v1.py` remain `799a1711fa4f7818c6c09a9f8c422f960b434c48`, `0176f6238da73e9b5f73d6f31e083e05948dd48e`, and `f1b09aed0a8c10ad94d97f3a167c06f8a6eb15bb` respectively.

- [ ] **Step 2: Run activation test and verify RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_command_center_activation_v1.py`
  - Expected: FAIL because sync still imports presentation from `nba_pra_page2_v1`.

- [ ] **Step 3: Change one sync import boundary**
  - Keep `_baseline_model` and `default_line_for_context` imported from frozen `nba_pra_page2_v1`.
  - Import `_css` and `build_page2_html` from `nba_pra_page2_command_center_v1`.
  - Do not change fetch/load/evaluate behavior.

- [ ] **Step 4: Run activation test and verify GREEN**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nba_pra_page2_command_center_activation_v1.py`
  - Expected: all tests pass.

### Task 3: Full regression and protected-main proof lane

**Files:**
- Create: `.github/workflows/api2-nba-pra-page2-command-center-v1.yml`
- Create: `devsystem/runless_proof_plans/api2-nba-pra-page2-command-center-v1.json`
- Create: `devsystem/task_ledgers/api2-nba-pra-page2-command-center-v1.json`

**Interfaces:**
- Consumes: Tasks 1-2 implementation and the existing API2-isolated Runless authority.
- Produces: exact-head focused CI, protected-main Runless proof, merge authorization, and freeze identity.

- [ ] **Step 1: Run full focused regression locally/CI**
  - `tests/test_api2_nba_pra_page2_command_center_v1.py`
  - `tests/test_api2_nba_pra_page2_command_center_activation_v1.py`
  - `tests/test_api2_nba_pra_page2_insights_v1.py`
  - `tests/test_api2_nba_pra_page2_s_tier_v2.py`
  - `tests/test_api2_nba_pra_page2_ui_v1.py`
  - `tests/test_api2_nba_pra_page2_source_guard_v2.py`
  - `tests/test_api2_nba_pra_page1_page2_sync_v1.py`
  - `tests/test_api2_nba_pra_page2_integration_v1.py`
  - Compile command-center + sync modules.

- [ ] **Step 2: Add one PR workflow for the same focused suite**
  - Trigger only on the Page 2 command-center files/control artifacts.
  - No GitHub Actions fallback for Runless final authority.

- [ ] **Step 3: Add exact Runless proof plan and task ledger**
  - Workstream/task: `api2-nba-pra-page2-command-center-v1`.
  - Freeze token: `API2_NBA_PRA_PAGE2_S_TIER_COMMAND_CENTER_V1_FROZEN`.
  - Required check: `runless-final-gate`, App ID `5204253`.
  - Source main SHA: the exact protected-main base at branch creation.
  - Artifacts include only the command-center module, sync activation, tests, workflow, proof plan, task ledger, design, and plan.

- [ ] **Step 4: Exact-head verification before merge**
  - Focused CI successful.
  - Runless proof successful and bound to exact PR head.
  - Frozen baseline blobs unchanged.
  - API2 authority only; no MONSTER authority/state.

- [ ] **Step 5: Expected-head merge and readback**
  - Merge only with exact expected PR head SHA.
  - Verify protected `main` equals merge SHA and candidate->merge artifact content is unchanged.

- [ ] **Step 6: Freeze + durable closeout**
  - Add/read back exact freeze record in API2 live-main frozen registry.
  - Close Runless proof to `GREEN_FROZEN` with exact candidate SHA, merge SHA, freeze token, proof digest, and registry state hash.
  - Final readback must show `GREEN_FROZEN`, failure class `NONE`, and the exact freeze token.
