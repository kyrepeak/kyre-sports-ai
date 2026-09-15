# Monster Production Certification V1 Contract

Status: additive control-plane contract
Projection influence: `0.0`
Deployment authority: none
Runtime mutation authority: none

## Purpose

Monster Production Certification V1 is a read-only control-plane conductor. It reconciles independent production identity and readiness signals into a truthful certification result without altering sports logic or production state.

## Hard safety invariants

1. The conductor MUST NOT deploy, restart, create, update, delete, or mutate Render services.
2. The conductor MUST NOT push, merge, rewrite, or mutate protected sports runtime files.
3. The conductor MUST NOT modify projection math, Monte Carlo logic, sportsbook/market calculations, model weights, or player/team outputs.
4. The conductor MUST NOT enable Render auto-deploy.
5. `sports_api/main.py` and `sports_api/api/health.py` are NO-TOUCH surfaces for V1.
6. Existing sport-specific freeze, regression, certification, and scope workflows remain authoritative and MUST NOT be replaced by V1.
7. PostHog/Error Radar and Monster Performance Profiler are advisory only. Their availability or output cannot make an otherwise non-GREEN identity result GREEN.
8. Missing, malformed, stale, contradictory, or unreachable required evidence MUST fail closed to a non-GREEN state.
9. Only the explicit `GREEN` state is certified.

## Required identity inputs

- Intended GitHub branch and commit.
- Render deployed branch/commit and deploy status.
- `/health` deployment branch/commit and liveness.
- `/health/ready` readiness and branch-alignment state.
- Required freeze/scope/regression guard status supplied to the conductor.

## Classification precedence

When multiple failures exist, the first applicable state below wins so output is deterministic:

1. `UNKNOWN` — required evidence missing/malformed/unavailable.
2. `DEPLOY_FAILED` — Render deploy status is failed/canceled/non-live.
3. `RUNTIME_PROOF_FAILED` — health liveness is not healthy.
4. `NOT_READY` — readiness is false or branch alignment is false.
5. `IDENTITY_CONFLICT` — Render deployed commit and runtime health commit disagree.
6. `PRODUCTION_LAG` — deployed/runtime commit is healthy and internally consistent but differs from intended GitHub commit.
7. `GUARD_FAILED` — identity is aligned but a required freeze/scope/regression guard is non-green.
8. `GREEN` — all required evidence exists, identity agrees, readiness is healthy, and required guards are green.

## Determinism contract

For the same normalized inputs, classification and normalized snapshot content MUST be identical. Volatile observation timestamps may be carried separately but MUST NOT influence the certification state.

## Workflow contract

The GitHub Actions workflow is a wrapper only. Classification logic lives in the tested Python module. The workflow may collect read-only inputs, invoke the conductor, upload evidence, and fail the job for non-GREEN results. It must not duplicate classification policy in shell/YAML.

## Certification evidence

`sports_api/certification/monster_production_certification_v1_evidence.json` may be created only after the implementation and live proof are GREEN. It records the certified baseline; it is not a continuously rewritten runtime cache.
