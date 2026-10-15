# Runless Execution Transport V1 Operations

## Authority

This transport is **not proof authority**. Runless V2 remains the only proof authority for new proofs. Supabase `runless_v2` remains durable execution/control-state authority, GitHub immutable receipts remain proof evidence, GitHub App `5204253` remains the only `runless-final-gate` publisher, and existing Finalization Authority remains the merge/freeze authority.

The transport must never create a parallel proof engine, local proof registry, GitHub Actions proof fallback, or special-case path for a sports page, PR, branch, or candidate.

## One connected execution lane

Use exactly one reusable named Vercel transport sandbox lane:

`api2-runless-transport`

The lane belongs to the existing `kyre-runless-proof` project. It carries authenticated HTTP requests only. It does not execute proof commands and it never owns Runless proof state.

Resolve the current authoritative production URL for `kyre-runless-proof` from Vercel at execution time. Do not hard-code a deployment URL into source, docs, proof plans, or receipts.

## Secret handling

`RUNLESS_PROOF_AUTH_TOKEN` is injected only as **command-scoped** environment data for operator-side client invocation. Connected ChatGPT execution does not export that token from Vercel.

Do not persist the token into the sandbox default environment, filesystem, snapshot, Git repository, proof receipt, logs, status rows, or chat output. The transport sandbox remains secretless at rest.

## Proof request procedure

1. Read the exact workstream/candidate authority and durable Runless state first.
2. If the same candidate already has an active proof, reuse its durable identity and do not submit another request.
3. If it already succeeded, return the existing receipt and gate evidence.
4. If it terminally failed, return the existing failure classification; classify the root cause before any replacement request.
5. Only when durable state proves that no proof exists may one authenticated `prove` request be sent.
6. The adapter posts the generic request to the existing Runless V2 `POST /prove` endpoint and returns the durable proof identity/state.
7. Transport interruption never becomes proof truth; durable Runless state remains authoritative.

## Interruption and anti-loop recovery

After any transport interruption, inspect **durable state first**. Never infer proof creation or completion from client timeout, sandbox lifetime, deployment state, or a percentage.

If durable state shows a proof exists, reuse it. If durable state still shows no proof exists, one controlled replacement transport invocation is allowed after the transport failure is classified. A **third blind retry** is forbidden unless new evidence changes the failure classification.

Transport failure does not become product/proof failure by assumption. Runless V2 durable state decides whether a proof exists and whether it is active, successful, or failed.

## Fencing and heartbeat

The existing Runless V2 lease and fencing generation remain authoritative. During a long proof sandbox execution, the proof service renews only the existing claim. It never acquires a second lease. A stale renewal fails closed before immutable receipt or gate publication. Recovery after lease expiry uses existing Runless claim semantics, which increment fencing generation and make prior stale writers invalid.

## Finalization handoff

A successful proof continues through the existing chain:

`proof -> immutable receipt -> App 5204253 runless-final-gate -> MERGE_AUTHORIZED -> expected-head merge -> merged-main provenance -> frozen-registry/finalization transaction -> canonical readback -> GREEN_FROZEN`

No manual user prompt is required between valid terminal transitions.

## Isolation

The transport repair does not mutate NBA PR `#1541`, Runless Dynamic Finalization Authority PR `#1544`, sports runtime/model/page files, or frozen registry state during implementation. Those PR identities are live certification baselines only, not constants in reusable transport code.

## Connected execution amendment — server-side Supabase transport

Implementation proved that MCP-created Vercel sandboxes do not inherit project secrets or OIDC credentials, while the connected Vercel tool intentionally does not reveal sensitive environment values. Therefore the permanent connected path is a server-side adapter, not secret export into a sandbox.

The connected caller invokes `runless_v2.request_proof_transport(...)` through the privileged Supabase connection. That function:

1. validates repository, candidate SHA, request identity, and a `kyre-runless-proof*.vercel.app` base URL resolved through Vercel;
2. serializes identical calls with a PostgreSQL advisory transaction lock;
3. returns an already-existing durable Runless proof before making any network call;
4. reads `runless_v2_transport_bearer` only inside Supabase Vault;
5. makes one synchronous authenticated HTTP POST to the existing `/prove` endpoint;
6. reads the resulting authoritative row from `runless_v2.proof_runs` and returns proof ID, native/projected state, fencing generation, receipt digest, gate ID, failure class, and execution identity;
7. exposes no bearer value to chat, source control, sandbox state, receipts, or logs.

`runless_v2.transport_client` remains the generic operator/client implementation, but it is no longer required to receive a secret through the ChatGPT sandbox boundary. Supabase is transport only; it does not replace the existing `/prove` executor or durable proof authority.
