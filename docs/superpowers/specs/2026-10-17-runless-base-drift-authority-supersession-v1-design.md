# Runless Base-Drift Authority Supersession V1 — Design Specification

Date: 2026-10-17
Status: Design approved; implementation not yet authorized
Workstream: `runless-base-drift-authority-supersession-v1`

## Purpose

Add one audited, fail-closed recovery path for a Runless V2 workstream whose exact candidate already reached `MERGE_AUTHORIZED`, but GitHub can no longer merge that candidate because `main` advanced and the PR branch must absorb the newer base before merge.

The recovery must retire only the stale merge authority, preserve its immutable proof receipt/check evidence, and permit exactly one descendant candidate to re-enter the normal Runless proof path. It must never create parallel authority, bypass branch protection, reuse stale proof as proof for a new SHA, or silently rewrite prior receipts.

## Observed failure

API 2 PR #1600 exposed the gap:

1. exact candidate `d5fc3affb6b80b6fad6ad9d3ae13547a97e99d07` passed Runless and reached `MERGE_AUTHORIZED`;
2. GitHub published `runless-final-gate` success from App `5204253` for that exact SHA;
3. meanwhile `main` advanced from `d6c8f1da...` to `74ad7abde...` and later to `0ade190bd...`;
4. the PR branch absorbed newer main and became descendant candidate `2d8453111736890628b50a9f3ffafc763ad9a506`;
5. Runless correctly rejected a new proof with `RUNLESS_V2_AUTHORITY_CONFLICT` because the old proof still owned `MERGE_AUTHORIZED`;
6. current V2 has no legal transition out of `MERGE_AUTHORIZED` except `MERGED`, so the old authority cannot be retired even though that exact SHA is no longer the mergeable PR head.

This creates a repeatable final-mile deadlock on an active repository.

## Core invariants

1. There is never more than one merge/finalization authority for a workstream.
2. A successful receipt/check remains permanently bound to its original exact candidate SHA.
3. Supersession does not imply success for the successor; the successor must run a fresh exact-head proof.
4. Supersession is allowed only for verified base drift, never for ordinary product-code edits or failed proof repair.
5. No live Runless execution lease may exist for the workstream during supersession.
6. The old proof must be exactly `MERGE_AUTHORIZED`; `MERGED`, `POST_MERGE_VERIFY`, `FREEZE`, `READ_BACK`, `GREEN_FROZEN`, `FAILED`, or earlier states are ineligible.
7. GitHub branch protection remains authoritative; no merge bypass is added.
8. Frozen-artifact, scope-lease, exact-head, proof-before-merge, and zero-GitHub-Actions-fallback rules remain unchanged for the successor proof.

## Proposed state model

Add one terminal historical state:

`SUPERSEDED_BASE_DRIFT`

Legal transition:

`MERGE_AUTHORIZED -> SUPERSEDED_BASE_DRIFT`

No transitions leave `SUPERSEDED_BASE_DRIFT`.

The state means only: “this exact candidate had valid proof and merge authorization, but its merge authority was retired because verified upstream base movement required a new exact PR head.”

It is not `FAILED`, because the proof itself succeeded. It is not `MERGED`, because the candidate did not merge. It is intentionally excluded from the outstanding-authority conflict set so a verified successor can claim the same workstream.

## Durable audit record

Create a dedicated immutable supersession record rather than overwriting proof evidence:

`runless_v2.authority_supersessions`

Required fields:

- `supersession_id`
- `workstream`
- `old_proof_id`
- `old_candidate_sha`
- `old_expected_main_sha`
- `successor_candidate_sha`
- `successor_expected_main_sha`
- `reason` fixed to `BASE_DRIFT`
- `github_pr_number` when applicable
- `github_branch`
- `old_gate_check_run_id`
- `old_receipt_digest`
- `created_at`

Uniqueness rules:

- one supersession per `old_proof_id`;
- one predecessor authority per `successor_candidate_sha` within a workstream.

Existing receipt mirrors, gate check IDs, proof fingerprints, and receipt digests remain unchanged on the old proof row.

## Base-drift verification

Supersession is a two-layer operation.

### Layer A — GitHub corroboration

Before any durable mutation, Runless must verify:

1. the old proof resolves uniquely and is `MERGE_AUTHORIZED`;
2. the associated PR is still open and on the same authoritative branch;
3. the PR current head equals the requested successor candidate;
4. the successor candidate differs from the old candidate;
5. current `main` differs from the old proof's `expected_main_sha`;
6. requested successor `expected_main_sha` equals current `main`;
7. the successor is a Git descendant of both the old candidate and current main, proving it is a base-drift descendant rather than an unrelated replacement;
8. no alternate PR/branch is substituted.

If any GitHub ancestry or identity check is unavailable or ambiguous, fail closed.

### Layer B — transactional durable mutation

Under the existing workstream advisory lock, the Supabase RPC must verify again:

1. old proof still exists and is exactly `MERGE_AUTHORIZED`;
2. no live workstream lease exists;
3. no other proof in the same workstream is in `MERGE_AUTHORIZED`, `MERGED`, `POST_MERGE_VERIFY`, `FREEZE`, or `READ_BACK`;
4. no supersession already exists for the old proof;
5. successor SHA is not the old SHA;
6. successor expected-main SHA differs from old expected-main SHA;
7. old receipt digest and gate check ID are present.

Then, in one transaction:

- insert the immutable supersession record;
- transition old proof state to `SUPERSEDED_BASE_DRIFT`;
- set detail to a deterministic base-drift marker without changing receipt/gate evidence;
- return the supersession record for read-back.

No successor proof row is created in this transaction. The successor enters through the existing normal `claim_workstream` / proof transport afterward.

## Public interface

Add a focused server-side operation, conceptually:

```text
supersede_base_drift_authority(
    repository,
    workstream,
    task_id,
    old_proof_id,
    old_candidate_sha,
    successor_candidate_sha,
    successor_expected_main_sha,
    pr_number,
    branch
) -> immutable supersession receipt
```

The connected ChatGPT environment must not receive or manage privileged Runless credentials. As with proof transport, the supported connected path should be a privileged server-side Supabase transport RPC that invokes the existing Runless/Vercel authority service with secrets held server-side.

## Normal successor flow

After supersession read-back succeeds:

1. successor candidate claims the same original workstream through normal Runless Step 2A;
2. successor must use current `main` as `expected_main_sha`;
3. successor receives a fresh proof ID/fingerprint/fencing generation;
4. all declared tests/probes execute again on the exact successor SHA;
5. a new receipt and new `runless-final-gate` are published for the successor only;
6. normal merge -> merged-main verification -> freeze -> read-back -> `GREEN_FROZEN` proceeds unchanged.

The old receipt may be cited as historical evidence but can never satisfy the successor's proof gate.

## Failure behavior

Fail closed with typed errors for:

- old proof not found;
- old proof not `MERGE_AUTHORIZED`;
- live workstream lease;
- old candidate mismatch;
- unchanged main identity;
- successor equals old candidate;
- successor is not descendant of old candidate;
- successor is not descendant of current main;
- PR/branch/head mismatch;
- another outstanding authority exists;
- duplicate supersession;
- missing old receipt/gate evidence;
- durable store or GitHub verification unavailable.

No error path may silently mutate authority or retry with a second successor.

## Code and schema surface

Expected implementation areas:

- new Supabase migration extending the proof state constraint and adding `authority_supersessions` plus transactional supersession RPC;
- `runless_v2/models.py` for `SUPERSEDED_BASE_DRIFT` and typed supersession models;
- `runless_v2/state_store.py` for the RPC boundary/read-back;
- `runless_v2/github_authority.py` for PR/head/main/ancestry corroboration;
- Runless API/transport layer for the authenticated supersession request;
- connected Supabase transport RPC mirroring the existing proof-transport credential boundary;
- dynamic finalization authority resolver so superseded rows are historical, not current authority;
- focused regression tests and one Runless proof plan for this architecture repair.

Do not mix sports-page product code into this repair PR.

## Test matrix

Required tests before deployment/use:

1. happy path: authorized old candidate + changed main + descendant successor -> one supersession record;
2. same request is idempotent and returns the same supersession record;
3. second different successor for the same old proof is rejected;
4. live execution lease rejects supersession;
5. wrong old state rejects supersession;
6. `MERGED` or later states reject supersession;
7. `FAILED` rejects supersession;
8. unchanged main rejects supersession;
9. non-descendant successor rejects supersession;
10. successor not containing current main rejects supersession;
11. PR/branch/head mismatch rejects supersession;
12. existing alternate outstanding authority rejects supersession;
13. receipt/gate fields on old proof remain byte-for-byte unchanged after supersession;
14. `claim_workstream` accepts exactly one new successor after supersession;
15. old proof can never become active again;
16. dynamic authority resolution ignores `SUPERSEDED_BASE_DRIFT` as current authority while preserving it as historical evidence;
17. GitHub Actions fallback remains 0;
18. full existing Runless V2 state-store/finalization regression suite remains green.

## Rollout for the current PR #1600 blocker

After this architecture repair itself is proven, merged, and frozen:

1. read back old PR #1600 proof `api2-universal-nav-single-owner-speed-v1-d5fc3affb6b80b6f-c7392888590faff7` and its immutable receipt/gate;
2. reconcile PR #1600 to the then-current `main` exactly once if needed;
3. invoke the new base-drift supersession path for the stale authorized candidate;
4. read back the supersession record;
5. submit exactly one successor proof for the then-current exact PR head;
6. merge only after the successor's own App-5204253 `runless-final-gate` is green;
7. perform merged-main verification, freeze, lease release, and canonical read-back;
8. claim `GREEN + FROZEN` only when the successor proof is durably `GREEN_FROZEN`.

If `main` moves again before the successor merges, the same audited supersession mechanism may be used again only on the newly authorized proof, producing a chain of explicit historical authorities rather than hidden rewrites or parallel authority.

## Non-goals

- no weakening of GitHub branch protection;
- no direct manual edits to proof rows;
- no reuse of stale check runs for new SHAs;
- no generic “cancel any proof” endpoint;
- no new sports workstream or duplicate sports PR;
- no automatic product-code rebasing inside Runless;
- no latest-PR/newest-proof heuristic;
- no GitHub Actions fallback.

## Completion criteria

This repair is complete only when:

1. schema/model/state-store/API changes pass the full focused regression matrix;
2. one exact-head Runless proof certifies the repair candidate;
3. repair PR merges and merged-main verification succeeds;
4. repair freeze/read-back reaches durable `GREEN_FROZEN`;
5. PR #1600 then uses the new path to supersede its stale merge authority, prove its current exact head, merge, freeze, and read back without parallel authority or branch-protection bypass.
