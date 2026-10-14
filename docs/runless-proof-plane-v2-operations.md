# Runless Proof Plane V2 Operations

## Permanent authority rule

Runless V2 is the only authority for new proofs after cutover. Its execution/control state is durable in the `runless_v2` Supabase schema; the immutable GitHub proof receipt, exact-head `runless-final-gate` from **App 5204253**, and GitHub Finalization Ledger V2 remain the terminal proof/freeze evidence.

Render V1 becomes **LEGACY_NON_AUTHORITATIVE** at cutover. **No new proof request is sent to Render V1.** GitHub Actions fallback remains 0. Neither Render nor GitHub Actions may silently become a substitute proof authority.

## Safe deployment sequence

The dedicated Vercel project is `kyre-runless-proof`. First deployment must use `RUNLESS_AUTHORITY_ENABLED=0`. This keeps `/prove` and `/closeout` fail-closed while health, authentication, Supabase connectivity, durable reads, and the Vercel Sandbox execution path are certified.

Do not set `RUNLESS_AUTHORITY_ENABLED=1` until every item in `devsystem/contracts/runless-vercel-supabase-v2.json` certification matrix is independently GREEN. Enabling authority is a cutover action, not a debugging shortcut.

## Step 2A and single authority

Every proof begins with one task, one workstream, one candidate SHA, one external scope lease, one authorization ID, and one durable proof identity. Supabase serializes workstream execution claims and records an outstanding `MERGE_AUTHORIZED` proof as program authority even after its ephemeral execution lease is released.

A **same proof** request is idempotent and may reuse exact durable/immutable evidence. A **different candidate** is rejected while an outstanding authorized proof owns the workstream. There is no parallel second authority.

## Durable leases and fencing

Workstream execution ownership lives in Supabase, not process RAM. New ownership after expiry increments the **fencing generation**. Every active mutating transition carries the lease token and fencing generation. A **stale fence** must fail closed before receipt/gate state can be mutated.

Lease expiry is decided by database UTC time. Cold start or Vercel function replacement must not lose proof status or strand a ghost owner because status and ownership are read back from Supabase.

## Vercel Sandbox

Static proof commands run in one short-lived, non-persistent **Vercel Sandbox** per authoritative proof attempt. It checks out the exact candidate SHA, verifies `git rev-parse HEAD`, loads the candidate proof plan, executes only allowlisted commands, hashes stdout/stderr, and is destroyed in `finally`.

Do not create a second Sandbox as an automatic retry. Classify the terminal result first. Deterministic proof failures enter durable anti-loop memory; infrastructure failure releases execution ownership without manufacturing a deterministic product failure.

## Authentication and secrets

`POST /prove`, `GET /status/{proof_id}`, `GET /receipts/{proof_id}`, and `POST /closeout` require the Runless proof bearer token. Authentication must fail before any mutation. Supabase service credentials and the GitHub App private key stay only in encrypted platform secret storage and are never printed in logs, receipts, status descriptions, repository files, or chat.

## Non-authoritative certification matrix

With `RUNLESS_AUTHORITY_ENABLED=0`, certify exactly once per evidence identity:

- **cold start** status recovery from Supabase;
- simultaneous same-workstream claims have a single winner;
- expired lease takeover increments fencing generation;
- stale fence writes are rejected;
- same proof idempotency;
- different candidate outstanding-authority rejection;
- deterministic failure anti-loop behavior;
- exact candidate checkout in the Vercel Sandbox;
- Sandbox cleanup on success and failure;
- API auth failure occurs before mutation;
- zero production `runless-final-gate` publication while authority is disabled.

If one item fails, classify and patch that root cause before continuing. Do not repeatedly poll or blindly retry the same unfinished operation.

## Activation

Only after the full certification matrix is GREEN:

1. enable V2 authority for the exact certified deployment/config;
2. submit one self-proof for `runless-vercel-supabase-v2-cutover`;
3. require immutable GitHub receipt readback plus exact candidate `runless-final-gate` success from App 5204253;
4. merge only that certified candidate;
5. verify merged-main identity and deploy/promote the merged build;
6. persist/read back finalization evidence for `RUNLESS_VERCEL_SUPABASE_V2_CUTOVER_FROZEN`;
7. close out durable state to **GREEN + FROZEN**.

A green check alone is never enough.

## Closeout and GREEN + FROZEN

`POST /closeout` does not invent merge or freeze truth. It independently reads the GitHub finalization record and manifest chain, binds workstream/freeze token/candidate/proof digest/merged-main SHA, and only then advances durable lifecycle state through `MERGED → POST_MERGE_VERIFY → FREEZE → READ_BACK → GREEN_FROZEN`.

A successful database write without matching GitHub readback is not **GREEN + FROZEN**.

## Recovery

For a cold start, redeploy, or transient Vercel/Supabase incident, recover from durable Supabase proof state plus immutable GitHub receipt/finalization truth. Do not reconstruct authority from local RAM, a stale browser session, an old Render status, or a check run without its matching V2 receipt identity.
