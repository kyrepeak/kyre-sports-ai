# MONSTER Step 2B First/Second-Pass Reliability Gate V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate a fail-closed Step 2B reliability preflight into Step 2A so implementation mutations target first- or second-pass success and stop before a third blind patch.

**Architecture:** Keep `mandatory_2b_reliability_gate_v1.py` independent and read-only. Call it from `mandatory_2a_action_gate_v1.py` for active `patch` and `edit_product` actions, while preserving Automatic Loop Kill precedence during live async work and existing Forward Motion authorization afterward.

**Tech Stack:** Python 3.11+, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-24-monster-step2b-first-second-pass-reliability-gate-v1-design.md`

## Global Constraints

- Step 2A remains mandatory.
- Automatic Loop Kill remains authoritative while `WAITING_ON_ASYNC`.
- Step 2B performs no network calls and no mutations.
- Attempt 2 requires materially new evidence.
- Two failed attempts force `ROOT_CAUSE_RESET`; no blind Attempt 3.

## Review Focus

- Missing Step 2B preflight cannot be bypassed with a valid Forward Motion receipt.
- Live async mutation lock still wins before Step 2B.
- Attempt-2 evidence cannot reuse the prior failed evidence fingerprint.
- Dependency preflight failures block before implementation.
- Non-implementation Step 2A mechanics remain behaviorally unchanged.

---

### Task 1: Step 2B Reliability Contract

**Files:**
- Create: `devsystem/mandatory_2b_reliability_gate_v1.py`
- Test: `tests/test_devsystem_mandatory_2b_reliability_gate_v1.py`

**Interfaces:**
- Produces: `authorize_implementation(action) -> dict`, `require_reliability_authority(result) -> dict`.

- [x] Write failing tests for missing preflight, Attempt 1, failed dependency, Attempt 2 evidence, and two-failure root-cause reset.
- [x] Verify tests fail before implementation exists.
- [x] Implement the minimal fail-closed gate and deterministic reliability receipt.
- [x] Verify the targeted tests and contract self-test pass.

### Task 2: Hard Step 2A Integration

**Files:**
- Modify: `devsystem/mandatory_2a_action_gate_v1.py`
- Create: `tests/test_devsystem_step2b_step2a_integration_v1.py`

**Interfaces:**
- Consumes: `authorize_implementation(action)`.
- Produces: Step 2A results with `two_b_enforced`, `reliability_decision`, `reliability_receipt_hash`, and `implementation_attempt` for implementation mutations.

- [x] Make active `patch` and `edit_product` actions call Step 2B before Forward Motion authorization.
- [x] Fail closed as `TWO_A_TWO_B_BLOCKED` when Step 2B denies.
- [x] Preserve live-async Automatic Loop Kill precedence.
- [x] Preserve existing non-implementation Step 2A behavior.

### Task 3: CI Certification and Freeze Proof

**Files:**
- Create: `.github/workflows/monster-step2b-reliability-gate-v1.yml`

**Interfaces:**
- Runs Step 2B self-test, Step 2A self-test, Step 2B/2A integration tests, existing Step 2A tests, and existing Anti-Loop tests.

- [x] Add targeted CI lane.
- [ ] Open one authoritative PR.
- [ ] Wait for the one authoritative terminal CI result.
- [ ] If green, merge and record exact main SHA as the frozen baseline.
