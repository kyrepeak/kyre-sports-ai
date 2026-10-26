# MONSTER Step 2G Final Production Convergence Implementation Plan

> **For agentic workers:** execute inline under Step 2A + Anti-Loop, with TDD and one authoritative MONSTER lane.

**Goal:** Add a permanent fail-closed MONSTER Step 2G that blocks final GREEN/FROZEN until the exact certified MONSTER state is proven on the live production runtime, router, backend path, and user-facing UI.

**Architecture:** Extend the existing MONSTER Step 2C-2F permanent control stack with one read-only convergence verifier. Step 2G consumes MONSTER-owned evidence only, classifies the exact failing boundary, emits a deterministic digest, and authorizes final freeze only after live convergence. It never imports or reads API 2 state.

**Tech Stack:** Python 3.11, pytest, GitHub Actions supporting evidence, existing MONSTER registries/receipt/freeze controls.

**Spec:** User-supplied permanent MONSTER Step 2G contract in this conversation.

## Global Constraints

- MONSTER only; API 2 evidence is forbidden.
- One branch, one PR, one proof lane, one deployment path.
- Step 2A and Anti-Loop remain mandatory.
- No blind redeploy or repeated cache clear.
- Repository/deployment success alone cannot authorize GREEN/FROZEN.
- Final freeze requires Step 2G evidence digest + exact live identity readback.

## Review Focus

- Repository new + deployment new + live website old must fail closed.
- Stable alias drift must fail even with a healthy deployment.
- Stale Streamlit module/process/cache state must fail closed.
- Router/backend/schema/UI identity mismatches must classify precisely.
- Any API 2 evidence must be rejected as foreign-system evidence.

### Task 1: RED contract + authority lock

**Files:**
- Create `tests/test_devsystem_mandatory_2g_final_production_convergence_v1.py`
- Create `devsystem/task_ledgers/monster-step2g-final-production-convergence-v1.json`
- Create `devsystem/monster_proof_plans/monster-step2g-final-production-convergence-v1.json`
- Create `.github/workflows/monster-step2g-final-production-convergence-v1.yml`

- [x] Write Step 2G failing tests first.
- [x] Lock Step 2A one-lane authority.
- [x] Lock Anti-Loop no-repeat policy.
- [ ] Observe one terminal RED run proving the Step 2G module is missing.

### Task 2: Implement Step 2G verifier

**Files:**
- Create `devsystem/mandatory_2g_final_production_convergence_v1.py`

- [ ] Implement deterministic MONSTER-only convergence validation.
- [ ] Add precise boundary failure classification.
- [ ] Enforce runtime/cache/router/backend/UI parity.
- [ ] Emit deterministic Step 2G evidence digest and recovery sequence.
- [ ] Make focused tests GREEN.

### Task 3: Integrate permanent stack + final receipt

**Files:**
- Modify `devsystem/mandatory_2c2d2e2f_permanent_enforcement_v1.py`
- Modify `devsystem/monster_authoritative_proof_receipt_v1.py`
- Add/update regression tests.

- [ ] Require Step 2G in permanent stack.
- [ ] Require `step2g` GREEN in final authoritative receipt.
- [ ] Require live convergence proof before frozen authorization.
- [ ] Run existing Step 2A–2F + Step 2G focused regression bundle.

### Task 4: Exact-head proof, merge, live convergence, freeze

- [ ] Certify exact PR head.
- [ ] Merge only expected head to `monster-main`.
- [ ] Verify merged SHA and rollback anchor.
- [ ] Verify stable production alias/runtime/route/backend/UI identity.
- [ ] Write MONSTER-owned frozen checkpoint with Step 2G digest.
- [ ] Read frozen registry back and require exact identity/digest match.
- [ ] Declare `MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1_FROZEN` only after all checks are GREEN.
