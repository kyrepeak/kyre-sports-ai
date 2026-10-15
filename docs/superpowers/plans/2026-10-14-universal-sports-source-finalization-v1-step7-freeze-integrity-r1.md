# Universal Sports Source Finalization V1 Step 7 Freeze Integrity R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Step 7 so the reusable finalization worker fails closed on untrusted certification identity, immutable-token reuse, and non-exact blob readback, then append a new immutable repair closeout without rewriting the original Step-7 freeze record.

**Architecture:** Keep the existing append-oriented ledger and read-only legacy bridge. Extend the injected backend contract only with trusted certification and exact blob/path evidence required to prove identity, path absence, and exact write readback; retain one CAS write and zero deterministic retries. The original Step-7 freeze token remains historical and untouched; R1 uses a new freeze token.

**Tech Stack:** Python 3.13, pytest, GitHub append-oriented finalization ledger, Runless V2 proof/finalization.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Step 2A single-authority execution remains mandatory.
- Exactly one repair branch/PR/proof/finalization path is authoritative.
- Render is not required for final-state persistence.
- GitHub Actions fallback remains 0.
- No sports product/runtime/model/projection mutation.
- No legacy frozen-registry mutation in Step 7 bridge mode.
- One CAS write attempt per unchanged evidence state; no retry loop.
- GREEN + FROZEN only after exact independent readback.
- Never overwrite the original Step-7 immutable freeze record or bridge record.

## Review Focus

- A packet with `certified=true` but candidate/merge/proof/token different from trusted certification must fail before write.
- A reused freeze token whose record or bridge path already exists must fail before write.
- Parsed JSON equality must not hide exact Git blob/byte drift after write.
- Legacy registry state and active thaws must remain unchanged.
- Original Step-7 behavior and existing finalizer/frozen-registry regressions must remain GREEN.

---

### Task 1: Regression Tests for the Three Integrity Defects

**Files:**
- Create: `tests/test_devsystem_universal_sports_finalization_worker_step7_freeze_integrity_r1.py`

**Interfaces:**
- Consumes: `devsystem.universal_sports_finalization_worker_v1.finalize_certified_packet(packet, backend=...)`.
- Produces: regression expectations for trusted certification, immutable target paths, and exact blob readback.

- [ ] Write a failing test that changes candidate/proof identity while backend trusted certification remains unchanged; assert zero writes.
- [ ] Write a failing test that exposes an existing record/bridge target path; assert zero writes.
- [ ] Write a failing test whose backend reserializes JSON while preserving parsed equality but returns a different blob SHA; assert one write then readback failure.
- [ ] Run only the R1 tests and confirm RED for the intended missing protections.

### Task 2: Minimal Worker Hardening

**Files:**
- Modify: `devsystem/universal_sports_finalization_worker_v1.py`
- Test: `tests/test_devsystem_universal_sports_finalization_worker_step7_freeze_integrity_r1.py`

**Interfaces:**
- Backend trusted certification evidence: `trusted_certification() -> Mapping[str, Any]` with `freeze_token`, `candidate_sha`, `merged_main_sha`, and `proof_digest`.
- Backend immutable path evidence: `read_blob_sha(ref, path) -> str | None` returning `None` when a target path does not exist.
- Existing `snapshot()`, `cas_commit(...)`, `read_ref(ref)`, and `read_json(ref, path)` remain in use.

- [ ] Bind packet freeze token/candidate/merged-main/proof digest to `backend.trusted_certification()` before any write.
- [ ] Require record and bridge target paths to be absent before the CAS write.
- [ ] After the single CAS write, compare each written path's observed blob SHA to `_git_blob_sha(exact_submitted_text)` and fail closed on mismatch.
- [ ] Run R1 tests and confirm GREEN.
- [ ] Run original Step-7 focused tests and preserve compatibility by updating only test backends to satisfy the hardened interface where necessary.

### Task 3: Repair Contracts and Exact-Head Verification

**Files:**
- Create: `devsystem/contracts/universal-sports-finalization-worker-step7-freeze-integrity-r1.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step7-freeze-integrity-r1.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step7-freeze-integrity-r1.json`

**Interfaces:**
- New freeze token: `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_R1_FROZEN`.
- Proof plan binds worker, original Step-7 tests, R1 tests, contract, ledger, and this implementation plan.

- [ ] Lock the three new hard protections and immutable R1 token in the repair contract.
- [ ] Run Python compile, original Step-7 tests, R1 tests, existing 100% finalizer regressions, and frozen-registry regression suites.
- [ ] Run the repository-wide test suite when feasible and classify/report any inherited failures rather than hiding them.
- [ ] Persist the exact candidate and obtain one authoritative Runless exact-head proof.

### Task 4: Merge and New Immutable R1 Closeout

**Files:**
- Append only to the finalization ledger after proof and merge; do not modify the original Step-7 record/bridge.

**Interfaces:**
- Consumes: exact candidate proof receipt and exact merged-main SHA.
- Produces: a new R1 freeze record + bridge record + monotonic manifest update with independent GitHub readback.

- [ ] Merge the single repair PR only after exact-head proof is terminal GREEN and review findings are resolved.
- [ ] Append the R1 freeze record/bridge using the current ledger head as the CAS precondition.
- [ ] Independently read back exact R1 record/bridge/manifest blobs and verify candidate, merged-main, proof digest, revision, state hash, and zero unrelated mutation.
- [ ] Mark Step 7 GREEN + FROZEN only after the terminal readback is exact.
