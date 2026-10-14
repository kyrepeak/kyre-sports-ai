# Universal Sports Source Finalization V1 Step 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Harden the append-oriented finalization bootstrap into a reusable, portable Finalization Worker and provide an explicit safe bridge to the legacy frozen registry without creating a second mutation owner.

**Architecture:** A pure worker validates one already-certified finalization packet against exact ledger and legacy-registry snapshots, constructs canonical freeze/manifest/bridge targets, performs one injected atomic CAS write to the finalization-ledger ref, and independently reads back every written object. The legacy registry is read-only: the bridge binds its exact ref/head/blob/revision/hash and active-thaw set; legacy thaw retirement remains owned by the existing legacy authority.

**Tech Stack:** Python 3.13, pytest, existing finalization bootstrap and frozen-registry contracts.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints
- Step 2A single-authority execution remains mandatory.
- Render is not required for final-state persistence.
- GitHub Actions fallback remains 0.
- No sports product/runtime/model mutation.
- No legacy frozen-registry mutation in Step 7 bridge mode.
- One CAS write attempt per unchanged evidence state; no retry loop.
- GREEN + FROZEN only after exact independent readback.

## Review Focus
- stale ledger ref/head/blob/revision/hash must fail before any write;
- mismatched repository/workstream/candidate/merged-main identity must fail closed;
- legacy registry state or active-thaw drift must fail before any write;
- requested legacy thaw retirement must be rejected rather than silently mutated;
- post-write readback tamper must fail after exactly one write and must not retry.

### Task 1: Finalization Worker + Legacy Bridge
**Files:**
- Create: `devsystem/universal_sports_finalization_worker_v1.py`
- Create: `tests/test_devsystem_universal_sports_finalization_worker_step7_v1.py`

- [x] Write failing tests for happy path and all review-focus failures.
- [x] Run focused tests and confirm RED because the worker module does not exist.
- [x] Implement the minimal worker using existing bootstrap and frozen-registry validators.
- [x] Run focused tests and confirm GREEN.
- [x] Run compile check.

### Task 2: Step-7 Contracts and Proof Plan
**Files:**
- Create: `devsystem/contracts/universal-sports-finalization-worker-v1.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step7.json`
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step7.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step7.json`

- [x] Lock the worker/bridge invariants and Step-7 freeze token.
- [x] Bind the exact focused test + compile commands in the Runless proof plan.
- [x] Verify all JSON parses.
- [ ] Persist the complete Step-7 candidate and run exact-head proof.
