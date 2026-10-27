# MONSTER NBA PRA Page 2 V4 CSS Wrapper R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop NBA PRA Page 2 V4 stylesheet rules from rendering as visible text on Streamlit mobile while preserving the frozen V4 presentation and all existing data/model behavior.

**Architecture:** Keep `nba_pra_page2_command_center_v1._css()` as the base stylesheet and place V4 additions inside the same valid `<style>...</style>` envelope. Make no changes to data loading, model math, provider routing, player handoff, line evaluation, or Page 2 HTML hierarchy.

**Tech Stack:** Python 3, Streamlit HTML/CSS rendering, pytest.

**Spec:** Existing frozen V4 design at `docs/superpowers/specs/2026-10-26-monster-nba-pra-page2-s-tier-v4-design.md` plus the production screenshot regression reported on 2026-10-26.

## Global Constraints

- Authority: MONSTER ONLY.
- Presentation-only repair.
- Preserve `MONSTER_NBA_PRA_PAGE2_S_TIER_V4` and every V4 section/marker.
- Sportsbook projection influence remains `0.0`.
- No provider, API gateway, model, projection, line-evaluation, or Page 1 behavior changes.
- One authoritative branch and one PR.
- Production is not GREEN until a real mobile Streamlit browser proves the stylesheet is hidden and V4 content is visible.

## Review Focus

- V4 CSS must remain inside a style element after base V1 CSS composition.
- No duplicate/nested malformed style tags.
- No `.p2v4-*` rule may appear in rendered visible text.
- Existing V4 command-center markers must remain unchanged.
- Existing Page 2 model/provider boundaries must remain untouched.

---

### Task 1: Repair V4 stylesheet composition

**Files:**
- Modify: `nba_pra_page2_command_center_v4.py`
- Create: `tests/test_monster_nba_pra_page2_v4_css_wrapper_r1.py`

**Interfaces:**
- Consumes: `_v1._css() -> str`
- Produces: `_css() -> str` containing one valid stylesheet envelope with both V1 and V4 rules.

- [ ] **Step 1: Write the failing regression test**
  - Assert `_css()` starts with `<style>` and ends with `</style>`.
  - Assert there is exactly one opening and one closing style tag.
  - Assert the V4 marker and `.p2v4-hero` occur before the closing style tag.
  - Assert no non-whitespace content exists after the final closing style tag.

- [ ] **Step 2: Run the regression test and verify RED**
  - Run: `python -m pytest -q tests/test_monster_nba_pra_page2_v4_css_wrapper_r1.py`
  - Expected: FAIL because V4 rules currently occur after the base `</style>`.

- [ ] **Step 3: Implement the minimal composition fix**
  - Keep the V4 CSS body byte-for-byte except for stylesheet-envelope composition.
  - Remove only the base stylesheet's final `</style>` before appending V4 rules, then close the stylesheet exactly once.

- [ ] **Step 4: Verify targeted GREEN**
  - Run: `python -m pytest -q tests/test_monster_nba_pra_page2_v4_css_wrapper_r1.py tests/test_monster_nba_pra_page2_s_tier_v4.py`
  - Expected: all tests pass.

- [ ] **Step 5: Verify syntax and scope**
  - Run: `python -m py_compile nba_pra_page2_command_center_v4.py nba_pra_page2_sync_v1.py`
  - Confirm diff changes no model/provider/data code.
