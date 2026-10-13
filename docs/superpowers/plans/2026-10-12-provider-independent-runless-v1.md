# Provider-Independent Runless V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple Runless proof execution from Render so the same exact-head proof identity can execute on an alternate compute surface, persist one authoritative GitHub receipt, publish the approved Runless gate, and complete Universal Sports Step 4 without weakening existing protections.

**Architecture:** Keep candidate identity, Step 2A, proof-plan semantics, receipt storage, approved GitHub App gate publication, merge ordering, and finalization authority unchanged. Extract provider-independent frozen-state verification and executor semantics from the hosted service so Render and an ephemeral Vercel sandbox can execute the same proof contract; GitHub receipt readback remains durable authority, while executor choice is metadata rather than trust.

**Tech Stack:** Python 3, Pydantic, pytest, existing `runless_proof_plane` modules, GitHub App API, Vercel sandbox as alternate compute.

**Spec:** `docs/superpowers/specs/2026-10-12-provider-independent-runless-v1-design.md`

## Global Constraints

- Preserve exact candidate SHA binding and exact current-main binding.
- Preserve live scope-lease validation and Step 2A authorization.
- Preserve exact proof-plan commands, artifact/dependency blob maps, proof fingerprint, receipt digest, and approved `runless-final-gate` publisher identity.
- Render is optional compute; it is not proof authority.
- GitHub receipt readback is mandatory before merge authorization.
- GitHub Actions fallback remains `0`.
- Universal Sports Steps 1–6 must not mutate the legacy frozen registry merely to align `source_main_sha`.
- Existing frozen Steps 1–3 remain protected and may not be reopened.
- No sports-page product/runtime or model files may change.
- Only one authoritative proof identity may exist for a candidate/workstream at a time.
- Executor failover is legal only after a terminal infrastructure failure and must reuse the same proof identity/fingerprint.

## Review Focus

- **Sidecar lineage ambiguity:** Universal Sports proof must fail closed when sidecar finalization lineage cannot uniquely establish inherited frozen state.
- **Executor identity drift:** alternate executor must fail if checked-out SHA differs from requested candidate before any proof command executes.
- **Duplicate proof lane:** a second executor must not start while the same proof identity is active or terminal-successful.
- **Receipt replay/collision:** an existing receipt with mismatched candidate/task/workstream/fingerprint must fail closed rather than be reused.
- **Gate/receipt split-brain:** approved gate publication must require a receipt that was written, read back, digest-validated, and matched to the exact candidate.

---

### Task 1: Frozen-State Verification Adapter

**Files:**
- Create: `runless_proof_plane/frozen_state.py`
- Modify: `runless_proof_plane/prove.py`
- Test: `tests/test_runless_provider_independent_frozen_state_v1.py`

**Interfaces:**
- Consumes: GitHub client, candidate SHA/tree, current main SHA/tree, workstream, existing legacy registry backend, Universal Sports sidecar manifest/record data.
- Produces: `verify_frozen_state(client, *, workstream: str, candidate_sha: str, candidate_tree: dict[str, str], main_sha: str, main_tree: dict[str, str]) -> dict[str, object]` returning revision/hash/lineage identity, active thaws, inherited paths, exact-thawed paths, and authority kind.

- [ ] **Step 1: Write failing sidecar/legacy verification tests**

Pin these assertions in `tests/test_runless_provider_independent_frozen_state_v1.py`:
- Universal Sports workstream with valid sidecar lineage passes when legacy `source_main_sha` is stale but candidate inherits current-main frozen blobs.
- No legacy registry mutation occurs.
- ambiguous/missing sidecar lineage fails closed.
- candidate frozen delta without one exact thaw fails closed.
- legacy non-Universal workstream preserves current registry-main identity behavior.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest -q tests/test_runless_provider_independent_frozen_state_v1.py`
Expected: FAIL because `runless_proof_plane.frozen_state` and provider-independent verification do not exist.

- [ ] **Step 3: Implement the minimal adapter**

Implement `verify_frozen_state(...)` in `runless_proof_plane/frozen_state.py`. Detect Universal Sports sidecar-finalized workstreams from authoritative sidecar manifest/record lineage; validate current-main identity, inherited blob equality, exact thaw grants for candidate deltas, and fail closed on ambiguous lineage. Preserve the existing legacy path for all other workstreams.

Modify `runless_proof_plane/prove.py` to call the adapter instead of the embedded `_verify_frozen_candidate` production path; keep compatibility helper coverage where existing unit tests depend on it.

- [ ] **Step 4: Run focused + existing Runless proof tests**

Run: `python -m pytest -q tests/test_runless_provider_independent_frozen_state_v1.py tests/test_runless_*prove*.py tests/test_runless_*registry*.py`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(runless): add provider-independent frozen state verification"`

---

### Task 2: Provider-Neutral Executor Contract and Proof Identity

**Files:**
- Modify: `runless_proof_plane/executor.py`
- Create: `runless_proof_plane/provider_executor.py`
- Modify: `runless_proof_plane/models.py`
- Test: `tests/test_runless_provider_executor_v1.py`

**Interfaces:**
- Consumes: validated proof plan, exact candidate workspace, deterministic proof context.
- Produces: `ExecutionContext`, `EvidenceBundle`, `RunlessExecutor` protocol, `HostedRunlessExecutor`, and `compute_provider_independent_proof_identity(...)`.

- [ ] **Step 1: Write failing executor-equivalence and anti-duplication tests**

Tests must assert:
- hosted and alternate executor wrappers produce equivalent evidence semantics for the same plan/workspace;
- executor metadata does not change the semantic proof fingerprint;
- wrong checked-out candidate identity fails before commands execute;
- same proof identity cannot be concurrently claimed by two executor instances;
- terminal INFRA failure permits executor switch while preserving proof identity.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_runless_provider_executor_v1.py`
Expected: FAIL because the provider-neutral interfaces do not exist.

- [ ] **Step 3: Implement minimal provider-neutral interfaces**

Keep existing `execute_command` / `execute_static_slice` behavior as the hosted implementation. Add typed context/bundle objects and a narrow executor protocol. Compute proof identity/fingerprint from task/workstream/candidate/lease/authorization plus proof-plan/artifact/dependency policy, never from executor kind.

- [ ] **Step 4: Run focused + parallel-slice regressions**

Run: `python -m pytest -q tests/test_runless_provider_executor_v1.py tests/test_runless_task17_step2_parallel_slices.py`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(runless): make proof execution provider neutral"`

---

### Task 3: Receipt-First Authority and Readback Gate

**Files:**
- Modify: `runless_proof_plane/prove.py`
- Modify: `runless_proof_plane/receipts.py`
- Modify: `runless_proof_plane/gate.py`
- Test: `tests/test_runless_receipt_first_authority_v1.py`

**Interfaces:**
- Consumes: successful `EvidenceBundle`, exact proof identity/fingerprint, frozen-state verification result, GitHub receipt backend, approved GitHub App client.
- Produces: `persist_and_validate_terminal_receipt(...) -> dict`, and gate publication only after exact receipt readback.

- [ ] **Step 1: Write failing receipt-authority tests**

Tests must assert:
- successful evidence writes exactly one receipt and immediately reads it back;
- readback digest/candidate/task/workstream/proof fingerprint must match before gate publication;
- tampered readback fails closed;
- duplicate receipt with identical identity may be reused only if all bound fields match;
- duplicate receipt with mismatched identity/fingerprint fails closed;
- `publish_gate(..., conclusion="success")` cannot run for an unvalidated/non-read-back receipt.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_runless_receipt_first_authority_v1.py`
Expected: FAIL because current code publishes after `store.put` without a mandatory exact readback authority step.

- [ ] **Step 3: Implement receipt-first authority**

Add a small receipt persistence/readback helper in `receipts.py`; update `prove.py` to build or reuse one immutable receipt, read it back, validate identity and digest, then advance to gate publication. Update `gate.py` to require the validated receipt marker/contract without changing the required GitHub App check name.

Executor metadata may be added as backward-compatible optional receipt fields; do not alter required receipt keys or digest semantics incompatibly.

- [ ] **Step 4: Run receipt/gate/prove regressions**

Run: `python -m pytest -q tests/test_runless_receipt_first_authority_v1.py tests/test_runless_*receipt*.py tests/test_runless_*gate*.py tests/test_runless_*prove*.py`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(runless): make GitHub receipt readback proof authority"`

---

### Task 4: Alternate Ephemeral Executor Entry Point

**Files:**
- Create: `runless_proof_plane/ephemeral_runner.py`
- Modify: `docs/runless-proof-plane-operations.md`
- Test: `tests/test_runless_ephemeral_runner_v1.py`

**Interfaces:**
- Consumes: serialized existing `ProofRequest`, environment-provided GitHub App credentials, exact candidate SHA, current scope lease.
- Produces: CLI/module entry point `python -m runless_proof_plane.ephemeral_runner --request-json <path>` that executes the same provider-independent orchestration and returns terminal JSON; no HTTP service and no Render dependency.

- [ ] **Step 1: Write failing ephemeral-runner tests**

Assert:
- runner accepts the existing request shape;
- exact candidate mismatch exits nonzero before proof commands;
- missing credentials fail closed;
- executor kind is metadata only;
- runner delegates to the same proof orchestration used by hosted Runless;
- no GitHub Actions path exists.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_runless_ephemeral_runner_v1.py`
Expected: FAIL because the entry point does not exist.

- [ ] **Step 3: Implement the ephemeral runner**

Build settings/GitHub App client from existing configuration, parse one proof request, call the shared provider-independent orchestration once, emit terminal JSON, and exit nonzero on terminal failure. Do not start FastAPI or require Render-specific environment values.

Update operations docs: Render is one executor; ephemeral sandbox is the recovery executor after terminal infra failure; both reuse the same proof identity and receipt authority.

- [ ] **Step 4: Run focused + full control-plane regression slice**

Run: `python -m pytest -q tests/test_runless_ephemeral_runner_v1.py tests/test_runless_provider_independent_frozen_state_v1.py tests/test_runless_provider_executor_v1.py tests/test_runless_receipt_first_authority_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(runless): add ephemeral provider-independent proof runner"`

---

### Task 5: Step-4 Recovery Certification Without Render

**Files:**
- No Step-4 product/code changes expected.
- Runtime artifact: one ephemeral Vercel sandbox/session only.
- Read/write authority: existing `runless-proof-receipts` ref and approved GitHub App gate.
- Existing candidate: `d06b4e39a12ae5772020a987a5e3a1767982602b` on PR #1529.

**Interfaces:**
- Consumes: completed Tasks 1–4, Step-4 proof plan `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step4.json`, live scope lease, unchanged Step-4 candidate.
- Produces: one exact terminal receipt, exact-head `runless-final-gate`, merged PR #1529, and sidecar freeze/readback token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP4_TRUST_QUORUM_ENGINE_FROZEN`.

- [ ] **Step 1: Verify Step 2A identity once**

Confirm PR #1529 head still equals `d06b4e39a12ae5772020a987a5e3a1767982602b`, current main remains the expected base or classify any drift before continuing, and the scope lease is live. Do not create a new proof identity.

- [ ] **Step 2: Create one ephemeral Vercel sandbox from the provider-independent Runless implementation**

Use one sandbox/session as compute only. Allow outbound GitHub access. Do not create a second hosted proof service or GitHub Actions workflow.

- [ ] **Step 3: Execute the exact Step-4 request once**

Run the same task/workstream/candidate/lease/authorization request through `ephemeral_runner`. Execute the exact plan commands:
- `python -m pytest -q tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
- `python -m pytest -q tests/test_devsystem_universal_sports_provider_registry_step2_v1.py tests/test_devsystem_universal_sports_field_router_step3_v1.py tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
- `python -m py_compile devsystem/universal_sports_trust_quorum_v1.py`

Expected terminal state: `MERGE_AUTHORIZED`, one read-back validated receipt, zero public probes, GitHub Actions disabled.

- [ ] **Step 4: Verify exact-head gate and merge only the certified SHA**

Confirm `runless-final-gate` success corresponds to the same candidate/receipt digest and approved App identity. Merge PR #1529 only if the head is unchanged.

- [ ] **Step 5: Execute immediate sidecar finalization and authoritative readback**

Build/write/read back the Step-4 freeze record and manifest transition using the existing Universal Sports bootstrap/finalization contract. Require `render_dependency=false`, `github_actions_fallback=0`, `legacy_registry_mutation=false`, exact candidate identity, merged-main identity, proof digest, canonical artifact map, and freeze token.

- [ ] **Step 6: Declare terminal completion only after readback**

Expected: Step 4 = `GREEN + FROZEN + IMPLEMENTED`; Steps 1–3 remain unchanged/frozen; no Render dependency was required for proof execution.

---

## Plan Self-Review

- **Spec coverage:** executor independence, sidecar frozen-state compatibility, Step 2A single-lane failover, deterministic identity, receipt authority, approved gate identity, alternate executor, Step-4 recovery, and provider-independent finalization are all mapped to Tasks 1–5.
- **Step scan:** each implementation task follows RED -> minimal implementation -> GREEN -> commit; recovery task performs one authoritative execution path only.
- **Type consistency:** Task 1 produces frozen-state verification consumed by Task 3 orchestration; Task 2 produces provider-neutral evidence/identity consumed by Task 3; Task 3 produces receipt-first authority consumed by Task 4/5; Task 4 exposes the alternate runner used in Task 5.
- **Review Focus:** all five high-risk conditions are pinned to explicit tests in Tasks 1–3.
- **Proportion:** implementation details are limited to exact interfaces and invariants; algorithm bodies remain with the implementer.

## Execution Method

Use **Native / executing-plans** in the current session. The tasks have sequential interface dependencies, and preserving the single authoritative Step-4 lane is more important than parallel implementation. Each task still receives its own TDD verification and commit checkpoint before proceeding.
