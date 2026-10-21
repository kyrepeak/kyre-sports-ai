# NBA PRA Page 1 S-Tier UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade NBA PRA Page 1 into a premium analytics command center while preserving the working PRA pipeline and enforcing the API 2 rule that Page 1 uses only Kyre Sports API, never SGO.

**Architecture:** Keep `nba_pra_page1_v2.py` as the page orchestrator and `nba_pra_page1_ui_v2.py` as the presentation layer. Preserve sportsbook identity/line/price/timestamp per quote. Route market data through `nba_pra_market_api_v1.py` -> Kyre Sports API only; remove Page 1 SGO credential/fallback behavior and remove SGO from diagnostics. Keep approved source routing behind the Kyre API rather than calling every source from the page.

**Tech Stack:** Python, Streamlit, FastAPI/Vercel transport, pytest.

**Spec:** Approved in chat: S-tier Page 1 command center, team logos, player face IDs/headshots, Edge Score/tier, slate navigator, market KPIs, compact analytics cards, and NBA multi-source routing rule.

## Global Constraints

- API 2 never uses SGO for this NBA PRA Page 1 path; Page 1 calls Kyre Sports API only.
- Do not average conflicting sportsbook lines. Preserve sportsbook, line, odds/price, and timestamp.
- Do not fabricate or guess missing data.
- Sportsbook projection influence stays exactly `0.0`.
- Preserve the already-working next-slate and market-card behavior.
- One authoritative branch/PR/run lane only.

## Review Focus

- Missing headshot still renders a stable professional fallback and team logo.
- Missing model projection does not fabricate Edge Score/probability.
- Multiple sportsbook quotes remain separate and never averaged.
- API-only transport request contains no SGO credential field.
- Existing all-markets rendering still works when BEST EDGES is empty.

---

### Task 1: Pin the S-tier UI contract and API-only routing

**Files:**
- Modify: `tests/test_api2_nba_pra_page1_v2_ui_contract.py`
- Modify: `tests/test_api2_nba_pra_page1_provider_transport_hardening_v1.py`

**Interfaces:**
- Consumes: `build_player_card_html`, `source_diagnostic_summary`, `load_kyre_sports_api_pra_observations`.
- Produces: failing tests for player team logo + Edge Score/tier, API-only diagnostics, and credential-free API request.

- [ ] **Step 1:** Add failing assertions for team logo, Kyre Edge Score/tier, API-only diagnostics, and no SGO request field.
- [ ] **Step 2:** Run focused tests and verify RED for the new behavior.

### Task 2: Implement the premium analytics presentation

**Files:**
- Modify: `nba_pra_page1_ui_v2.py`
- Modify: `nba_pra_page1_v2.py`

**Interfaces:**
- Consumes: existing player/item/model/grade structures.
- Produces: team-logo + headshot identity row, Kyre Edge Score/tier, stronger visual hierarchy, and Kyre-API-only diagnostics.

- [ ] **Step 1:** Implement the minimal UI helpers and markup required by Task 1 tests.
- [ ] **Step 2:** Run focused UI tests and verify GREEN.

### Task 3: Enforce Kyre Sports API-only Page 1 market transport

**Files:**
- Modify: `nba_pra_market_api_v1.py`
- Modify: `nba_pra_page1_data_v2.py`
- Modify: `runless_v2/nba_pra_market_v1.py`

**Interfaces:**
- Consumes: slate date and Kyre Sports API endpoint.
- Produces: credential-free Page 1 API request and no SGO fallback in the Kyre NBA PRA endpoint.

- [ ] **Step 1:** Remove the SGO credential from the Streamlit client request contract and Page 1 loader.
- [ ] **Step 2:** Remove SGO fallback execution from the NBA PRA Vercel endpoint while retaining FanDuel-first legitimate market collection.
- [ ] **Step 3:** Run provider/transport tests and verify GREEN.

### Task 4: Regression proof and closeout

**Files:**
- Modify only proof/freeze metadata if required by the repository's existing Runless gate.

- [ ] **Step 1:** Run the NBA PRA regression suite, provider/transport gate, navigation gate, and compile/static checks through the authoritative CI lane.
- [ ] **Step 2:** Confirm exact branch head is up to date with `main` and `runless-final-gate` is SUCCESS.
- [ ] **Step 3:** Merge by expected head SHA, verify merged main, and stop. No duplicate PR/run/deploy.
