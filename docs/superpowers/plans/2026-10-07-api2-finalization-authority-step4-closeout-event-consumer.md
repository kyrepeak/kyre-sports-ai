# API 2 Finalization Authority V1 — Step 4 Closeout Event Consumer

## Goal

Convert a one-shot Runless event-resume handoff into exactly one remaining legal closeout action, without granting authority from telemetry and without reopening work that canonical terminal truth already proves complete.

## Problem

Runless Event Resume intentionally stops at a safe handoff. It can produce `RUNLESS_RESUME_CONSUMED` plus one `next_legal_action`, but it does not itself execute that action. That leaves a final-mile gap where the system can correctly know what must happen next while still failing to consume the last legal closeout action.

## Root cause

Detection, resume claiming, and mutation authority are deliberately separated. Tail-SLA/Event Resume has `NETWORK_CALLS=false`, `AUTO_MUTATE=false`, and no mutation authority. Before this step there was no dedicated consumer that required final MONSTER Step 2A global execution authority for the same action/target and then consumed that action exactly once.

## Patch

Add `devsystem/closeout_event_consumer_v1.py` as a narrow control-plane bridge:

1. Canonical terminal truth is checked first. If Step 3 already says the task is terminal, no executor is called and the caller moves forward.
2. Only `RUNLESS_RESUME_CONSUMED` is accepted. A mere READY/detection signal cannot execute anything.
3. The consumer requires the final Step 2A `GLOBAL_EXECUTION_AUTHORIZED` result and requires its action type and target to match the resumed legal action.
4. A deterministic consumer key binds workstream, continuation packet hash, exact action identity, Step 2A execution proof hash, and action fingerprint.
5. An existing receipt for that key blocks duplicate execution.
6. The caller-supplied executor is invoked at most once.
7. Success emits a deterministic closeout-consumer receipt and advances to canonical completion reconciliation.
8. Failure is classified and returned with `retry_allowed_now=false`; no blind retry loop is permitted.
9. Tail-SLA telemetry is carried only as detection context and cannot grant authority.

## Scope

Only these Step-4 control-plane artifacts may change:

- `devsystem/closeout_event_consumer_v1.py`
- `tests/test_devsystem_closeout_event_consumer_v1.py`
- `devsystem/runless_proof_plans/api2-finalization-authority-v1-step4-closeout-event-consumer.json`
- `devsystem/execution_plans/api2-finalization-authority-v1-step4-closeout-event-consumer.json`
- `devsystem/task_ledgers/api2-finalization-authority-v1-step4-closeout-event-consumer.json`
- this document

No sports product runtime, model, projection, probability, ranking, qualification, sportsbook, or other-sport logic is in scope. Frozen Step 1–3 artifacts are read-only dependencies.

## Step 2A

- authoritative branch: `api2-finalization-authority-v1-step4-closeout-event-consumer-r1`
- rollback main: `85bfd1031b12318c64ca090be5fd5807f57a2f49`
- lease: `SCOPE-LEASE-236118E524AC04B3EE928E70`
- lease owner: `api2-finalization-authority-v1-step4`
- authoritative lease revision: `268`
- authoritative lease generation: `154`
- one active problem, one branch, one proof chain, one PR maximum
- GitHub Actions fallback: not authorized
- unrelated frozen-registry thaws preserved
- exact-head proof required before merge

## TDD evidence

Authoritative RED commit: `90484a772afe12a94f543743d65629f157bc31c2`.

RED command: `python -m pytest -q tests/test_devsystem_closeout_event_consumer_v1.py`.

Observed RED: import failure because `devsystem.closeout_event_consumer_v1` did not yet exist.

Implementation commit: `35a993e6b19660a6d77e4b22fbe0cc22c3ba35d7`.

Fresh local GREEN after implementation: `8 passed in 0.05s`.

Fresh compile check: `python -m py_compile devsystem/closeout_event_consumer_v1.py` → PASS.

## Runless proof contract

The exact candidate must run the checked-in Step-4 Runless proof plan. Required proof includes the new Step-4 contract tests plus regression coverage for terminal latch, event-driven resume, global Step 2A enforcement, canonical completion, atomic closeout, Runless final gate, and Runless Step 2A.

No GitHub Actions proof run may substitute for Runless.

## Acceptance

Step 4 is eligible for GREEN + FROZEN only when all of the following are true:

- exact candidate Runless proof succeeds;
- final Step 2A action binding is preserved;
- duplicate closeout consumption is blocked;
- executor failure never blind-retries;
- canonical terminal truth short-circuits execution;
- exact certified head is merged;
- post-merge proof is reused rather than rerunning unchanged static proof;
- `API2_FINALIZATION_AUTHORITY_V1_STEP4_FROZEN` is written transactionally;
- exact registry read-back confirms the token and artifact map;
- GitHub Actions proof runs used: 0.

After that read-back, Step 4/6 is GREEN + FROZEN and overall Finalization Authority progress becomes 4/6 = 66.7%.
