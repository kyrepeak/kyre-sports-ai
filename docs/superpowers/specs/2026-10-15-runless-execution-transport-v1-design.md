# Runless Execution Transport V1 — Design

**Date:** 2026-10-15  
**Status:** Proposed for review  
**Repository:** `kyrepeak/kyre-sports-ai`  
**Authoritative repair branch:** `api2-runless-execution-transport-v1`  
**Base main:** `e064907f7c03b355a8b7d4160b0027e3f4ad9f22`

## 1. Purpose

Remove the API 2 / MONSTER control-plane dead end where the connected execution environment can diagnose Runless V2 durable state but cannot initiate the already-existing authenticated Runless proof API.

This repair MUST expose a generic, safe, idempotent execution transport for all future Runless workstreams. It MUST NOT create a second proof engine, a second authority, a GitHub Actions proof fallback, or a special-case path for the current NBA/Runless candidate.

The existing Runless V2 proof authority remains authoritative.

## 2. Confirmed Existing Architecture

Runless V2 already exposes the required proof entrypoint:

- `POST /prove` — authenticated proof execution.
- `GET /status/{proof_id}` — durable proof state.
- `GET /receipts/{proof_id}` — durable receipt mirror.
- `POST /closeout` — validated GREEN + FROZEN closeout.

`POST /prove` already executes `execute_proof_request(...)` against:

- Supabase `runless_v2` durable state;
- existing Step 2A validation;
- workstream leases and fencing generations;
- the existing Vercel Sandbox proof executor;
- immutable GitHub proof receipts;
- GitHub App `5204253` exact-head `runless-final-gate` publication.

Therefore this design does **not** introduce another executor. The repair is an execution-transport adapter around the existing API.

## 3. Current Root Cause

The current ChatGPT/API 2 tool surface can directly inspect GitHub and Supabase durable state, and it can manage Vercel resources, but there is no stable reusable operation that converts a validated Step 2A request into exactly one authenticated call to the existing Runless V2 `POST /prove` API.

The result is a capability gap:

`PROOF_NOT_CREATED` can be diagnosed but not cleanly transitioned to an authoritative proof from the same connected execution environment.

## 4. Chosen Architecture

Create a **stateless transport client** and use one reusable **Vercel named sandbox transport lane** as the connected execution bridge.

Flow:

`ChatGPT/API 2`
→ `Vercel connected execution tool`
→ `named transport sandbox`
→ `runless_v2.transport_client`
→ existing authenticated `POST /prove`
→ existing Runless V2 authority
→ existing short-lived proof sandbox
→ receipt
→ App 5204253 `runless-final-gate`
→ existing Finalization Authority
→ frozen-registry closeout.

The named transport sandbox is **not proof authority** and does not run proof commands itself. It only carries authenticated HTTP requests to the existing Runless V2 service.

If the named transport sandbox is stopped, it may be resumed/recreated without changing proof identity because proof identity and workstream authority remain in Supabase.

## 5. Step 2A Authority

Exactly one repair mutation path is authorized:

- branch: `api2-runless-execution-transport-v1`
- future PR: one PR from this branch only
- no mutation to NBA PR `#1541`
- no mutation to Runless Dynamic Finalization Authority PR `#1544` while the transport repair is built
- no duplicate transport branch, PR, deployment, proof request, or lease

The repair workstream is separate from the blocked Step-1 proof workstream. After the transport repair is certified, the original Step-1 workstream resumes at its exact current candidate.

## 6. Transport Client Contract

Add a generic module conceptually equivalent to:

```text
request_runless_proof(
    repository,
    workstream,
    task_id,
    candidate_sha,
    lease_id,
    authorization_id,
    expected_main_sha=None,
)
```

The implementation will live in the repository and invoke the existing Runless V2 HTTP API. It will not duplicate proof validation or proof execution logic.

Required client operations:

1. `request` — invoke `POST /prove` exactly once for one request identity.
2. `status` — read `GET /status/{proof_id}`.
3. `receipt` — read `GET /receipts/{proof_id}`.

The client must emit machine-readable JSON only. It must never print bearer tokens, GitHub App keys, Supabase credentials, or decrypted secrets.

## 7. Secret Handling

The existing `RUNLESS_PROOF_AUTH_TOKEN` remains the proof API credential.

For connected execution:

- resolve the token from the existing Vercel project secret store;
- inject it only as command-scoped environment data when executing the transport client;
- do not write the token into the repository, sandbox filesystem, proof receipt, logs, status rows, or chat output;
- do not persist the token into a sandbox snapshot.

The transport sandbox itself remains secretless at rest.

## 8. Endpoint Resolution

Do not hard-code a PR, branch, candidate, NBA page, or current deployment URL.

The adapter resolves the active Runless V2 service from the existing `kyre-runless-proof` Vercel project and targets its authoritative production service endpoint.

The request payload remains generic and is validated by the existing Runless V2 service against GitHub and Supabase authority.

## 9. Idempotency and Duplicate Protection

Runless V2 remains the source of truth for idempotency.

Existing database protections already provide:

- primary-key proof identity;
- unique `(workstream, request_fingerprint)` protection;
- workstream-level transactional/advisory serialization;
- one active workstream lease;
- monotonically increasing fencing generation on authority recovery;
- stale-fence rejection;
- outstanding `MERGE_AUTHORIZED` authority conflict rejection.

The transport client MUST NOT implement a competing local proof registry.

Repeated identical client requests are allowed only to recover/read the same durable proof. They must not create another proof identity.

Concurrent identical requests must converge on one durable proof through Runless V2 database serialization.

## 10. Durable State Projection

The adapter exposes a stable external execution-state projection without replacing the native Runless state machine.

Mapping:

- `REQUESTED` ← Runless `IDENTIFY`
- `QUEUED` ← `2A_LOCK`, `FINGERPRINT`
- `RUNNING` ← `REUSE_OR_PROVE`, `PUBLIC_CHECK_IF_REQUIRED`, `RECEIPT`, `RUNLESS_FINAL_GATE`
- `SUCCEEDED` ← `MERGE_AUTHORIZED`, `MERGED`, `POST_MERGE_VERIFY`, `FREEZE`, `READ_BACK`, `GREEN_FROZEN`
- `FAILED` ← `FAILED`

Native Runless state remains authoritative and is always returned beside the projected state.

## 11. Heartbeat and Abandonment

The current durable workstream lease remains the execution heartbeat authority.

While an authoritative proof is executing, the existing lease must be renewed periodically using the existing fencing generation. The proof service will receive the smallest possible heartbeat hardening needed so that a long sandbox command does not silently outlive durable ownership.

Rules:

- renew before lease expiry while the proof executor is active;
- renewal uses the current lease token + fencing generation only;
- a stale/failed renewal fails closed;
- no second proof is spawned by heartbeat failure;
- expired ownership may be recovered only through the existing claim/recovery semantics, which increment fencing generation;
- the prior stale fence can never publish a receipt or gate.

No new lease model is introduced.

## 12. Transport Failure Recovery

A client/network/sandbox transport failure does not imply proof failure.

Recovery sequence:

1. read exact durable Runless state for the requested candidate;
2. if proof exists and is active, do not submit another proof;
3. if proof exists and succeeded, return its receipt;
4. if proof exists and failed, return its terminal failure classification;
5. if no proof exists, one controlled replacement transport invocation is allowed;
6. if the workstream lease is stale/expired, existing Runless fencing semantics decide authority recovery;
7. a third blind retry is forbidden without new evidence.

## 13. Exact-Candidate Protection

The existing Runless preflight remains mandatory.

The service must reject:

- stale candidate SHA;
- wrong task/workstream binding;
- missing or mismatched proof plan;
- invalid external scope lease;
- stale expected-main identity when required;
- stale fencing generation;
- conflicting outstanding workstream authority.

The transport client cannot bypass those checks.

## 14. Response Contract

The transport layer returns enough data for the connected execution environment to anchor one authoritative chain:

```json
{
  "proof_id": "...",
  "candidate_sha": "40-hex",
  "state": "native Runless state",
  "transport_state": "REQUESTED|QUEUED|RUNNING|SUCCEEDED|FAILED",
  "fencing_generation": 1,
  "receipt_digest": "optional",
  "gate_check_run_id": 123,
  "execution_identity": "transport invocation / proof execution identity when available"
}
```

If an execution identity is not available before completion, `proof_id` + fencing generation remains the durable execution authority and the transport invocation identity is diagnostic only.

## 15. Finalization Handoff

Successful proof execution must continue using existing authority:

proof success
→ immutable receipt
→ App 5204253 `runless-final-gate`
→ exact SHA readback
→ `MERGE_AUTHORIZED`
→ expected-head protected merge
→ merged-main provenance verification
→ frozen-registry/finalization transaction
→ canonical readback
→ lease release
→ `GREEN_FROZEN`.

The transport adapter must not fork or reimplement Finalization Authority.

## 16. Required Test Matrix

The repair is not certifiable until all are proven:

1. no proof → exactly one durable proof;
2. repeated identical request → same proof;
3. active proof → no duplicate;
4. successful proof → same receipt returned;
5. stale candidate → rejected;
6. wrong workstream/task → rejected;
7. stale fencing generation → rejected;
8. transport failure → fail closed and durable-state recovery path used;
9. concurrent identical requests → exactly one durable proof;
10. successful proof → exact-head `runless-final-gate` from App 5204253;
11. gate cannot publish for a different SHA;
12. NBA PR `#1541` remains untouched.

Additional heartbeat tests:

13. active execution renews the existing lease;
14. stale heartbeat/fence cannot publish receipt or gate;
15. recovered ownership increments fencing generation and preserves one authority.

## 17. Live Certification Case

Only after the generic transport repair itself is proven safe, use the blocked Runless Dynamic Finalization Authority V1 Step-1 candidate as the first live certification case:

- workstream: `runless-dynamic-finalization-authority-v1`
- PR: `#1544`
- candidate: `e8f833d761b809206c6ac67a245e388f6a225098`

Current known state before certification:

- proof: none;
- receipt: none;
- active Runless lease: none;
- final gate: not created;
- failure classification: `PROOF_NOT_CREATED`.

The first live transport request must create exactly one authoritative proof for this exact candidate, then continue the existing finalization chain to genuine GREEN + FROZEN.

These live values are certification inputs only and MUST NOT be hard-coded into the adapter.

## 18. Rollback

Rollback is simple because the adapter owns no proof authority:

- stop using the transport sandbox/client;
- leave Runless V2 `/prove`, Supabase durable authority, GitHub receipts, gate publisher, and finalization ledger unchanged;
- any already-created proof remains recoverable from durable Runless state.

No proof data migration is required to remove the adapter.

## 19. Non-Goals

This repair does not:

- redesign Runless V2;
- replace Supabase;
- replace Vercel proof sandbox execution;
- create a GitHub Actions proof fallback;
- modify sports models/pages;
- change NBA PR `#1541`;
- merge or rewrite PR `#1544`;
- weaken exact-head, scope-lease, fencing, frozen-registry, or proof-before-merge requirements.

## 20. Success Criteria

The capability gap is permanently closed when the connected API 2 / MONSTER execution environment can safely request one generic Runless proof through the existing V2 authority, recover from transport interruption without duplicating proof authority, and drive the same exact candidate through receipt, final gate, merge, finalization readback, and GREEN + FROZEN without manual transport workarounds.