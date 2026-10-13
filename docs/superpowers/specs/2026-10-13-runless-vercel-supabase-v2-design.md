# Runless V2 — Vercel + Supabase Durable Proof Authority

**Date:** 2026-10-13  
**Workstream ID:** `runless-vercel-supabase-v2`  
**Repository:** `kyrepeak/kyre-sports-ai`  
**Status:** Design approved in chat; written spec awaiting explicit review approval before implementation planning.

## Purpose

Move the Runless proof critical path off Render without weakening Step 2A, exact-head verification, proof-before-merge, frozen-registry protection, anti-loop protection, or the GitHub finalization ledger.

The migration must solve two concrete failures in the current Runless V1 architecture:

1. Render pipeline-minute exhaustion can block proof-host recovery.
2. Runless V1 stores active workstream ownership and proof status only in Python process memory. A proof that reaches `MERGE_AUTHORIZED` but never reaches `GREEN_FROZEN` can leave an in-memory workstream owner behind indefinitely, causing `RUNLESS_WORKSTREAM_BUSY` after otherwise-successful proof execution.

The target architecture is:

- **Vercel** for the Runless control API.
- **Vercel Sandbox** for short-lived candidate checkout and static proof execution.
- **Supabase Postgres** for durable Runless leases, proof state, request fingerprints, and mirrored receipt/status metadata.
- **GitHub App 5204253** for exact-head `runless-final-gate` publication and readback.
- **GitHub immutable proof receipts + finalization ledger** as final proof/freeze authority.
- **Render removed from the proof critical path.**
- **GitHub Actions proof fallback remains 0.**

This is a new infrastructure/control-plane workstream. It must not mutate the sports product/runtime/model implementation and must not modify the active Step-6 product PR while V2 is being built and certified.

## Current Context and Constraint

The current active sports program is `universal-sports-source-finalization-v1`.

- Steps 1–5 are already GREEN + FROZEN.
- Step 6 implementation lives on PR #1531.
- Step 6 candidate SHA is currently `1f270dcd8a76c4ac6f1576ded02a1b4c048286a4`.
- Step 6 is blocked only on an exact-head Runless proof.
- The existing Render proof plane is not to be used as the recovery or final proof path for this migration.

Runless V2 is therefore a prerequisite infrastructure workstream whose first production use will be the existing Step-6 candidate after V2 itself is certified.

## Non-Goals

This migration does **not**:

- redesign the sports pages;
- change provider-routing, quorum, source-receipt, canonical identity, or provider-health product logic;
- move the sports application runtime to Vercel;
- replace the GitHub finalization ledger;
- create a second proof authority that can independently certify candidates in parallel with Runless V1;
- enable GitHub Actions as proof fallback;
- implement the broader Step-7 Finalization Worker hardening beyond the minimum V2 closeout/readback integration needed to prevent stale proof ownership.

## Approved Architectural Direction

### 1. Vercel control API

Create a dedicated Vercel project named `kyre-runless-proof` rather than overloading the existing `kyre-sports-finalizer` project.

The control API remains Python/FastAPI and preserves the current Runless request contract where practical:

- `GET /health`
- `POST /prove`
- `GET /status/{proof_id}`
- `GET /receipts/{proof_id}`
- a minimal authenticated closeout endpoint for durable terminal-state transition after immutable merge/freeze evidence exists

The API must be stateless with respect to active proof ownership. No correctness-critical state may live only in `app.state`, module globals, or process memory.

### 2. Vercel Sandbox proof worker

Runless V1 currently creates a temporary Git checkout for the exact candidate SHA and shells out to commands such as `pytest` and `py_compile`. V2 must preserve that behavior rather than pretending a regular serverless function is a general-purpose build runner.

For each proof requiring static execution, the Vercel API creates one short-lived, non-persistent Vercel Sandbox. The Sandbox:

1. receives the exact candidate identity and short-lived GitHub installation credential required for checkout;
2. checks out the exact candidate SHA;
3. verifies checked-out HEAD equals the requested candidate SHA;
4. loads the candidate's Runless proof plan;
5. executes only validated allowlisted proof commands from that plan;
6. captures deterministic evidence digests and exit status;
7. returns evidence to the control API;
8. is destroyed after the proof attempt.

Sandbox state is never proof authority and must not persist between requests.

Default properties:

- non-persistent;
- one Sandbox per authoritative proof attempt;
- bounded execution duration based on the proof plan with a hard platform maximum;
- no automatic retry loop;
- no background polling loop;
- network access restricted to only what the proof requires;
- no unrelated repo mutations from the Sandbox.

### 3. Supabase durable Runless state

Use the existing Supabase project `jqajcdckalsfizbvngiu`, but isolate V2 state in a dedicated schema, proposed as `runless_v2`.

Supabase is the durable **control-state authority**, not the final immutable freeze authority.

Proposed tables:

#### `runless_v2.proof_runs`

One row per deterministic proof ID.

Required fields include:

- `proof_id` primary key;
- `task_id`;
- `workstream`;
- `candidate_sha`;
- `expected_main_sha`;
- `scope_lease_id`;
- `authorization_id`;
- `request_fingerprint` unique within the workstream contract;
- `proof_fingerprint`;
- `state`;
- `failure_class`;
- `detail`;
- `fencing_generation`;
- `receipt_digest`;
- `gate_check_run_id` when available;
- `created_at`;
- `updated_at`;
- `terminal_at`.

#### `runless_v2.workstream_leases`

One current execution owner per workstream.

Required fields include:

- `workstream` primary key;
- `owner_proof_id`;
- `lease_token` UUID;
- `fencing_generation` bigint;
- `acquired_at`;
- `renewed_at`;
- `expires_at`;
- `updated_at`.

Every new ownership generation increments monotonically. Any stale worker carrying an older generation must be rejected from state transitions or gate publication.

#### `runless_v2.failed_fingerprints`

Durable anti-loop memory for deterministic failures.

Required fields include:

- `request_fingerprint` primary key;
- `workstream`;
- `proof_id`;
- `failure_class`;
- `detail_digest`;
- `created_at`.

An unchanged failed request must remain blocked until the evidence state actually changes according to existing anti-loop semantics.

#### `runless_v2.receipt_mirrors`

Optional durable operational mirror for status/recovery. GitHub remains the immutable receipt authority.

Required fields include:

- `proof_id` primary key;
- `receipt_digest`;
- `candidate_sha`;
- `workstream`;
- `receipt_json` JSONB;
- `github_receipt_ref`;
- `github_receipt_path`;
- `created_at`.

The mirror is useful for `/status` and recovery but cannot replace GitHub readback when certifying GREEN + FROZEN.

### 4. Atomic database operations

All ownership and state transitions must happen through transaction-safe SQL functions/RPCs rather than client-side read-then-write races.

Required operations:

#### `claim_workstream`

- accepts `workstream`, `proof_id`, requested TTL, and request fingerprint;
- rejects a different unexpired owner;
- treats the same proof/request as idempotent;
- allows takeover only after lease expiry or an explicit terminal release;
- increments `fencing_generation` for a new ownership generation;
- returns the lease token and generation.

#### `renew_workstream`

- succeeds only when `proof_id`, `lease_token`, and `fencing_generation` all match;
- fails closed if ownership changed or expired beyond the permitted renewal policy.

#### `advance_proof_state`

- requires the expected current state;
- requires the current lease token/generation for states that mutate active proof execution;
- allows only legal state-machine transitions;
- is compare-and-swap style and atomic.

#### `record_failure_and_release`

In one transaction:

- records the deterministic failed fingerprint;
- marks the proof failed;
- clears active execution ownership if and only if token/generation still match.

#### `record_merge_authorized_and_release_execution`

On successful pre-merge proof:

- records `MERGE_AUTHORIZED` durably;
- records proof/receipt/gate evidence;
- releases the ephemeral **execution lease** in the same transaction.

Releasing the execution lease does **not** allow a different candidate to become authoritative for the same workstream automatically. `proof_runs` still records an outstanding authorized proof.

A subsequent `/prove` call for the same workstream must therefore behave as follows:

- same request fingerprint / same candidate: idempotently reuse the authorized proof;
- different candidate while an authorized proof has not been explicitly closed, superseded, or invalidated: fail closed with a deterministic workstream-authority conflict;
- terminal failed proof with changed evidence: may create a new ownership generation under normal Step 2A rules.

This separates **process execution ownership** from **program authority ownership** and prevents both ghost RAM locks and unauthorized parallel proofs.

### 5. Durable state machine

Preserve the existing Runless state order:

`IDENTIFY → LOCK_2A → FINGERPRINT → REUSE_OR_PROVE → PUBLIC_CHECK_IF_REQUIRED → RECEIPT → RUNLESS_FINAL_GATE → MERGE_AUTHORIZED → MERGED → POST_MERGE_VERIFY → FREEZE → READ_BACK → GREEN_FROZEN`

`FAILED` remains a terminal failure state.

The first V2 `/prove` request stops at `MERGE_AUTHORIZED`, matching existing Runless pre-merge semantics.

The post-merge/freeze closeout path does **not** perform the product merge or invent frozen state. Instead, after external merge + GitHub finalization-ledger persistence occur, an authenticated closeout request must:

1. verify the proof ID/candidate/workstream identity;
2. verify the expected merged-main identity;
3. independently read back the GitHub finalization ledger/freeze record;
4. verify the expected freeze token, proof digest, candidate SHA, merged-main SHA, and manifest chain;
5. transition `MERGED → POST_MERGE_VERIFY → FREEZE → READ_BACK → GREEN_FROZEN` durably;
6. leave no active execution lease.

This closeout exists to make Runless lifecycle state accurate and recoverable; it does not replace the finalization ledger as freeze authority.

### 6. Exact-head proof and GitHub authority

V2 must preserve all current exact-head semantics:

- exact candidate commit identity;
- exact `main` identity when requested;
- live external scope lease validation;
- Step 2A single-authority authorization;
- frozen-registry/ledger protection;
- candidate/dependency/artifact fingerprinting;
- deterministic static proof evidence;
- public probes only when the plan requires them;
- immutable receipt generation;
- GitHub App check publication;
- independent check readback.

The check remains:

- name: `runless-final-gate`;
- GitHub App ID: `5204253`;
- exact candidate SHA required;
- conclusion must be `success` before merge authorization.

The existing `vercel_finalizer/app.py` already demonstrates GitHub App authentication, exact-head check publication, and independent readback. V2 should reuse/refactor those primitives rather than create a new check publisher.

### 7. V2 authority marker and V1 deprecation

The system must not create two independent proof authorities.

Cutover therefore uses an explicit V2 authority contract in the repository plus durable V2 receipt evidence.

After cutover:

- only V2 proof receipts are accepted for new Runless proofs;
- a `runless-final-gate` check by itself is insufficient for V2-controlled workstreams unless its associated V2 proof ID/receipt digest is present and read back from the approved V2 durable path;
- Render V1 is treated as legacy/non-authoritative even if its old endpoint remains technically reachable;
- no new proof request is sent to Render V1;
- V1 may be decommissioned later as a separate housekeeping action.

This avoids making successful migration dependent on spending Render build minutes or successfully redeploying the old service.

### 8. Authentication and secrets

The V2 proof API must not be an unauthenticated mutation endpoint.

Secrets must live only in platform secret stores, never committed to the repository or stored in public Supabase tables.

Required secret classes:

- GitHub App ID/installation/private key for App 5204253;
- Vercel-to-Supabase server credential;
- proof API caller authentication secret or signed request key;
- optional GitHub webhook secret if webhook resume is retained.

Recommended request authentication:

- `Authorization: Bearer <RUNLESS_PROOF_AUTH_TOKEN>` or an HMAC-signed request;
- constant-time verification;
- replay-resistant request identity using deterministic proof ID plus authorization ID;
- secrets stored in Vercel encrypted environment variables and, where a Supabase-originated HTTP caller is used, Supabase Vault.

No browser/client application receives privileged Supabase or GitHub credentials.

### 9. Supabase security

The `runless_v2` schema is server-side control-plane data.

Requirements:

- public/anon direct writes denied;
- RLS or schema permissions deny untrusted clients by default;
- atomic mutation functions exposed only to the V2 server credential;
- read-only operational views may be added later if useful, but are not required for the migration;
- database functions validate state transitions internally rather than trusting caller-provided status;
- all timestamps use database UTC time for lease expiry decisions.

### 10. Failure classification and recovery

Runless V2 must classify failures before strategy changes.

Minimum categories preserved or extended from V1:

- `STATIC_PROOF`;
- `PUBLIC_PROOF`;
- `INFRA`;
- Step 2A identity/lease conflicts;
- frozen-registry/ledger conflicts;
- GitHub App/auth failures;
- Sandbox provisioning/execution failures;
- Supabase durable-state failures;
- illegal state transitions;
- stale fencing-generation writes.

Rules:

- deterministic proof failure records a failed fingerprint and blocks unchanged retries;
- infrastructure failure may release the execution lease without marking the request fingerprint as a deterministic product failure when evidence was never executed or completed;
- no blind retry loop;
- no repeated polling of the same unfinished operation;
- same-proof idempotent retry returns/reuses durable state where safe;
- stale worker writes fail due to fencing-generation mismatch.

### 11. Idempotency

The deterministic proof ID continues to derive from stable request identity including task/workstream/candidate/lease/authorization fields.

Idempotency rules:

- same proof ID + same fingerprint returns the existing durable proof state;
- same proof ID with conflicting identity is an integrity failure;
- an already-published valid exact-head gate may be reused only when the corresponding V2 receipt identity/digest also matches;
- immutable GitHub receipt collision with different identity fails closed;
- Vercel/Supabase retries must never create duplicate authoritative proof runs.

### 12. Performance and cost discipline

The Vercel API remains lightweight. Expensive command execution happens only inside an ephemeral Sandbox and only when reusable immutable evidence is unavailable.

Performance rules:

- no Sandbox is created for an already-reusable successful exact proof;
- one Sandbox per authoritative proof attempt;
- Sandbox is destroyed promptly after completion;
- dependency installation is minimized and should reuse the repository's existing dependency definitions rather than introduce a second package graph;
- proof-plan command timeouts remain authoritative and bounded;
- no continuous worker is required;
- no Render minutes are consumed by V2.

### 13. Migration / cutover phases

#### Phase A — schema and adapter

- add `runless_v2` Supabase schema/tables/functions;
- add repository-side durable state adapter;
- add tests for lease claim, TTL expiry, fencing, state transitions, idempotency, failed fingerprint blocking, and concurrent claim rejection.

#### Phase B — Vercel worker portability

- add Vercel FastAPI entrypoint/project config for Runless V2;
- add Vercel Sandbox executor implementing the same validated command semantics as current `CandidateWorkspace` + `execute_static_slice`;
- reuse/refactor GitHub App primitives from the existing Runless/Vercel finalizer code;
- keep proof authority disabled until certification tests pass.

#### Phase C — non-authoritative certification

Prove without publishing the production gate that:

- cold starts do not lose status;
- API restarts do not strand workstream ownership;
- simultaneous same-workstream claims yield one owner;
- expired lease takeover increments fencing generation;
- stale worker writes are rejected;
- same proof retry is idempotent;
- deterministic failed fingerprints block unchanged retries;
- candidate checkout is exact SHA;
- static evidence matches V1 semantics;
- immutable receipt construction is deterministic.

#### Phase D — authority cutover

- enable V2 proof authority;
- publish the V2 authority contract/marker;
- verify GitHub App 5204253 can publish and read back `runless-final-gate` from Vercel V2;
- stop sending new proofs to Render V1;
- verify finalization requires matching V2 receipt identity, not merely a check name.

#### Phase E — Step-6 completion

Using the existing authoritative Step-6 path only:

1. fresh-read main, PR #1531 head, registry/ledger identity, and external scope lease;
2. renew/replace the external Step-6 scope lease once if it legitimately expired;
3. send exactly one Step-6 proof request through V2;
4. require exact-head `runless-final-gate` success from App 5204253;
5. independently read back the V2 proof receipt/digest;
6. merge PR #1531 only if all identities still match;
7. write Step-6 finalization-ledger revision 6 using existing canonical hash semantics;
8. independently read back the ledger/freeze record;
9. close out the V2 proof lifecycle to `GREEN_FROZEN` from immutable evidence;
10. report Step 6 GREEN + FROZEN only after all readbacks succeed.

### 14. Testing contract

At minimum, implementation tests must cover:

#### Supabase durable ownership

- first claim succeeds;
- concurrent second owner fails;
- same proof re-claim is idempotent;
- expired lease may be taken over;
- takeover increments fencing generation;
- stale generation cannot advance proof state;
- terminal failure records fingerprint and releases execution lease atomically;
- `MERGE_AUTHORIZED` records evidence and releases execution lease atomically;
- a different candidate is still blocked while an outstanding authorized proof owns workstream authority.

#### Durable state machine

- only legal transitions succeed;
- compare-and-swap expected-state mismatch fails;
- process restart/cold start does not lose state;
- `/status` reads Supabase, not process memory;
- closeout cannot invent `GREEN_FROZEN` without GitHub ledger readback.

#### Sandbox executor

- checks out exact candidate SHA;
- rejects stale/mismatched checkout;
- executes only validated allowlisted commands;
- captures deterministic stdout/stderr digests;
- classifies nonzero exit as static proof failure;
- classifies timeout/infrastructure separately;
- destroys Sandbox after completion.

#### GitHub proof authority

- correct App ID 5204253;
- exact candidate SHA on check run;
- check name `runless-final-gate`;
- success only after receipt persistence;
- independent check readback required;
- V2 receipt identity/digest must match the accepted gate;
- old Render-only check without valid V2 receipt is insufficient after cutover.

#### Regression protection

- GitHub Actions proof fallback remains 0;
- Render dependency remains false;
- sports product/runtime/model files remain outside this migration's mutation scope;
- existing finalization ledger semantics are preserved;
- existing frozen artifacts are not silently rewritten.

## Acceptance Criteria

Runless V2 is ready for authoritative use only when all of the following are true:

1. Vercel hosts the Runless V2 FastAPI control endpoint.
2. Vercel Sandbox performs exact-candidate static proof execution.
3. Supabase durably stores workstream ownership, proof state, failed fingerprints, and operational receipt metadata.
4. No correctness-critical active state depends on one Python process lifetime.
5. Workstream lease TTL and fencing prevent stale-owner resurrection.
6. Same-proof retries are idempotent.
7. Different-candidate parallel proof authority is blocked.
8. App 5204253 publishes exact-head `runless-final-gate` only after successful V2 proof.
9. A matching V2 receipt digest is required for authoritative proof acceptance.
10. GitHub immutable receipt/finalization ledger remains final proof/freeze authority.
11. Render is absent from the proof critical path.
12. GitHub Actions fallback remains 0.
13. A cold start or deployment does not require manual lock clearing.
14. Step 6 can complete proof → merge → ledger freeze → durable closeout without contacting Render.

## Rollback

Before V2 authority cutover, rollback is simply disabling the V2 proof-authority flag and making no production proof requests through it.

After cutover, rollback must fail closed rather than silently return to Render V1. If V2 becomes unavailable:

- do not send new authoritative proofs to Render;
- do not use GitHub Actions unless the user explicitly authorizes a separate emergency exception;
- preserve existing V2 durable state and immutable GitHub receipts;
- repair or redeploy V2, then resume from Supabase/GitHub truth.

No rollback path may invalidate already-frozen GitHub ledger entries.

## Implementation Boundaries

The implementation plan may introduce new files/modules for:

- Supabase migration(s) under the repository's migration conventions;
- a `runless_v2` state adapter/client;
- a Vercel Sandbox executor;
- Vercel entrypoint/config for `kyre-runless-proof`;
- V2 authority/cutover contract;
- unit/integration tests.

Existing Runless V1 code should be refactored only where sharing deterministic proof/GitHub primitives reduces duplication without reopening unrelated legacy startup workers.

PR #1531 and its seven Step-6 product/proof-plan files remain outside this migration branch's mutation scope until V2 certification is complete and the existing Step-6 workstream resumes.

## Final Design Decision

Use **Vercel FastAPI + ephemeral Vercel Sandbox + Supabase durable state + GitHub App/ledger authority**.

This preserves the current Runless proof semantics while removing Render build-minute dependency and eliminating stale process-memory workstream locks as a correctness requirement.
