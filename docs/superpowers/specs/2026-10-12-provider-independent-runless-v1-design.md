# Provider-Independent Runless V1 — Design

Date: 2026-10-12
Project: API 2 / MONSTER control plane
Status: design approved in chat; written spec pending user review

## Intent

Decouple Runless proof execution from Render so exact-head certification can continue when any one hosting provider is unavailable, out of quota, or degraded, without weakening Step 2A, proof-before-merge, frozen-registry protection, receipt integrity, or Finalization Authority / 100% Convergence V1.

Success means:

- Render is optional compute, not proof authority.
- A proof may execute on any approved executor that satisfies the same deterministic contract.
- One authoritative proof identity exists per workstream/candidate; alternate executors may resume that same identity but may not create parallel proof lanes.
- The exact candidate SHA, proof plan, artifact map, dependency map, scope lease, and authorization identity are bound into the proof fingerprint.
- Proof evidence is persisted as an immutable terminal receipt and read back from GitHub before merge.
- GitHub Actions remains fallback count 0 for this design.
- Universal Sports sidecar finalization continues with render_dependency=false and legacy_registry_mutation=false.
- Existing frozen steps remain protected and are not reopened.

## Current Failure This Design Solves

Universal Sports Source + Finalization V1 Step 4 has correct implementation at candidate `d06b4e39a12ae5772020a987a5e3a1767982602b`, PR #1529. The existing Render-hosted Runless service rejects the proof because its deployed code still enforces a legacy registry/main identity assumption. The compatibility repair exists, but Render cannot deploy it because pipeline minutes are exhausted.

This exposes an architectural flaw: execution authority is effectively tied to one hosted service. The proof contract itself is already mostly provider-independent, but transport/execution is not.

## Decision

Adopt a receipt-first architecture:

1. **Proof identity is authoritative, executor is not.**
   - `proof_id` is derived from task_id, workstream, candidate_sha, lease_id, authorization_id, and proof fingerprint.
   - The executor label is metadata only and cannot alter proof semantics.

2. **GitHub receipt readback is the durable proof authority.**
   - Terminal receipts remain stored on the dedicated `runless-proof-receipts` ref.
   - A proof is merge-authorizing only after the receipt is written, read back, validated, and matched to the exact candidate and fingerprint.

3. **Executors are interchangeable compute surfaces.**
   - Supported initial executor classes: existing Render service and an ephemeral Vercel sandbox.
   - Future executors may be added if they implement the same executor contract.
   - No executor may weaken or skip the proof plan.

4. **One-lane Step 2A remains mandatory.**
   - Only one proof identity may be active for a candidate/workstream.
   - Switching executor after a terminal infrastructure failure resumes the same proof identity/fingerprint; it does not mint another lane.
   - Unchanged failed attempts are not replayed unless evidence or infrastructure state changed.

5. **Finalization remains provider-independent.**
   - Final freeze records continue to require `render_dependency=false`.
   - GitHub Actions fallback remains `0`.
   - Legacy registry mutation remains forbidden for Universal Sports Steps 1–6.

## Architecture

### A. Provider-Independent Proof Request

Introduce a serializable `ProviderIndependentProofRequest` envelope with:

- task_id
- workstream
- candidate_sha
- lease_id
- authorization_id
- expected_main_sha (optional existing field)
- proof_id
- proof_fingerprint
- executor_kind
- executor_instance_id

The first five fields preserve the existing request contract. `proof_id` and `proof_fingerprint` are computed centrally from candidate content and policy, not supplied as trusted arbitrary user input. Executor fields are informational and included in the receipt evidence trail.

### B. Frozen-State Verification Adapter

Separate frozen-state verification from executor hosting.

For Universal Sports sidecar-finalized workstreams, verification must:

- verify live `main` identity,
- verify inherited frozen artifact blobs against the authoritative current main tree,
- verify any candidate frozen deltas have an exact thaw grant,
- accept the Universal Sports sidecar finalization ledger as the authoritative finalization lineage for Steps 1–6,
- never mutate the legacy frozen registry just to align `source_main_sha`,
- fail closed on ambiguous or missing lineage.

Legacy workstreams continue using the existing legacy registry contract.

This is a compatibility adapter, not a weakening of frozen-state checks.

### C. Executor Contract

Create a narrow executor interface:

`execute(plan, workspace, context) -> EvidenceBundle`

Required executor behavior:

- checkout the exact candidate SHA,
- verify candidate identity before running commands,
- execute the exact proof-plan commands with configured timeout,
- execute required public probes only when specified,
- capture exit codes and evidence digests,
- return structured failure classification,
- perform no merge or freeze action directly.

Initial implementations:

- `HostedRunlessExecutor` — current service behavior.
- `VercelSandboxRunlessExecutor` — ephemeral sandbox used when hosted Runless infrastructure is unavailable.

### D. Receipt-First Authority

After successful execution:

1. build the same immutable Runless terminal receipt,
2. include candidate SHA, artifact/dependency maps, proof fingerprint, evidence digests, registry/sidecar identity, executor metadata, failure class NONE,
3. write to `runless-proof-receipts`,
4. read the exact receipt back from GitHub,
5. verify receipt digest and identity,
6. only then publish or satisfy `runless-final-gate`,
7. mark state `MERGE_AUTHORIZED`.

The receipt—not Render, Vercel, or another provider—is the durable authority.

### E. Gate Publication

Preserve the current protected-branch requirement: `runless-final-gate` from the approved GitHub App remains the visible merge gate.

The provider-independent path therefore separates:

- **execution**: any approved executor,
- **receipt authority**: GitHub receipt branch/readback,
- **gate publication**: approved GitHub App identity,
- **merge/finalization**: existing Finalization Authority sequence.

If direct App publication is unavailable from an alternate executor, the executor must return the validated receipt to the control-plane authority, which publishes the gate for that exact receipt digest. A generic commit status from an unrelated identity is not acceptable.

## Step 4 Recovery Flow

For the currently blocked Universal Sports Step 4:

1. Keep PR #1529 and candidate `d06b4e39a12ae5772020a987a5e3a1767982602b` unchanged.
2. Preserve the existing Step 4 proof plan and freeze token.
3. Use one Vercel sandbox as the replacement compute surface for the same authoritative proof identity.
4. Checkout the exact candidate and run the exact Step 4 proof commands.
5. Apply the already-designed sidecar-aware frozen verification semantics; do not mutate the legacy registry.
6. Produce the immutable terminal receipt.
7. Persist/read back the receipt from GitHub.
8. Publish/verify the exact-head `runless-final-gate` from the approved App identity.
9. Merge PR #1529 only if the exact candidate remains unchanged.
10. Immediately execute sidecar freeze + manifest readback using token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP4_TRUST_QUORUM_ENGINE_FROZEN`.
11. Declare GREEN + FROZEN only after authoritative readback.

## Anti-Loop / Failure Ownership

Provider failover is allowed only after a terminal infrastructure failure is classified.

Rules:

- no repeated polling of unfinished operations,
- no second executor while the first executor is still authoritative/pending,
- no duplicate receipt for unchanged proof identity,
- no retry after deterministic code/proof failure without a real patch/evidence change,
- executor transport failures are classified separately from proof failures,
- receipt identity collision fails closed.

## Security and Integrity Invariants

The design must preserve all of these:

- exact candidate SHA binding,
- exact current main binding,
- live scope lease validation,
- workstream match,
- proof-plan match,
- artifact/dependency blob map binding,
- deterministic proof fingerprint,
- immutable receipt digest,
- GitHub receipt readback,
- approved gate publisher identity,
- no merge before gate,
- no freeze before merged-main identity,
- no legacy registry mutation for Universal Sports Steps 1–6,
- no GitHub Actions fallback,
- no page/product runtime mutation by proof infrastructure.

## Files / Components Expected to Change

Implementation is expected to remain control-plane-only and likely touch:

- `runless_proof_plane/prove.py` — extract provider-independent orchestration and final authority handoff.
- `runless_proof_plane/executor.py` — define executor interface / hosted adapter.
- new provider-independent executor module under `runless_proof_plane/` or `devsystem/`.
- frozen verification adapter module for legacy registry vs Universal Sports sidecar lineage.
- receipt schema only if executor metadata cannot be added compatibly; prefer backward-compatible optional metadata.
- tests for provider equivalence, exact identity, anti-loop behavior, sidecar lineage, receipt readback, and fail-closed cases.
- docs/runless proof-plane operations documentation.

No sports-page product/runtime files should change.

## Testing Strategy

TDD is mandatory.

RED tests should cover:

- Render unavailable but Vercel executor succeeds with identical proof fingerprint.
- Alternate executor cannot alter candidate SHA or proof commands.
- same proof identity cannot run simultaneously on two executors.
- executor switch after terminal infrastructure failure reuses proof identity.
- Universal Sports sidecar lineage passes without legacy registry mutation.
- unreconciled/ambiguous frozen drift still fails closed.
- wrong lease fails closed.
- wrong main SHA fails closed.
- malformed/tampered receipt fails readback.
- duplicate receipt with mismatched identity fails closed.
- approved gate cannot be published for an unvalidated receipt.
- finalization record preserves render_dependency=false, github_actions_fallback=0, legacy_registry_mutation=false.

Regression tests must keep existing hosted Runless behavior green.

## Migration / Rollout

Phase 1: add provider-independent orchestration while preserving current hosted executor as default.

Phase 2: add Vercel sandbox executor and prove equivalence on the blocked Step 4 candidate.

Phase 3: update operations docs so executor selection is policy-driven and provider health aware.

Phase 4: future work may remove Render from any mandatory dependency list once provider-independent execution has multiple proven executors.

No big-bang replacement is required.

## Rejected Approaches

### Mutate the legacy frozen registry to match current main
Rejected because it could hide unreconciled frozen drift and violate frozen-registry protection.

### Use generic Runless dry-run certification
Rejected because it does not execute the Step 4 proof plan and cannot substitute for exact-candidate evidence.

### Use GitHub Actions fallback
Rejected because current architecture requires fallback count 0 and the goal is to remove provider coupling, not move it into CI.

### Stand up another always-on clone of Runless
Rejected as the primary design because it merely swaps one hosting dependency for another. Ephemeral interchangeable executors are cleaner.

## Acceptance Criteria

Provider-Independent Runless V1 is complete when:

- one exact proof identity can execute on at least two executor classes without semantic differences,
- successful evidence produces one deterministic terminal receipt,
- GitHub readback validates the exact receipt and digest,
- the approved `runless-final-gate` corresponds to that exact receipt/candidate,
- executor failover does not create duplicate proof lanes,
- Universal Sports sidecar lineage is accepted without legacy registry mutation,
- Step 4 can complete proof -> merge -> freeze with Render unavailable,
- all regression protections remain green.
