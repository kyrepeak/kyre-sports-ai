# MONSTER NBA PRA Page 2 S-Tier V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade NBA PRA Page 2 into a compact S-tier decision terminal without changing any model, provider-routing, or verified data behavior.

**Architecture:** Add a presentation-only V4 successor that consumes the existing normalized Page 2 mappings and completeness-aware verified game history. Keep live sync/data/model owners intact and activate V4 only at the renderer import seam. Tests lock presentation hierarchy, anti-fabrication behavior, mobile game-log semantics, and exact preservation of upstream frozen/model code.

**Tech Stack:** Python 3.12, HTML/CSS/SVG string renderer, Streamlit sync shell, pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-monster-nba-pra-page2-s-tier-v4-design.md`

## Global Constraints
- Authority is MONSTER ONLY.
- Kyre Sports API remains the only application-facing gateway.
- No SGO, ESPN, or ESPN BET.
- No projection-math/provider-routing changes.
- No fabricated values.
- Preserve repaired Page 2 history/role/availability behavior.
- Mobile must avoid horizontally clipped game-log data.

## Review Focus
- Missing logos/photos/usage/availability must degrade semantically, not fabricate.
- One-book markets must not pretend consensus exists.
- Sparse game history must produce a valid chart/empty state without fake L10 samples.
- Active-line changes must update only presentation/evaluate-line output with zero provider fetches in the fragment.
- Mobile game log must expose all core row values without relying on horizontal table scrolling.

---

### Task 1: RED acceptance contract
**Files:**
- Create: `tests/test_monster_nba_pra_page2_s_tier_v4.py`
- Create: `.github/workflows/monster-nba-pra-page2-s-tier-v4.yml`

**Interfaces:**
- Consumes: existing Page 2 context/model/result/matchup dictionaries.
- Produces: a failing contract for `nba_pra_page2_command_center_v4.py` and V4 sync activation.

- [ ] Write tests that require V4 identity, hierarchy, L10 threshold chart, distribution visual, model drivers, compact Kyre Read, mobile game cards, no provider access, and live-sync V4 import.
- [ ] Open the single authoritative PR and observe the workflow fail because V4 is absent/not activated.

### Task 2: V4 presentation successor
**Files:**
- Create: `nba_pra_page2_command_center_v4.py`
- Modify: `nba_pra_page2_sync_v1.py`

**Interfaces:**
- Consumes: normalized `context`, `model`, `line_result`, `matchup`, `active_line`.
- Produces: `_css() -> str`, `build_page2_html(...) -> str`.

- [ ] Implement V4 with no I/O/provider imports.
- [ ] Preserve completeness-aware verified history and role/availability semantics.
- [ ] Activate V4 in sync only.
- [ ] Run focused acceptance + existing Page 2 regressions GREEN.

### Task 3: Proof and Runless gate
**Files:**
- Create: `devsystem/runless_proof_plans/monster-nba-pra-page2-s-tier-v4.json`

- [ ] Compile V1-V4 + sync.
- [ ] Prove focused Page 2 regressions GREEN.
- [ ] Prove no provider fetch inside slider fragment.
- [ ] Prove source scope is Page 2 presentation only.
- [ ] Obtain Runless `MERGE_AUTHORIZED` proof for exact candidate head.

### Task 4: Protected merge + Step 2G production proof
- [ ] Merge the one authoritative PR with expected exact head.
- [ ] Verify protected `main` contains the candidate tree/changes.
- [ ] Verify production Streamlit path serves the redesigned Page 2 when selected through the NBA PRA board.
- [ ] Record MONSTER-only Step 2G checkpoint with exact SHA/tree, proof receipt, production identity, and deterministic digest.
- [ ] Read the checkpoint back independently and require `MONSTER_ONLY`, `FROZEN`, and zero foreign/API2 evidence before declaring 100% GREEN + FROZEN.
