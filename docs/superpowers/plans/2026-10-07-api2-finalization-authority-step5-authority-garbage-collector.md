# API 2 Finalization Authority V1 — Step 5 Authority Garbage Collector

## Goal

Guarantee that canonically completed workstreams cannot retain mutation-capable authority that keeps them looking live, blocks later work, or causes duplicate closeout attempts.

## Problem

The control plane deliberately separates canonical completion, proof receipts, leases, mutation owners, and resume authority. A workstream can therefore be terminal while stale authority objects remain active elsewhere.

## Patch

Add a pure `authority_garbage_collector_v1` that:

1. requires canonical terminal truth for every target workstream before collection;
2. retires mutation-capable authority belonging to those completed targets;
3. preserves unrelated/current workstream authority;
4. preserves immutable proof/evidence and read-only records;
5. fails closed when a protected target authority still remains;
6. rejects duplicate authority IDs before any cleanup;
7. emits a deterministic receipt binding terminal digests to retired authority IDs;
8. is idempotent on a second pass;
9. grants no network, product-runtime, or ambient mutation authority.

## Scope

Only these Step-5 artifacts may change:

- `devsystem/authority_garbage_collector_v1.py`
- `tests/test_devsystem_authority_garbage_collector_v1.py`
- `devsystem/runless_proof_plans/api2-finalization-authority-v1-step5-authority-garbage-collector.json`
- `devsystem/execution_plans/api2-finalization-authority-v1-step5-authority-garbage-collector.json`
- `devsystem/task_ledgers/api2-finalization-authority-v1-step5-authority-garbage-collector.json`
- this document

Frozen Steps 1–4 are dependencies only and remain read-only.

## Step 2A

- base main: `b42b320e69d4894ed2ec5bbd3a065824d35d6fff`
- branch: `api2-finalization-authority-v1-step5-authority-garbage-collector-r1`
- one active problem, one branch, one proof chain, one PR maximum
- exact-head proof required before merge
- GitHub Actions fallback is not authorized
- unrelated active thaws must be preserved

## TDD

Test-first commit: `5e5691e9eaf5f891817d0793ef8563547daa76a3`.

RED stub commit: `0c0fec6517e97db5453063df2ee2b3e0bd639a92`.

The exact RED candidate is executed through Runless before production behavior is implemented. The implementation may then make only the smallest change necessary to satisfy the contract.

## Completion

Step 5 becomes GREEN + FROZEN only after exact-head Runless success, exact candidate merge, post-merge proof reuse without static re-execution, transactional registry freeze under `API2_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN`, and exact registry read-back. After that, overall Finalization Authority progress is 5/6 = 83.3%.
