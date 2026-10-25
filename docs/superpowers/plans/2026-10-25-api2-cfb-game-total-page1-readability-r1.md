# API2 CFB Game Total Page 1 Readability R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CFB Game Total Page 1 materially easier to read on tablet/mobile without changing its structure, analytics, or frozen predecessor modules.

**Architecture:** Add `cfb_game_total_page1_atier_v7.py` as a presentation-only successor. It reuses V6 data/model/card behavior, injects larger CSS for the V5 rail and V6 decision card, and becomes the bootstrap target. V5/V6 remain unchanged.

**Tech Stack:** Python, Streamlit, HTML/CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-25-api2-cfb-game-total-page1-readability-r1-design.md`

## Global Constraints
- API2 only; base `refs/heads/api2-main`.
- One authoritative branch/PR/proof path.
- No model/projection/probability/ranking/selection/provider/API/Page 2 changes.
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- All `MAY_MODIFY_*` boundaries remain false.
- V5/V6 stay untouched.

## Review Focus
- Tablet/mobile CSS must not shrink typography below the new readability floors.
- Long team names must still truncate safely rather than overflow.
- Three primary metrics must remain in the same structure.
- Existing rail horizontal scrolling must remain intact.
- Bootstrap must activate only V7 and retain API2 frozen boundaries.

---

### Task 1: Readability contract

**Files:**
- Create: `tests/test_api2_cfb_game_total_page1_readability_r1.py`

**Interfaces:**
- Consumes: V5/V6 class names and bootstrap import contract.
- Produces: RED assertions for V7 sizing, inheritance, and activation.

- [ ] Write static tests asserting V7 exists, imports V6, defines the approved rail/card scale targets, contains mobile readability floors, retains zero model influence/frozen boundaries, and bootstrap points to V7.
- [ ] Run the test and verify RED because V7/activation do not exist yet.

### Task 2: V7 presentation successor

**Files:**
- Create: `cfb_game_total_page1_atier_v7.py`
- Modify: `cfb_game_total_page1_api_bootstrap_repair_r1.py`

**Interfaces:**
- Consumes: V6 `render_game_total_page1()` and existing V5/V6 CSS class names.
- Produces: V7 render entrypoint and bootstrap activation.

- [ ] Implement V7 as a presentation-only wrapper over V6, applying approved larger CSS targets without changing analytics logic.
- [ ] Advance bootstrap V6 -> V7 and update version text only.
- [ ] Run the new readability test; expect PASS.
- [ ] Run existing CFB Game Total Page 1 decision-card/logo-rail/upcoming/final-polish/activation/source-policy regressions; expect PASS.
- [ ] Run Python compile checks on V7/bootstrap/tests.

### Task 3: Exact-head proof and freeze

**Files:**
- Update API2 proof/freeze authority records only through their dedicated API2 registry refs.

**Interfaces:**
- Consumes: exact PR head and merged `api2-main` SHA.
- Produces: API2-owned GREEN proof and FROZEN checkpoint.

- [ ] Open one PR to `api2-main`.
- [ ] Prove exact PR head with scoped tests/compile and changed-file scope.
- [ ] Merge with expected-head fence.
- [ ] Verify merged `api2-main` provenance.
- [ ] Record/read back API2 frozen checkpoint `API2_CFB_GAME_TOTAL_PAGE1_READABILITY_R1_FROZEN`.