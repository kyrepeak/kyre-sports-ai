# CFB Game Total Page1 V2 Step5 Pace & Expected Possessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Certify and freeze the already-live multi-source Step 5 Pace & Expected Possessions surface on the current Page1 V2 V38 route without modifying product runtime.

**Architecture:** Reuse the existing `cfb_game_total_step5_pace_v1.py` engine and its V17 presentation hook. Prove by source graph that current V38 transitively preserves V17, prove the Step4 public repair does not replace the Step5 evidence seam, then use one Runless exact-head proof and atomic closeout to register the checkpoint as frozen.

**Tech Stack:** Python, pytest, Streamlit source graph, Runless Proof Plane, MONSTER frozen registry.

**Spec:** Current API2 9-step Page1 V2 plan; Step 5 = Pace & Expected Possessions.

## Global Constraints

- Exact source main: `53c4bf0aa194befe56934d476f0f1a1a22d3d40d`.
- Frozen registry baseline: revision 205 / `5608b396896c3a1aa5c5f3eae815c8f22141a1d4110593baa1f02ee640a5189b`.
- No product-runtime mutations.
- Preserve all Step 1-4 frozen artifacts and all unrelated thaws.
- Reuse NCAA + SportsDataverse/cfbfastR + Punt & Rally evidence; ESPN remains last-resort only.
- Sportsbook projection influence remains `0.0`.
- One authoritative branch, PR, Runless proof, merge, and closeout chain.
- GitHub Actions fallback = 0.

## Review Focus

- V38 must still reach the V17 Step5 presentation owner through its current ancestor graph.
- The Step4 public-repair layer must not replace `_step_evidence_html`.
- Step5 must keep SportsDataverse primary / ESPN last-resort behavior.
- Existing Step5 must fail closed to CHECK/DATA LIMITED when evidence is incomplete.
- The certification branch must contain control-plane/test artifacts only; no product runtime diffs.

---

### Task 1: Characterize the live Step5 inheritance

**Files:**
- Create: `tests/test_cfb_game_total_page1_v2_step5_pace_possessions_v1.py`
- Read only: `cfb_game_total_step5_pace_v1.py`
- Read only: `cfb_game_total_clean_page_v17.py`
- Read only: `cfb_game_total_clean_page_v38.py`
- Read only: `cfb_game_total_page1_v2_step4_public_repair_v1.py`

**Interfaces:**
- Consumes: current Page1 V2 V38 route and existing V17 Step5 owner.
- Produces: an exact source-level certification that no new product implementation is required.

- [ ] **Step 1: Write the certification test first.**
- [ ] **Step 2: Run the test and confirm the control-plane contract is RED because Step5 task metadata does not yet exist.**
- [ ] **Step 3: Add the Step5 execution plan, Runless proof plan, and task ledger.**
- [ ] **Step 4: Run the focused Step5 certification and the existing V168 Step5 suite; require GREEN.**

### Task 2: Runless exact-head certification and atomic closeout

**Files:**
- Create: `devsystem/execution_plans/cfb-game-total-page1-v2-step5-pace-possessions.json`
- Create: `devsystem/runless_proof_plans/cfb-game-total-page1-v2-step5-pace-possessions.json`
- Create: `devsystem/task_ledgers/cfb-game-total-page1-v2-step5-pace-possessions.json`

**Interfaces:**
- Consumes: Task 1 certification and the exact Step2A lease.
- Produces: `runless-final-gate` success, merged-main receipt, and `CFB_GAME_TOTAL_PAGE1_V2_STEP5_PACE_POSSESSIONS_FROZEN`.

- [ ] **Step 1: Prove the exact candidate head once through Runless App 5204253.**
- [ ] **Step 2: Merge only the exact certified head.**
- [ ] **Step 3: Rebind authority to merged main and reuse static evidence for atomic closeout.**
- [ ] **Step 4: Read back the frozen registry and require the new Step5 checkpoint plus unchanged unrelated thaws.**
