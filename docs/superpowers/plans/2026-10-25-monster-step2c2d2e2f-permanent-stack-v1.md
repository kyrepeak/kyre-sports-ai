# MONSTER Permanent Step 2C + 2D + 2E + 2F Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Extend the existing MONSTER control plane with permanent canonical-router ownership (Step 2E), live-production/stable-alias verification (Step 2F), and a MONSTER-owned authoritative proof receipt while preserving frozen Step 2C/2D behavior.

**Architecture:** Keep the existing Step 2A/Anti-Loop/Step 2B/Step 2C/Step 2D modules as prerequisites. Add two read-only fail-closed gates driven by MONSTER-owned registries, then compose them in one permanent control-stack validator. GitHub Actions supplies regression evidence; a separate MONSTER receipt contract binds exact SHA, gate evidence, deployment applicability/identity, rollback anchor, and freeze target.

**Tech Stack:** Python 3.11, pytest, Streamlit frontend routing, FastAPI Kyre Sports API mount inspection, JSON registries, SHA-256 evidence receipts.

**Spec:** `docs/superpowers/specs/2026-10-25-monster-step2c2d2e2f-permanent-stack-v1.md`

## Global Constraints

- System authority is MONSTER only.
- Base is `monster-main` at `c9be8571401a0b07f34c28fdaa86056202d5e26a`.
- Exactly one branch, PR, proof namespace, deployment path (when applicable), scope lease, and one-use authorization.
- Do not read foreign-system state as evidence.
- Preserve existing Step 2C/2D behavior unless a failing MONSTER-owned test proves a repair is required.
- GitHub Actions is supporting evidence only; authoritative GREEN/FROZEN requires a MONSTER receipt + freeze readback.

## Review Focus

- Registry entry exists but runtime resolves a different sport/market module.
- Backend endpoint file exists but router is not mounted in `sports_api/main.py`.
- Stable alias is healthy but points to a deployment whose certified SHA differs from MONSTER candidate.
- Preview/stale deployment is presented as production.
- Failure evidence is reused without a materially changed fingerprint.

---

### Task 1: TDD RED contracts + authority state

**Files:**
- Create: `tests/test_devsystem_mandatory_2e_canonical_router_ownership_v1.py`
- Create: `tests/test_devsystem_mandatory_2f_live_production_consumption_v1.py`
- Create: `tests/test_devsystem_monster_step2c2d2e2f_permanent_stack_v1.py`
- Create: `.github/workflows/monster-step2c2d2e2f-permanent-stack-v1.yml`
- Existing: `devsystem/task_ledgers/monster-step2c2d2e2f-permanent-stack-v1.json`

- [ ] Write RED tests requiring Step 2E, Step 2F, proof receipt, and composed permanent stack modules.
- [ ] Require exact-SHA checkout, depth 1, no persisted credentials, and branch scope `monster-main`.
- [ ] Open exactly one PR to `monster-main` and capture the expected missing-module RED failure.

### Task 2: Step 2E canonical router ownership

**Files:**
- Create: `devsystem/mandatory_2e_canonical_router_ownership_v1.py`
- Create: `devsystem/monster_router_registry_v1.json`

**Interfaces:**
- Consumes the live route set from `universal_sports_nav_registry_v1.py`, the runtime adapter mapping in `universal_runtime_v5_loader.py`, and backend mounts in `sports_api/main.py`.
- Produces `validate_router_registry(...) -> dict` with GREEN/BLOCKED result, failure fingerprint, Step 2C evidence, and `next_legal_action`.

- [ ] Make duplicate sport/market ownership fail closed.
- [ ] Prove each live registered route resolves through the authoritative runtime, preserves required params, and has one expected consumer owner.
- [ ] For backend-required routes, prove endpoint metadata and mounted router ownership.
- [ ] Reject orphan routes, cross-sport adapters, generic fallthrough ownership, and legacy override conflicts.

### Task 3: Step 2F live production consumption / stable alias

**Files:**
- Create: `devsystem/mandatory_2f_live_production_consumption_v1.py`
- Create: `devsystem/monster_production_registry_v1.json`

**Interfaces:**
- Consumes a MONSTER production attestation containing candidate SHA, deployment ID/SHA, production flag, stable alias, alias target, canonical endpoint, health/schema/router/consumer evidence, smoke coverage, rollback anchor, and evidence timestamps.
- Produces GREEN/BLOCKED result with deterministic failure classification/fingerprint and Step 2C recovery evidence.

- [ ] Fail closed for candidate/deployment mismatch, preview-as-production, stale deployment, alias drift, wrong project/environment, endpoint/router/schema mismatch, unhealthy response, missing smoke coverage, missing rollback anchor, or duplicate promotion lane.
- [ ] Require both correct code identity and live stable-alias consumption.
- [ ] Encode deployment applicability explicitly; N/A is valid only for read-only control-plane-only implementation proof.

### Task 4: MONSTER authoritative receipt + permanent stack

**Files:**
- Create: `devsystem/monster_authoritative_proof_receipt_v1.py`
- Create: `devsystem/mandatory_2c2d2e2f_permanent_enforcement_v1.py`
- Create: `devsystem/monster_proof_plans/monster-step2c2d2e2f-permanent-stack-v1.json`

**Interfaces:**
- Receipt generator canonicalizes exact candidate SHA, gate results, evidence digests, regression result, production/deployment evidence, rollback anchor, and freeze target and returns an SHA-256 receipt digest.
- Permanent enforcement requires Step 2C, Step 2D, Step 2E, Step 2F, isolation, Anti-Loop, Step 2B, and Step 2A contracts to be present and GREEN.

- [ ] Reject receipts with foreign-system evidence, mismatched SHA, mismatched digest, missing rollback/freeze target, or skipped gate.
- [ ] Require GitHub Actions only as supporting regression evidence, never sole authority.

### Task 5: Exact proof, merge, final verification, freeze

**Files:**
- Update: `devsystem/task_ledgers/monster-step2c2d2e2f-permanent-stack-v1.json`
- Create on freeze ref: `devsystem/monster_freeze_records/monster-step2c2d2e2f-permanent-stack-v1.json`

- [ ] Run exact-head MONSTER workflow and obtain terminal GREEN regression evidence.
- [ ] Independently create/read MONSTER authoritative proof receipt bound to the exact candidate.
- [ ] Merge only the certified head into `monster-main` with an expected-head lease.
- [ ] Re-run/read post-merge control proof.
- [ ] If deployment is applicable, prove exact production deployment + stable alias + smoke + rollback; if not applicable, bind the explicit N/A reason into the receipt.
- [ ] Write content-addressed MONSTER freeze checkpoint and read back candidate SHA, merged SHA, evidence digest, receipt digest, deployment identity/applicability, rollback anchor, and freeze token.
