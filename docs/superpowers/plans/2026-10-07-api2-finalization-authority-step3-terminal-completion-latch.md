# API 2 Finalization Authority V1 Step 3 — Terminal Completion Latch

## Mission

Prevent already-terminal API 2 work from reopening after canonical completion has been proven.

## Root cause

Task 17 atomic closeout can already return `RUNLESS_ATOMIC_CLOSEOUT_ALREADY_COMPLETE`, but that protection exists only inside final closeout. Earlier workflow entry points can still re-enter proof, merge, freeze, deployment, or stale-ledger checks after canonical terminal truth already exists.

## Design

Add a pure latch above the workflow entry points. The latch delegates terminal truth to Step 1 `canonical_completion_resolver_v1` and never treats a ledger as completion authority.

When the exact canonical tuple is terminal, the latch returns `TERMINAL_LATCH_ALREADY_COMPLETE`, blocks duplicate mutation work, and directs the controller to `MOVE_TO_NEXT_STEP`.

The immutable terminal tuple is:

- task id
- freeze token
- candidate SHA
- Runless receipt digest
- merged-main SHA

A deterministic SHA-256 digest binds that tuple. Stale ledger state cannot change the digest or reopen the task.

## Reopen rule

Terminal work may reopen only when both are true:

1. an explicit thaw id is supplied, and
2. a distinct new task id is supplied.

The old terminal digest is preserved as `reopen_from_terminal_digest` for provenance. Same-task re-entry remains blocked.

## Safety

- No sports/product runtime changes.
- No model, projection, probability, ranking, qualification, or sportsbook changes.
- No network calls.
- No automatic mutation.
- No mutation authority granted by this module.
- GitHub Actions fallback = 0.
- Step 2A remains required before every external mutation.

## TDD

Authoritative RED candidate: `7deae8da3b554733cbc796a413bf32dd512270c5`.

Runless proof id: `api2-finalization-authority-v1-step3-terminal-completion-latch-7deae8da3b554733-aa0d37b948c066ce`.

RED failure class: `STATIC_PROOF` on `tests/test_devsystem_terminal_completion_latch_v1.py`, observed before `devsystem/terminal_completion_latch_v1.py` existed.

## Acceptance

- Terminal canonical tuple short-circuits duplicate prove/recheck/merge/freeze/deploy/ledger-recheck requests.
- Stale ledger cannot reopen terminal work.
- Incomplete canonical truth leaves the latch open.
- Explicit thaw without a distinct new task is blocked.
- Explicit thaw plus a distinct new task is allowed only as a new workstream.
- Read-only canonical terminal queries remain allowed without reopening mutation work.
- Terminal digest is deterministic and stable across stale-ledger repair.
