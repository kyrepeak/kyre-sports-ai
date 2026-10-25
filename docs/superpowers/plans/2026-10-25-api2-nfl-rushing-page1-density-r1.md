# API2 NFL Rushing Page 1 Density R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NFL Rushing Yards Page 1 substantially shorter and easier to scan on mobile while preserving all data, Page 2 behavior, and frozen analytics boundaries.

**Architecture:** Add `nfl_rushing_yards_simple_rb_grid_v2.py` as a presentation-only successor over V1 helpers/data. Add `streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py` to shadow only NFL/Rushing Yards to V2, then advance `app.py` to that terminal. Frozen V1 and Page 2 remain untouched.

**Tech Stack:** Python, Streamlit, HTML/CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-25-api2-nfl-rushing-page1-density-r1-design.md`

## Global Constraints
- API2 only; base `refs/heads/api2-main` exact source `4c79978bab5d11455dada42f7949d6978c2dc099`.
- One authoritative branch/PR/proof path: `api2-nfl-rushing-page1-density-r1`.
- Step 2A, Anti-Loop, Step 2B, and Step 2C are mandatory.
- No Page 2/model/projection/probability/ranking/RB-role/provider/API changes.
- No SGO / ESPN / ESPN BET.
- No fabricated line, edge, probability, or null-to-zero conversion.
- Frozen V1 stays untouched.

## Review Focus
- Pending cards must have zero repeated `WAIT` values and one concise pending message.
- Verified-market cards must still show sportsbook line, edge, model side, probability/confidence, and projection.
- Mobile CSS must remain one compact three-cell decision strip rather than reverting to a 2x2 grid.
- Full Analysis query parameters must still bind player/game/date to Page 2.
- Terminal overlay must shadow only NFL/Rushing Yards and delegate all other routes to the prior terminal.

---

### Task 1: RED density contract

**Files:**
- Create: `tests/test_api2_nfl_rushing_page1_density_r1.py`

**Interfaces:**
- Consumes: frozen V1 card/data contract and prior terminal route contract.
- Produces: RED assertions for V2 card hierarchy, pending semantics, and route activation.

- [ ] Write tests for projection hero, three-cell decision strip, zero repeated `WAIT`, one pending message, supporting rail, Full Analysis handoff, V2 terminal shadowing, upcoming-only copy, and forbidden-provider absence.
- [ ] Run exact focused test/proof and verify RED because V2/terminal activation do not exist yet.

### Task 2: V2 presentation successor

**Files:**
- Create: `nfl_rushing_yards_simple_rb_grid_v2.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py`
- Modify: `app.py`

**Interfaces:**
- Consumes: V1 slate loader/helpers/card values and prior terminal runtime.
- Produces: compact Page 1 V2 renderer and NFL-only terminal activation.

- [ ] Implement V2 projection hero + MARKET/EDGE/MODEL strip + one quick-stat rail.
- [ ] Preserve exact Page 2 query handoff and upcoming-only board behavior.
- [ ] Add terminal overlay that changes only `nfl/rushing-yards`.
- [ ] Advance `app.py` to the new terminal and preserve all unrelated ancestry markers.
- [ ] Run focused density test; expect PASS.
- [ ] Run existing NFL Rushing Page 1/Page 2/source-policy regressions; expect PASS.
- [ ] Run Python compile checks on changed Python files.

### Task 3: Exact-head proof and freeze

**Files:**
- Create/update API2 execution plan, proof plan, task ledger, proof/freeze registry records through their dedicated API2 authority paths.

**Interfaces:**
- Consumes: exact PR head and merged `api2-main` SHA.
- Produces: API2-owned GREEN proof and FROZEN checkpoint.

- [ ] Open exactly one PR to `api2-main`.
- [ ] Prove exact PR head through the existing Runless V2 transport; do not create a parallel proof.
- [ ] Require exact-head final gate / merge authority.
- [ ] Merge with expected-head fence.
- [ ] Verify merged `api2-main` provenance.
- [ ] Record and read back `API2_NFL_RUSHING_PAGE1_DENSITY_R1_FROZEN`.
