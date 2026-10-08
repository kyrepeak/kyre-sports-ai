# API 2 Finalization Authority V1 — Step 6 100% Finalizer

## Goal

Close the six-step Finalization Authority program at a deterministic, reusable 100% terminal state without reopening any already-frozen step.

## Contract

The finalizer is a pure convergence layer. It accepts five prior canonical terminal checkpoints (Steps 1–5) plus the Step-5 Authority Garbage Collector result.

It finalizes only when:

1. Steps 1–5 are all present exactly once.
2. Every checkpoint is terminal GREEN + FROZEN.
3. Every checkpoint carries its exact expected freeze token.
4. Every checkpoint carries a valid terminal digest and merged-main SHA.
5. Authority Garbage Collector is terminal (`AUTHORITY_GC_COLLECTED` or `AUTHORITY_GC_ALREADY_CLEAN`).
6. Remaining target mutation authority is exactly zero.
7. The GC explicitly hands off to `RUN_100_PERCENT_FINALIZER`.

On success it emits one deterministic receipt and the only next legal action is `RUNLESS_PROVE_MERGE_FREEZE_STEP6`.

## Safety

- no network calls
- no automatic mutation
- no product-runtime authority
- no GitHub Actions fallback
- unrelated active thaws are preserved in the terminal packet
- duplicate step identities and malformed terminal evidence fail closed
- frozen Steps 1–5 are read-only dependencies

## Step 2A

- base main: `6c193bab72e6b55e1e39558d3322887643b78a87`
- branch: `api2-finalization-authority-v1-step6-100-percent-finalizer-r1`
- lease: `SCOPE-LEASE-0B3BDBFBD1355D489BE0C914`
- one branch / one proof chain / one PR maximum
- exact-head merge required
- GitHub Actions fallback not authorized

## TDD

Test-first commit: `8f71d94140de6ffa19e32090aa18574d3808c8ac`.

RED: `1 passed, 9 failed in 0.11s` with finalizer behavior absent.

Implementation commit: `80c1d448efde7fed93e93f806a443c4fafee68b0`.

Target GREEN: `10 passed in 0.03s` before Runless certification.

## Completion

Step 6 becomes GREEN + FROZEN only after:

1. exact-head Runless proof (including full-suite verification),
2. exact certified candidate merge,
3. merged-main proof reuse without static evidence re-execution,
4. transactional registry freeze under `API2_FINALIZATION_AUTHORITY_V1_STEP6_FROZEN`,
5. independent registry read-back matching the closeout receipt.

At that point Finalization Authority V1 is 6/6 = 100% GREEN + FROZEN.
