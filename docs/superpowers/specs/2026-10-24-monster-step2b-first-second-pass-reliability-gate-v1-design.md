# MONSTER Step 2B First/Second-Pass Reliability Gate V1 — Design

Date: 2026-10-24
Workstream: `monster-step2b-reliability-gate-v1`
Base main: `a10146e789c86d608a451c4f8d4e339463c2c81a`

## Intent

Add a permanent integrated control between problem/path selection and implementation so MONSTER/API 2 is optimized for first- or second-pass success instead of repeated patch cycles.

## Goals

- Preserve Step 2A as the mandatory action front door.
- Preserve Automatic Loop Kill as owner of live-async duplicate/mutation blocking.
- Require a complete reliability preflight before active `patch` and `edit_product` implementation mutations.
- Authorize Attempt 1 only after finished-state, authoritative-path, acceptance-proof, and dependency checks pass.
- Authorize Attempt 2 only after the failed assumption is classified and materially new evidence exists.
- Block a third implementation patch and hand off to `ROOT_CAUSE_RESET`.
- Bind the Step 2B decision to the exact Step 2A action through a deterministic reliability receipt hash.

## Non-goals

- No sports/product runtime changes.
- No network calls from the control-plane gate itself.
- No weakening or replacement of Step 2A, Forward Motion V2, or Automatic Loop Kill.
- No automatic third implementation attempt.

## Architecture

`Step 2A authorize_action()` remains the canonical front door. While a persistent brain is `WAITING_ON_ASYNC`, Automatic Loop Kill continues to decide first and blocks competing mutations. When the brain is active and the action type is `patch` or `edit_product`, Step 2A calls `mandatory_2b_reliability_gate_v1.authorize_implementation()` before Forward Motion authorization.

A denied Step 2B result returns `TWO_A_TWO_B_BLOCKED`. A valid Step 2B result does not itself execute anything; the action must still pass the existing Forward Motion receipt checks before Step 2A returns `TWO_A_AUTHORIZED`.

## Approaches considered

1. Fold all reliability rules directly into Step 2A. Rejected because it would mix path/action authorization with pre-implementation evidence policy and make Step 2A harder to reason about.
2. Keep Step 2B as a standalone advisory helper. Rejected because implementation mutations could bypass it.
3. **Selected:** separate Step 2B module, hard-called by Step 2A only for implementation-producing mutations. This preserves clear ownership and makes bypass fail closed.

## Failure semantics

- Missing/incomplete preflight: block before implementation.
- Failed production/dependency preflight: block before implementation.
- One failed attempt: require failure classification, failed assumption, and new evidence before Attempt 2.
- Two failed attempts: block and emit `anti_loop_handoff=true`, `next_legal_action=ROOT_CAUSE_RESET`, `recheck_policy=ONLY_AFTER_MATERIALLY_NEW_EVIDENCE`.

## Proof

Targeted tests cover the Step 2B contract, Step 2A integration, and precedence of the existing Automatic Loop Kill live-async lock. A dedicated GitHub Actions workflow runs all three control families together.
