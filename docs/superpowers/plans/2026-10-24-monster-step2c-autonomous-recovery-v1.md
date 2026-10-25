# MONSTER Step 2C Autonomous Recovery + Green Convergence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an autonomous recovery controller that keeps diagnosing after Anti-Loop stops repeated repairs and only reopens implementation when materially new root-cause evidence exists.

**Architecture:** Add a pure `mandatory_2c_autonomous_recovery_v1.py` decision module. Integrate its deterministic recovery receipt into Step 2B, then propagate recovery metadata through Step 2A while preserving Automatic Loop Kill precedence. No product/runtime mutation is performed by Step 2C itself.

**Tech Stack:** Python 3.11+, pytest, GitHub Actions, existing MONSTER DevSystem contracts.

**Spec:** `docs/superpowers/specs/2026-10-24-monster-step2c-autonomous-recovery-v1-design.md`

## Global Constraints

- Step 2A remains the single mandatory action front door.
- Automatic Loop Kill remains authoritative while `WAITING_ON_ASYNC`.
- Step 2B retains a hard two-attempt cap per diagnosis generation.
- Step 2C performs no network calls and no repository/product mutations.
- No third blind patch is allowed.
- New implementation generation requires materially new root-cause evidence bound to the exact authoritative path.
- User intervention occurs only for a verified human-only blocker.
- One authoritative branch, one PR, one proof path.

## Review Focus

- Duplicate evidence must never unlock another implementation generation.
- A recovery receipt for a different task/checkpoint/path must be rejected.
- An unverified or unsupported human blocker must remain autonomous diagnosis.
- Live async state must still block competing mutations before recovery logic runs.
- Recovery generation bookkeeping must not silently erase the original two failed attempts.

---

### Task 1: Step 2C Pure Recovery Contract

**Files:**
- Create: `devsystem/mandatory_2c_autonomous_recovery_v1.py`
- Create: `tests/test_devsystem_mandatory_2c_autonomous_recovery_v1.py`

**Interfaces:**
- Produces: `decide_recovery(context: Mapping[str, Any]) -> dict[str, Any]`
- Produces: `validate_recovery_receipt(receipt: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]`
- Produces: deterministic `recovery_receipt_hash` for a proven materially new root cause.

- [ ] Write RED tests for duplicate evidence, new evidence selection, diagnosis expansion, valid root-cause receipt, forged receipt rejection, and verified human blocker behavior.
- [ ] Run the Step 2C test file and verify RED because the module does not exist.
- [ ] Implement the minimal pure Step 2C decision/receipt contract.
- [ ] Run Step 2C tests and contract self-test to GREEN.

### Task 2: Step 2B Recovery-Generation Integration

**Files:**
- Modify: `devsystem/mandatory_2b_reliability_gate_v1.py`
- Modify: `tests/test_devsystem_mandatory_2b_reliability_gate_v1.py`

**Interfaces:**
- Consumes: Step 2C `validate_recovery_receipt(...)`.
- Produces: `TWO_B_TWO_C_RECOVERY_REQUIRED` when two failures exist without valid recovery authority.
- Produces: `TWO_B_RECOVERY_ATTEMPT_AUTHORIZED` when the exact valid Step 2C receipt opens a new diagnosis generation.

- [ ] Add RED tests proving two failed attempts remain blocked without Step 2C authority and valid authority opens only a new evidence-bound generation.
- [ ] Run Step 2B targeted tests and verify RED.
- [ ] Implement the minimal Step 2B integration without changing Attempt 1/2 behavior.
- [ ] Run Step 2B + Step 2C tests to GREEN.

### Task 3: Step 2A + Anti-Loop End-to-End Integration

**Files:**
- Modify: `devsystem/mandatory_2a_action_gate_v1.py`
- Create: `tests/test_devsystem_step2c_step2b_step2a_integration_v1.py`

**Interfaces:**
- Consumes: Step 2B recovery metadata.
- Produces: Step 2A results exposing `two_c_enforced`, `recovery_decision`, and `recovery_receipt_hash` when applicable.

- [ ] Add RED integration tests: no Step 2C receipt blocks after two failures; valid receipt + Forward Motion allows the new repair generation; mismatched receipt fails closed; live async mutation is still blocked by Automatic Loop Kill first.
- [ ] Run the integration test and verify RED.
- [ ] Implement minimal Step 2A metadata propagation/authorization integration.
- [ ] Run Step 2A + Step 2B + Step 2C + Anti-Loop targeted suite to GREEN.

### Task 4: Dedicated Certification and Freeze Proof

**Files:**
- Create: `.github/workflows/monster-step2c-autonomous-recovery-v1.yml`
- Create: `devsystem/runless_proof_plans/monster-step2c-autonomous-recovery-v1.json`

**Interfaces:**
- CI runs Step 2C self-test, Step 2B self-test, Step 2A self-test, and all targeted recovery/Anti-Loop tests.
- Runless plan certifies the exact candidate head with approved module/pytest commands.

- [ ] Add the dedicated CI lane and Runless proof plan.
- [ ] Open exactly one authoritative PR.
- [ ] Wait for terminal CI evidence; classify any failure before one evidence-backed correction.
- [ ] Obtain one exact-head Runless final-gate proof.
- [ ] Merge only the certified exact head.
- [ ] Append/read back Finalization Ledger V2 freeze record and manifest.
- [ ] Claim GREEN + FROZEN only after exact record/manifest readback.
