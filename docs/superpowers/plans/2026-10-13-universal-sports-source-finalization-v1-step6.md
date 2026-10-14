# Universal Sports Source Receipt + Provenance Step 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic, provenance-complete source receipts for every accepted field-level sports data decision without adding network calls or reopening Steps 1–5.

**Architecture:** Step 6 is an additive receipt layer over existing Step 3 routing, Step 4 quorum decisions, and Step 5 canonical identity/field-health context. It records only providers actually attempted, preserves selected providers, fallback rank, freshness, health, rejected attempts, aliases, canonical IDs, agreement state, and value fingerprint, then seals the result with deterministic receipt identity and digest.

**Tech Stack:** Python 3, JSON contracts, pytest, existing Runless proof plane, GitHub finalization ledger.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Workstream: `universal-sports-source-finalization-v1`.
- Routing unit remains `DATA_FIELD`.
- Active providers means actually consulted providers only.
- Canonical IDs remain internally owned.
- `fabrication=false` and incompatible provenance is not synthesized.
- No product runtime or sports-model mutation.
- No legacy frozen-registry mutation.
- Render is not required for finalization.
- GitHub Actions fallback remains `0`.
- Step 2A permits one authoritative branch, PR, proof path, and freeze transaction only.

## Review Focus

- A selected provider that was not actually attempted must fail closed.
- Missing freshness evidence for an attempted provider must fail closed.
- Missing field-aware health for an attempted provider must fail closed.
- Non-accepted quorum decisions must not emit accepted source receipts.
- Any receipt or contract tampering must be detected by deterministic fingerprints.

---

### Task 1: Receipt contract and TDD boundary

**Files:**
- Create: `devsystem/contracts/universal-sports-source-receipt-v1.json`
- Test: `tests/test_devsystem_universal_sports_source_receipt_step6_v1.py`

**Interfaces:**
- Consumes: Step 3 route, Step 4 quorum decision, Step 5 identity/health context.
- Produces: frozen Step-6 receipt contract and acceptance tests.

- [x] **Step 1: Prove the Step-6 implementation module is absent on the authoritative branch.**
- [x] **Step 2: Commit the failing test contract before implementation.**
- [x] **Step 3: Define the deterministic receipt contract and contract fingerprint.**

### Task 2: Deterministic source receipt implementation

**Files:**
- Create: `devsystem/universal_sports_source_receipt_v1.py`
- Test: `tests/test_devsystem_universal_sports_source_receipt_step6_v1.py`

**Interfaces:**
- Consumes: `route`, `quorum_decision`, `identity_resolution`, `identity_health_context`, attempted observations.
- Produces: `build_source_receipt(...)` and `validate_source_receipt(...)`.

- [x] **Step 1: Implement deterministic receipt construction with attempted/selected providers, fallback rank, freshness, field health, aliases, canonical IDs, rejected attempts, and quorum provenance.**
- [x] **Step 2: Seal each receipt with deterministic `receipt_id` and `receipt_digest`.**
- [x] **Step 3: Fail closed for non-accepted decisions, missing observation/health evidence, off-route attempts, or identity drift.**
- [x] **Step 4: Run local preflight tests; expected result is 10 passing tests.**

### Task 3: Certification and freeze packet

**Files:**
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step6.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step6.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step6.json`

**Interfaces:**
- Consumes: exact Step-6 PR head and existing Runless/finalization bootstrap.
- Produces: one exact-head proof, merged-main identity, and Step-6 finalization-ledger record/manifest transition.

- [x] **Step 1: Bind the execution plan to authoritative PR #1531 and base SHA `246d7d92485fdc93b220f53b14df95402d9aadc6`.**
- [x] **Step 2: Define one Runless proof packet covering Step 6 plus Step 2–5 regressions.**
- [x] **Step 3: Lock task ledger to `RUN_SINGLE_EXACT_HEAD_RUNLESS_PROOF`.**
- [ ] **Step 4: Execute exactly one exact-head Runless proof and require `runless-final-gate` success on the exact candidate SHA.**
- [ ] **Step 5: Merge PR #1531 only after exact-head proof success.**
- [ ] **Step 6: Append the Step-6 immutable freeze record and advance the ledger manifest by one revision.**
- [ ] **Step 7: Independently read back record + manifest hashes and confirm Steps 1–5 are unchanged before declaring GREEN + FROZEN.**
