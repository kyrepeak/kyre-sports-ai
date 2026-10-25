# MONSTER Step 2D Data-Truth V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permanent MONSTER-only post-execution Step 2D gate that blocks false blanks, unverified absence, technical-failure negative caching, fabricated values, unapproved fallbacks, and end-to-end truth mismatches.

**Architecture:** Preserve the frozen Step 2B/2C baseline. Add a new read-only `mandatory_2d_data_truth_gate_v1` that consumes MONSTER field traces after execution, plus a new additive permanence gate and one exact-head Step 2D workflow. Step 2D failures emit MONSTER-owned evidence and deterministically route back to Anti-Loop/Step 2C.

**Tech Stack:** Python 3.11, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-24-monster-step2d-data-truth-v1.md`

## Global Constraints
- MONSTER is the only authority for this implementation.
- Preserve the existing frozen Step 2B/2C baseline rather than modifying its frozen files.
- One authoritative branch, PR, and Step 2D proof workflow.
- Exact candidate SHA checkout, fetch depth 1, credentials not persisted.
- No product/runtime mutation from the Step 2D verifier itself.
- No final GREEN before post-merge verification; no FROZEN before independent freeze-record readback.

## Review Focus
- Technical failure incorrectly becoming NOT_AVAILABLE or another absence state.
- Real zero incorrectly treated as blank.
- Fallback selected outside the field-specific approved set.
- Source value surviving ingestion but drifting at authoritative/final output.
- Failure evidence being negative-cached or losing its explicit diagnostic state.

---

### Task 1: RED Step 2D behavior contracts
**Files:** create the Step 2D behavior and recovery integration tests plus the single exact-head workflow.
- [ ] Write failing tests for value preservation, false blank, unverified absence, verified absence, failure-state preservation, fallback policy, no fabrication, no negative-cache on technical failure, isolation, and execution ordering.
- [ ] Run the authoritative PR workflow and record RED because the Step 2D modules do not yet exist.

### Task 2: Implement Step 2D and recovery handoff
**Files:** create `devsystem/mandatory_2d_data_truth_gate_v1.py`.
- [ ] Implement post-execution verification with explicit failure/absence state separation.
- [ ] Implement field-specific fallback proof and semantic truth comparison.
- [ ] Emit deterministic failure fingerprints and the Anti-Loop -> Step 2C recovery route.
- [ ] Run the focused Step 2D behavior suite GREEN.

### Task 3: Make Step 2D permanent
**Files:** create `devsystem/mandatory_2d_permanent_enforcement_v1.py`, proof plan, ledger, permanence tests.
- [ ] Compose the existing MONSTER permanent baseline with Step 2D without mutating the frozen baseline.
- [ ] Bind the single exact-head Step 2D workflow and proof plan.
- [ ] Prove the full MONSTER control chain and focused regressions on the exact candidate.
- [ ] Merge with expected-head protection, rerun the same workflow on the merge SHA, write a content-addressed MONSTER freeze record, and read it back.
