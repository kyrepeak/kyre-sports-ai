# Monster Production Certification V1 — Implementation Plan

Date: 2026-09-15
Base main: `c0f480bdb5a7210b2dd3a8ed6b642cabe5e8b800`
Feature branch: `monster-final-form-production-cert-v1`

## Goal

Add a read-only, cross-project Monster production certification conductor that reconciles GitHub intended identity, Render deployment identity/status, Kyre Sports API health/readiness identity, and existing certification/freeze signals into one deterministic certification result.

## Non-goals / frozen boundaries

- No modification to sports projection math.
- No modification to Monte Carlo engines.
- No modification to sportsbook/market calculations.
- No modification to `sports_api/main.py` for V1.
- No modification to `sports_api/api/health.py` for V1.
- No enablement of Render auto-deploy.
- No deployment/create/update/delete side effects from the conductor.
- Existing sport-specific certification/freeze workflows remain authoritative inputs and are not replaced.
- PostHog/error-radar and performance-profiler signals are advisory only and cannot change certification identity truth or sports outputs.

## Planned additive files

1. `scripts/build_monster_production_certification_snapshot_v1.py`
   - Pure reconciliation/classification core plus read-only HTTP/GitHub/Render input adapters.
   - Deterministic snapshot classification for normalized inputs.
   - CLI exits non-zero when certification is not GREEN.

2. `tests/test_monster_production_certification_snapshot_v1.py`
   - TDD coverage for GREEN, production lag, failed deploy, identity conflict, health failure, readiness failure, unavailable evidence, deterministic output, and no side-effect contract.

3. `.github/workflows/monster-production-certification-v1.yml`
   - Manual/PR workflow wrapper that invokes the tested Python conductor.
   - Workflow contains no duplicate classification logic.
   - Uploads snapshot output as evidence artifact.

4. `.github/monster-production-certification-v1-contract.md`
   - Permanent safety and semantics contract.

5. `sports_api/certification/monster_production_certification_v1_evidence.json`
   - Created only after successful live certification; immutable baseline evidence for the certified implementation state.

## Build order

1. Write safety contract.
2. Write failing tests first and verify RED.
3. Implement minimal conductor core until tests GREEN.
4. Add workflow wrapper and workflow-structure tests/validation.
5. Run read-only live certification against GitHub/Render/API evidence.
6. Re-run existing scope/freeze/regression gates.
7. Create certification evidence JSON only after all required proof is GREEN.
8. Open/finish PR through protected `main` checks; merge only after required status checks are GREEN.
9. Verify protected `main` and production identity after merge without changing frozen sports logic.

## Certification states

- `GREEN`: intended GitHub commit, Render deployed commit, runtime health commit, branch/readiness, and required guards all agree and are healthy.
- `PRODUCTION_LAG`: GitHub intended commit is newer than the healthy deployed commit; not certified current.
- `IDENTITY_CONFLICT`: Render commit and runtime health commit disagree.
- `DEPLOY_FAILED`: latest/selected Render deploy failed.
- `RUNTIME_PROOF_FAILED`: health endpoint unavailable or unhealthy.
- `NOT_READY`: readiness endpoint reports not ready or branch misalignment.
- `GUARD_FAILED`: required freeze/scope/regression guard is not green.
- `UNKNOWN`: required evidence is unavailable or malformed.

Only `GREEN` is certified.

## Failure containment / rollback

V1 is additive and read-only. If the conductor or workflow is wrong, disable/remove the V1 workflow and additive files on the feature branch/revert PR. Sports runtime rollback is not required because V1 does not modify production runtime or frozen sports systems.

## Verification requirements

- TDD red-green proof for the Python conductor.
- Full targeted pytest file passes with zero failures.
- Workflow syntax/contract verification passes.
- Compare feature branch to base and confirm only planned additive files changed.
- Required protected-main `devsystem-final-gate` remains green before merge.
- Live identity proof must never be inferred; unavailable evidence results in non-GREEN.
