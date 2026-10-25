# MONSTER Step 2C Autonomous Recovery + Green Convergence V1 — Design

Date: 2026-10-24
Workstream: `monster-step2c-autonomous-recovery-v1`
Base main: `1b4b6a366b490e815efa605a1a3a9cae87d8b99b`

## Intent

Make Anti-Loop stop repeated bad actions without stopping progress. After Step 2B exhausts its two implementation attempts for one diagnosis, MONSTER must continue autonomously in diagnosis mode until it either proves a materially new root cause and produces a new evidence-bound repair cycle, or proves a genuine human-only blocker.

## Goals

- Preserve Step 2A as the single mandatory action front door.
- Preserve Automatic Loop Kill as the live-async duplicate/mutation guard.
- Preserve Step 2B's hard two-attempt cap per diagnosis generation.
- Add Step 2C as a separate, read-only autonomous recovery controller.
- Never treat `ROOT_CAUSE_RESET` as "stop and wait for Kyre" by default.
- Automatically continue diagnostics when evidence is stale, incomplete, or duplicated.
- Require materially new evidence before opening a new implementation generation.
- Bind a successful recovery decision to the exact task/checkpoint/authoritative path with a deterministic receipt.
- Allow user intervention only for a verified human-only blocker.

## Non-goals

- Step 2C does not perform network calls, repository writes, deployments, or product/runtime mutations.
- Step 2C does not bypass Step 2A, Step 2B, Forward Motion, or Automatic Loop Kill.
- Step 2C does not convert a third blind patch into a renamed "recovery" patch.
- Step 2C does not fabricate evidence or infer a root cause from absence of evidence.

## Selected Architecture

### Control flow

`Step 2A -> Step 2B -> implementation attempt 1/2`

If two attempts fail:

`Step 2B -> Step 2C autonomous diagnosis`

Step 2C then returns exactly one of:

1. `TWO_C_GATHER_NEW_EVIDENCE` — a new diagnostic source exists and should be inspected.
2. `TWO_C_EXPAND_DIAGNOSIS` — current evidence is exhausted/duplicated; broaden the diagnostic surface automatically without mutating product code.
3. `TWO_C_RECOVERY_AUTHORIZED` — a materially new root cause is proven and a deterministic recovery receipt is issued.
4. `TWO_C_HUMAN_BLOCKER` — a verified human-only blocker exists and user intervention is genuinely required.

A Step 2C recovery receipt does not execute a repair. It is supplied back to Step 2B. Step 2B validates it against the exact action identity and authoritative path. Only a valid receipt may start a **new diagnosis generation**, which is counted as recovery generation 1 attempt 1 rather than as a third attempt in the failed generation.

### Why this architecture

A direct "Attempt 3" exception would weaken Anti-Loop. Making Step 2C purely advisory would allow callers to ignore it. A separate deterministic recovery authority keeps responsibilities clean:

- Step 2A: is this the one legal action/path?
- Step 2B: is this implementation attempt evidence-ready, and is the current diagnosis within its two-attempt budget?
- Step 2C: after that budget is exhausted, is there a materially new diagnosis that justifies a new repair generation?
- Anti-Loop: are we repeating an action/evidence state without new information?

## Recovery Context Contract

Step 2C consumes a recovery context containing:

- `task_id`
- `checkpoint_id`
- `authoritative_path` with repository, branch, target, proof_path
- `failed_attempts` from the exhausted Step 2B generation
- `diagnostic_history` evidence fingerprints already consumed
- `evidence_candidates` with fingerprint, source, summary, and material flag
- optional `root_cause` with proven flag, classification, failed assumption, evidence fingerprint, repair summary
- optional `human_blocker` with verified flag, blocker type, and evidence

## Material Evidence Rules

- Empty fingerprints are invalid.
- A fingerprint already present in failed-attempt or diagnostic history cannot authorize a new recovery generation.
- A root-cause fingerprint must be materially new.
- A recovery receipt binds the new root cause to the exact task, checkpoint, path, failed-generation fingerprint set, and repair summary.

## Human Blocker Rules

User intervention is permitted only when `human_blocker.verified=true` and the blocker type is one of:

- `missing_credentials`
- `billing_or_plan`
- `required_human_approval`
- `irreversible_or_destructive_decision`
- `external_service_no_fallback`

Anything else remains autonomous diagnosis.

## Integration Rules

- Step 2B keeps its existing Attempt 1/Attempt 2 behavior unchanged.
- With two failed attempts and no valid Step 2C receipt, Step 2B blocks the mutation and returns a Step 2C handoff.
- With two failed attempts and a valid Step 2C receipt bound to the exact action/path, Step 2B authorizes `TWO_B_RECOVERY_ATTEMPT_AUTHORIZED` and resets the attempt counter for the new diagnosis generation.
- Step 2A still requires normal Forward Motion authorization after Step 2B accepts recovery.
- While `WAITING_ON_ASYNC`, Automatic Loop Kill still executes first and blocks competing mutations before Step 2B/2C can authorize anything.

## Failure Semantics

- Duplicate evidence: do not ask the user; continue/expand diagnosis.
- No current evidence candidates: do not patch; expand diagnosis.
- Unproven root cause: do not patch; continue diagnosis.
- Proven new root cause: issue receipt, then re-enter Step 2B/Step 2A.
- Verified human blocker: stop safely and state the exact evidence/blocker.

## Proof Requirements

The implementation must prove:

- two failed Step 2B attempts cannot directly authorize a third patch;
- Step 2C continues diagnosis without user intervention when evidence is duplicated or absent;
- a genuinely new evidence candidate is selected instead of a duplicate;
- a proven new root cause produces a deterministic recovery receipt;
- a forged/mismatched recovery receipt is rejected by Step 2B;
- a valid receipt opens a new repair generation through Step 2B and Step 2A;
- live-async Automatic Loop Kill still precedes all recovery mutation logic;
- only verified human-only blocker classes require the user.
