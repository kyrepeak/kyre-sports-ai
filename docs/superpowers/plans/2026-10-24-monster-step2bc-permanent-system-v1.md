# MONSTER Step 2B/2C Permanent System Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make MONSTER's completed Step 2B + Step 2C architecture a hard, permanent, fail-closed system behavior with explicit API 2 isolation and terminal GREEN/FROZEN proof.

**Architecture:** Preserve the existing MONSTER Step 2A → Step 2B → Step 2C control modules and add one MONSTER-only isolation guard. Wire the Step 2B/2C permanent enforcement into MONSTER's global permanent gate and targeted certification so the controls cannot silently disappear. Keep all recovery reasoning read-only until Step 2A authorizes one exact repair.

**Tech Stack:** Python 3, pytest, existing MONSTER DevSystem controls, existing MONSTER Runless proof/finalization path.

**Spec:** User-provided MONSTER-only implementation command in the 2026-10-24 conversation, plus the existing Step 2B/2C design specs already merged by MONSTER PRs #1785 and #1787.

## Global Constraints

- MONSTER and API 2 are independent systems; API 2 state is never evidence for MONSTER.
- Exactly one active MONSTER problem and one authoritative MONSTER branch/proof path.
- Failure → Anti-Loop → Step 2C → Step 2B → Step 2A → repair → verify → GREEN → FROZEN.
- No blind repeated failed action; new mutation requires materially new evidence/root-cause hypothesis.
- Human interruption only for a verified human-only blocker.
- GREEN requires acceptance proof; FROZEN requires explicit finalization/read-back.

## Review Focus

- API 2 branch/proof/evidence identifiers must fail closed at the MONSTER control boundary.
- The global MONSTER permanent gate must require Step 2B, Step 2C, isolation, and permanent enforcement artifacts.
- MONSTER targeted certification must execute the isolation and Step 2B/2C permanent enforcement checks.
- Existing Step 2A/Anti-Loop precedence must remain unchanged.
- Recovery generations must still require materially new evidence and exact authoritative-path binding.

---

### Task 1: RED permanent-system contract

**Files:**
- Modify: `tests/test_devsystem_step2bc_permanent_gate_v1.py`

- [ ] Add failing tests requiring global permanent-gate integration and a MONSTER-only isolation guard.
- [ ] Run the MONSTER Step 2C certification lane and verify the new contract fails for the intended missing integration.

### Task 2: MONSTER hard-isolation guard

**Files:**
- Create: `devsystem/monster_system_isolation_v1.py`
- Modify: `devsystem/mandatory_2a_action_gate_v1.py`
- Modify: `devsystem/mandatory_2b_reliability_gate_v1.py`
- Modify: `devsystem/mandatory_2c_autonomous_recovery_v1.py`

- [ ] Reject API 2-owned identifiers/evidence at MONSTER control boundaries.
- [ ] Preserve the shared repository name while rejecting API 2 branches, task/workstream/proof identifiers, evidence, and recovery state.
- [ ] Run focused tests to GREEN.

### Task 3: Global permanent enforcement

**Files:**
- Modify: `devsystem/permanent_gate_v1.py`
- Modify: `devsystem/mandatory_2bc_permanent_enforcement_v1.py`
- Modify: `.github/workflows/devsystem-targeted-ci.yml`

- [ ] Make Step 2B/Step 2C/isolation artifacts required global MONSTER DevSystem files.
- [ ] Require targeted CI markers that execute MONSTER isolation and Step 2B/2C permanent enforcement.
- [ ] Keep the global gate fail-closed if any permanent control drifts.
- [ ] Run focused + existing Step 2A/Anti-Loop/Step 2B/Step 2C regression tests.

### Task 4: Exact proof and freeze

**Files:**
- Create: `devsystem/runless_proof_plans/monster-step2bc-permanent-system-v1.json`
- Create: `devsystem/task_ledgers/monster-step2bc-permanent-system-v1.json`

- [ ] Bind one exact candidate SHA and one MONSTER Runless proof path.
- [ ] Require compile, focused integration tests, Step 2A, Anti-Loop, Step 2B, Step 2C, permanent gate, and isolation tests.
- [ ] Merge only the exact certified candidate.
- [ ] Read back MONSTER finalization evidence and record `MONSTER_STEP2BC_PERMANENT_SYSTEM_V1_FROZEN` only after terminal proof.
