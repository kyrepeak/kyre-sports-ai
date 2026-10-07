# API 2 Finalization Authority Step 1 — Canonical Completion Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make authoritative frozen-registry + Runless proof evidence resolve terminal completion even when a mutable task ledger is stale.

**Architecture:** Add one pure/read-only resolver. It validates the frozen registry and immutable Runless receipt, binds the successful `runless-final-gate` to that receipt, requires explicit merge provenance from the certified candidate into the registry's merged-main SHA, and treats ledger state as advisory only. Step 1 does not mutate or auto-heal old ledgers; that is Step 2.

**Tech Stack:** Python, pytest, existing DevSystem frozen-registry validator, existing Runless terminal-receipt validator.

**Spec:** API 2 — Finalization Authority & 100% Convergence V1, Step 1/6.

## Global Constraints

- STEP 2A before every mutation.
- One active problem, branch, PR, and proof chain.
- Runless proof only; GitHub Actions proof fallback forbidden.
- No product/runtime/sports-model changes.
- Unrelated frozen artifacts and active thaws remain untouched.
- Proof before GREEN + FROZEN.

## Review Focus

- Stale ledger must not veto valid canonical terminal evidence.
- A green ledger alone must never manufacture completion.
- Missing/failed/mismatched Runless gate must fail closed.
- Candidate-to-merged-main provenance must be exact and explicit.
- Tampered terminal receipts must fail closed without mutating inputs.

---

### Task 1: Canonical Completion Resolver

**Files:**
- Create: `devsystem/canonical_completion_resolver_v1.py`
- Create: `tests/test_devsystem_canonical_completion_resolver_v1.py`
- Create: `devsystem/runless_proof_plans/api2-finalization-authority-v1-step1-canonical-completion.json`
- Create: `devsystem/execution_plans/api2-finalization-authority-v1-step1-canonical-completion.json`
- Create: `devsystem/task_ledgers/api2-finalization-authority-v1-step1-canonical-completion.json`

**Interface:**
- Produces `resolve_completion(task_id, freeze_token, ledger, registry, receipt, gate, merge_evidence) -> dict`.
- `complete=True` only when the authoritative registry entry is FROZEN, the receipt validates and belongs to the task, the Runless final gate succeeds on the receipt candidate and digest, and merge evidence binds that candidate into the registry entry's merged-main SHA.
- Ledger disagreement is returned as `ledger_stale=True`; it is never a canonical veto.

- [ ] Write failing regression tests before implementation.
- [ ] Run the focused suite and observe RED because the resolver module does not exist.
- [ ] Implement the minimal pure resolver.
- [ ] Run focused + receipt/gate regression suites and observe GREEN.
- [ ] Run Runless exact-head proof; require immutable receipt + `runless-final-gate` success.
- [ ] Merge exact certified head only.
- [ ] Verify merged-main contract without duplicating an equivalent proof.
- [ ] Freeze Step 1 in the authoritative frozen registry with CAS/read-back while preserving unrelated thaws.
