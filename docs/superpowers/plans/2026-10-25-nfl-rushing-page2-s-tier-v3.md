# NFL Rushing Yards Page 2 S-Tier V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a premium mobile-first NFL Rushing Yards Page 2 analyst cockpit without changing Kyre projection math or sportsbook/provider ownership.

**Architecture:** Add a presentation-only `nfl_rushing_yards_professional_v3.py` successor that consumes the existing Kyre Sports API detail payload. Preserve V2 byte-for-byte and switch the compatibility owner in V1 to activate V3. All new charts, hit rates, insights, and summary states are deterministic derivatives of the existing verified payload.

**Tech Stack:** Python 3.13, Streamlit, server-rendered HTML/CSS, pytest, Kyre Sports API detail gateway.

**Spec:** `docs/superpowers/specs/2026-10-25-nfl-rushing-page2-s-tier-v3-design.md`

## Global Constraints
- Kyre Sports API remains the only application-facing data gateway.
- No direct provider calls from Page 2 renderer.
- No ESPN, ESPN BET, or SGO.
- No change to frozen NFL Rushing market reliability logic or Kyre projection formulas.
- No fabricated line, probability, edge, injury, personnel, weather, trench, spread, total, or history values.
- V2 stays preserved; V1 activates V3.

## Review Focus
- Verified line present vs absent: only verified lines may drive hit rates, edge/probability presentation, and performance reference line.
- Sparse recent history: chart and matrix must degrade to truthful compact states without division-by-zero or fake samples.
- Mobile width: semantic values must wrap and the floating top control must not obscure cards.
- Duplicate metrics: advanced efficiency must not repeat workload cards; source lineage must be collapsed.
- Existing Page 1/market routing: redesign must not import or alter sportsbook collectors, data-truth routing, or Page 1 ranking.

---

### Task 1: Lock V3 presentation contract

**Files:**
- Create: `tests/test_api2_nfl_rushing_page2_s_tier_v3.py`
- Create: `.github/workflows/api2-nfl-rushing-page2-s-tier-v3.yml`

**Interfaces:**
- Consumes: `nfl_rushing_yards_professional_v1.build_rushing_detail_html(detail)`
- Produces: an executable acceptance contract for V3 activation and S-tier section behavior.

- [ ] **Step 1:** Add failing tests asserting V1 imports V3, V2 remains preserved, all named S-tier sections render, source lineage uses `<details>`, mobile CSS does not ellipsize `.kry3value`, and no banned provider tokens appear.
- [ ] **Step 2:** Add fixture tests for verified market and no-market states; assert hit-rate/chart content appears only with a verified line and semantic pending copy otherwise.
- [ ] **Step 3:** Run the focused V3 test and confirm RED before implementation.

### Task 2: Implement presentation successor

**Files:**
- Create: `nfl_rushing_yards_professional_v3.py`
- Modify: `nfl_rushing_yards_professional_v1.py`

**Interfaces:**
- Consumes: `load_rushing_yards_detail(player_key, *, game_id=None)` and existing Page 2 detail mapping.
- Produces: `CSS`, `MODEL_VERSION`, `build_rushing_detail_html(detail) -> str`, and `render_page2(...)` compatible with V1's existing public surface.

- [ ] **Step 1:** Implement pure helpers for recent rows, hit-rate slices, insight bullets, semantic state, chart bars, compact metrics, history rows, and collapsed sources.
- [ ] **Step 2:** Implement the S-tier layout in the exact section order defined by the spec.
- [ ] **Step 3:** Preserve fail-closed market semantics: no fake edge/probability/hit-rate values when market line is unverified.
- [ ] **Step 4:** Update V1 to activate V3 while retaining the hidden legacy compatibility section index.
- [ ] **Step 5:** Run V3 tests and make them GREEN.

### Task 3: Regression protection + proof plan

**Files:**
- Create: `devsystem/runless_proof_plans/api2-nfl-rushing-page2-s-tier-v3.json`
- Create: `devsystem/task_ledgers/api2-nfl-rushing-page2-s-tier-v3.json`
- Modify: `.github/workflows/api2-nfl-rushing-page2-s-tier-v3.yml`

**Interfaces:**
- Consumes: V3 acceptance tests and existing NFL Rushing Page 1/market-reliability tests.
- Produces: one Runless exact-head proof/freeze path.

- [ ] **Step 1:** Bind focused tests for V3, V2 command center continuity, Page 1 RB grid, and NFL rushing market reliability.
- [ ] **Step 2:** Compile V1/V2/V3 and the existing detail gateway in the proof commands.
- [ ] **Step 3:** Lock one task ID, authorization ID, lease ID, freeze token, source-main SHA, artifact list and dependencies.
- [ ] **Step 4:** Run exact-head CI, then one Runless final gate.
- [ ] **Step 5:** Merge exact certified head, verify production deployment/readback, forward-port API2 frozen registry, close durable Runless state to GREEN_FROZEN, and release the API2 scope lease.
