# MONSTER WNBA PRA Page 1 Ultra S-Tier V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved ultra-simple S-tier WNBA PRA Page 1 presentation as a MONSTER-only additive successor without changing certified WNBA data/model behavior.

**Architecture:** Add a presentation-only V2 renderer over the certified Page 1 snapshot. Keep the frozen core and V1 polish byte-identical, preserve the old compatibility assignment for regression contracts, then install V2 before the refresh-handoff import. Gate with a successor source policy and Runless proof plan.

**Tech Stack:** Python, Streamlit, pytest, MONSTER Runless proof controls.

**Spec:** `docs/superpowers/specs/2026-10-26-monster-wnba-pra-page1-ultra-stier-v2-design.md`

## Global Constraints
- MONSTER ONLY; API 2 state/evidence is not proof.
- No provider/network calls from presentation code.
- No projection/probability/edge/qualification/selection math changes.
- No ESPN, ESPN BET, SGO, or Render.
- Frozen Page 1 core and final-polish V1 files remain byte-identical.
- One branch, one PR, one proof lane; classify failure before correction.

## Review Focus
- Missing trend data must disappear rather than show fake/blank analytics.
- Internal model-state strings must never leak into the consumer card.
- Empty certified-pick state must consume no large Page 1 section.
- V2 must install before V3.6.18 captures the renderer reference.
- Existing Page 2 handoff keys and click behavior must remain unchanged.

---

### Task 1: RED acceptance contract

**Files:**
- Create: `tests/test_monster_wnba_pra_page1_ultra_stier_v2.py`

**Interfaces:**
- Consumes: current `wnba_pra_hub_v3612.py`, frozen Page 1 helpers.
- Produces: executable acceptance contract for V2 presentation and integration.

- [ ] Write tests for decision-first card, compact leaderboard, optional verified trends, collapsed empty final section, source safety/frozen-byte boundaries, and compatibility ordering.
- [ ] Run the focused test on the test-only head and observe expected RED because V2 is not installed.
- [ ] Commit the RED contract.

### Task 2: V2 presentation successor

**Files:**
- Create: `wnba_pra_page1_ultra_stier_v2.py`
- Modify: `wnba_pra_hub_v3612.py`

**Interfaces:**
- Consumes: `base.build_player_board_rows`, `base.rank_top_edges`, `base._handoff`, V1 `_face`/`_logo` verified-image helpers.
- Produces: `render_page_snapshot(payload, **kwargs)` and presentation helpers used by acceptance tests.

- [ ] Implement compact hero/slate strip.
- [ ] Implement one Top 3 leaderboard.
- [ ] Implement compact decision-first player cards with optional trends and line movement.
- [ ] Preserve search/sort/status and Page 2 handoff.
- [ ] Collapse Final PRA completely when empty; render premium certified pick when qualified.
- [ ] Install V2 after the preserved V1 assignment and before V3.6.18 import.
- [ ] Run focused tests to GREEN.
- [ ] Run existing WNBA Page 1/final-polish regression tests.

### Task 3: Proof, source policy, and freeze controls

**Files:**
- Create: `devsystem/wnba_pra_page1_ultra_stier_source_policy_v2.py`
- Create: `devsystem/runless_proof_plans/monster-wnba-pra-page1-ultra-stier-v2.json`
- Create: `devsystem/task_ledgers/monster-wnba-pra-page1-ultra-stier-v2.json`

**Interfaces:**
- Consumes: exact V2 files and frozen blob IDs.
- Produces: fail-closed proof contract for `runless-final-gate` and durable GREEN/FROZEN state.

- [ ] Source policy forbids network/provider leakage and asserts V2 integration order.
- [ ] Source policy asserts frozen bytes for Page 1 core and final-polish V1 layers.
- [ ] Proof plan runs focused V2 tests + prior WNBA Page 1 regression + compile + source policy.
- [ ] Task ledger records Step 2A through 2G evidence and terminal state.
- [ ] Open one PR against `monster-main`; require exact-head `runless-final-gate`.
- [ ] Merge only the certified head, then perform Step 2G production convergence/freeze readback.
