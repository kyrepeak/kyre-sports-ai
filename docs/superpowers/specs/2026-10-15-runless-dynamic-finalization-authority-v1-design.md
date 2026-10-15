# Runless Dynamic Finalization Authority V1 — Design Specification

Date: 2026-10-15
Status: Design approved; implementation not yet authorized
Workstream: runless-dynamic-finalization-authority-v1

## Purpose

Remove legacy hard-coded finalization authority from the shared Runless/Vercel finalizer so current and future API 2 sports workstreams can finalize against their actual authoritative candidate rather than historical PR #1526 / branch api2-universal-sports-source-finalization-v1-step1.

This is shared control-plane architecture, not an NBA-specific patch. The current NBA candidate and PR remain isolated and must not be restarted or mutated by this workstream.

## Confirmed root cause

The existing finalizer embeds ALLOWED_BRANCH = api2-universal-sports-source-finalization-v1-step1 and fetches GitHub PR #1526 directly. Companion finalizer build/test code also assumes that historical authority. A newer candidate can therefore deploy while final-gate validation still targets old PR/branch state.

## Core invariant

For every finalization request:

requested candidate SHA == durable Runless authoritative candidate SHA == candidate being finalized.

Any ambiguity or mismatch fails closed.

## Source of truth

Use existing durable Runless V2 authority state, including its existing Supabase-backed authority where applicable. Do not create a second authority registry and do not infer authority from newest/open PR ordering.

The durable authority record must resolve, for the requested workstream/task:

- workstream/task identity
- authoritative candidate SHA
- authoritative branch and PR when applicable
- proof fingerprint/digest identity
- lease/fencing generation
- current finalization state

GitHub PR/branch data is corroborating validation metadata, not global hard-coded authority.

## Step 1 — Dynamic authority resolution

Remove finalization dependency on hard-coded PR #1526 and ALLOWED_BRANCH. Extend the finalization request/authority resolution boundary with enough workstream/task identity to locate exactly one durable authority record. Resolve the current authoritative candidate and associated metadata from existing Runless V2 state, then validate the requested SHA against it before any gate publication or merge authorization.

Required failure behavior:

- unknown workstream/task: fail closed
- zero authoritative records: fail closed
- multiple authoritative records: fail closed
- candidate SHA mismatch: fail closed
- stale fencing generation: fail closed
- PR/branch mismatch where a PR is applicable: fail closed
- unavailable durable authority store: fail closed; never fall back to historical constants

Step 1 does not publish a gate, merge a PR, rerun a proof, or mutate the NBA candidate. It establishes and proves dynamic authority resolution only.

## Later-step boundaries

Step 2 binds proof + immutable receipt to exact candidate/workstream/fencing generation.

Step 3 makes runless-final-gate publication exact-head and idempotent under GitHub App 5204253.

Step 4 adds a durable terminal completion latch with resumable state transitions.

Step 5 connects successful gate publication to existing Finalization Authority / 100% Convergence merge, merged-main verification, freeze, canonical read-back, and lease release.

Step 6 runs regression scenarios and recovers the existing NBA Step 1/3 candidate without restarting it.

These later behaviors must not be prematurely implemented in Step 1.

## Isolation and anti-duplication

This architecture workstream uses its own branch and live state. It must not overwrite NBA, MONSTER, or another API 2 lane. Before mutation, resolve one active problem and one authoritative mutation path. Do not create duplicate PRs, deployments, proof executions, gates, leases, or asynchronous jobs.

The current NBA authoritative candidate 0caf4fd0728b5ff666653b385a63d1c8ced9f154 remains protected while this repair is developed.

## Components

1. Authority resolver — adapter over existing durable Runless V2 authority state; returns one immutable authoritative snapshot or a typed failure.
2. Finalizer request boundary — carries workstream/task identity plus requested candidate SHA and, where required, fencing identity.
3. GitHub corroboration — validates resolved PR/head/branch against GitHub only after durable authority resolution.
4. Existing final-gate publisher — unchanged in Step 1 except that its authority input comes from the dynamic resolver rather than constants.

## Data flow

Finalization request
→ validate request syntax
→ resolve exactly one durable Runless authority snapshot by workstream/task
→ validate requested SHA == authoritative SHA
→ validate fencing/current authority state
→ corroborate PR/head/branch when applicable
→ return validated authority snapshot to finalization path.

No proof execution or final-gate publication is permitted if this chain fails.

## Testing and Step-1 proof

Step 1 must include deterministic tests proving:

1. current authority resolves dynamically without PR #1526 or ALLOWED_BRANCH constants;
2. correct workstream + exact SHA succeeds;
3. stale SHA fails closed;
4. wrong workstream fails closed;
5. stale fencing generation fails closed;
6. missing/ambiguous authority fails closed;
7. applicable PR/branch mismatch fails closed;
8. no NBA candidate mutation, proof rerun, gate publication, merge, or freeze occurs in Step 1;
9. source inspection/regression test prevents reintroduction of hard-coded PR #1526 / historical allowed branch as authority.

Step 1 becomes GREEN + FROZEN only after exact-head proof of these invariants and durable completion evidence. Deployment success alone is insufficient.

## Non-goals

- No sports data/model/page changes.
- No NBA candidate restart.
- No new authority database/registry.
- No latest-PR heuristic.
- No GitHub Actions fallback.
- No automatic merge/freeze until later approved steps.

## Completion criteria

Step 1 is complete when the shared finalizer resolves current authority dynamically from existing durable Runless state, hard-coded historical PR/branch authority is removed, mismatch cases fail closed, exact-head tests/proof pass, and Step-1 completion is durably read back and frozen without disturbing the NBA lane.