# Monster Project State V1 Design

## Purpose

Monster Project State V1 adds one read-only, deterministic project-truth layer above the existing Monster systems. Its job is to answer, from explicit evidence: where the engineering project is now, what is complete, what is active, what is blocked or drifting, and the exact next action.

It must not duplicate the existing Monster Control Plane, Live Bridge, Runtime Lab, Continuity Layer, Performance Profiler, Error Radar, or Production Certification. Instead, it consumes their receipts and reduces them into one project-state packet.

## Current Baseline

The protected repository already contains and has certified:

- Monster Error Radar V1 / PostHog adapter.
- Monster Performance Profiler V1.
- Monster Dependency Map V1.
- Monster Test Matrix V1.
- Monster Failure Memory V1.
- Monster One-Command Certification V1.
- Monster Control Plane V1.
- Monster Runtime Lab V1.
- Monster Continuity Layer V1.
- Monster Live Bridge V1.
- Monster Production Certification V1.

Production Certification V1 is the production-truth authority and remains read-only. Existing sport-specific certification/freeze workflows and `devsystem-final-gate` remain authoritative merge vetoes.

Current external evidence also shows that Render production identity is operational and auto-deploy remains disabled, while PostHog code exists but the connected project has no live event ingestion. Therefore PostHog is an advisory degraded capability, not a production-certification failure.

## Problem

Monster has several strong specialist systems but no dedicated current-tree Project State / Control Center layer. Continuity knows resumable checkpoint details. Live Bridge knows external operational evidence. Runtime Lab knows incident reproduction and safe-fix planning. Control Plane knows diagnosis. Production Certification knows production truth. None should be expanded into a global project tracker because that would mix responsibilities and create another large orchestration module.

The missing capability is one small conductor that reads these sources and returns one deterministic engineering-state packet.

## Chosen Architecture

Create a new additive module:

`sports_api/monster_project_state_v1.py`

The module is pure orchestration and classification. It performs no live network calls and no source mutation. External connector evidence must be sanitized and normalized by existing adapters before being supplied to Project State.

Project State consumes normalized evidence objects and emits one immutable-style dictionary packet with explicit state, reasons, evidence references, and the next action.

### Inputs

Project State may consume the following normalized inputs when available:

- Continuity checkpoint / resume packet.
- Live Bridge health and external-source packet.
- Runtime Lab incident/planner packet.
- Monster Control Plane diagnosis packet.
- Production Certification classification packet.
- PostHog/Error Radar status packet.
- Performance diagnosis packet.

Project State does not fetch these systems itself. Callers pass already-normalized dictionaries into the classifier.

### Output Contract

The top-level result must contain these stable fields:

- `version`: `MONSTER_PROJECT_STATE_V1`.
- `state`: one of `READY`, `ACTIVE`, `BLOCKED`, `REVALIDATE`, `COMPLETE`, `UNKNOWN`.
- `current_task`: stable human-readable task title or `unknown`.
- `current_step`: exact active step or `unknown`.
- `completed_steps`: ordered list of completed steps.
- `remaining_steps`: ordered list of remaining steps.
- `last_green_evidence`: normalized summary of most recent proven GREEN state.
- `repository`: repository identity summary.
- `production`: production-certification summary.
- `telemetry`: PostHog/Error Radar status summary.
- `performance`: Performance Profiler summary.
- `incident`: Runtime Lab summary.
- `blockers`: ordered explicit blockers.
- `forbidden_scope`: normalized list inherited from checkpoint/spec evidence.
- `next_action`: one exact action string.
- `reasons`: ordered classification reasons.
- `projection_weight`: `0.0`.
- `may_modify_projection`: `false`.
- `may_modify_source_data`: `false`.
- `may_modify_runtime`: `false`.
- `network_calls`: `false`.
- `auto_fix`: `false`.

The result must be deterministic for identical normalized inputs.

## State Precedence

Classification uses fail-closed precedence. Higher rules win over lower rules.

1. `BLOCKED`
   - Production Certification explicitly reports a non-GREEN unsafe state.
   - Continuity reports a recorded blocker.
   - Required evidence explicitly reports corruption/tampering or an unsafe contradiction.

2. `REVALIDATE`
   - Continuity reports repository, branch, head, or protected-main drift.
   - Required identity evidence has become stale or inconsistent but not yet proven unsafe.

3. `UNKNOWN`
   - Required Project State inputs are missing, malformed, or cannot support a safe classification.
   - `UNKNOWN` must never be upgraded optimistically to READY.

4. `COMPLETE`
   - Continuity/task evidence explicitly marks the task complete and no higher-precedence condition applies.

5. `ACTIVE`
   - A current task/step is identified, remaining steps exist, and no higher-precedence condition applies.

6. `READY`
   - Evidence is valid, no blocker or drift exists, no active task step requires continuation, and the packet supplies a safe next action.

## Advisory Evidence Rules

PostHog/Error Radar and Performance Profiler remain advisory, matching Production Certification V1.

- PostHog `NOT_CONFIGURED`, `UNAVAILABLE`, or no-ingestion state is surfaced in `telemetry` and `reasons`, but does not independently make Project State `BLOCKED`.
- Performance `SLOW`, `CRITICAL`, missing, or unavailable is surfaced in `performance` and `reasons`, but does not independently invalidate production identity.
- Runtime Lab incident evidence may contribute a blocker only if the normalized incident packet explicitly marks execution unsafe or blocked; Project State does not infer severity from free text.

## Required Evidence and Graceful Degradation

The minimal required evidence for a confident non-`UNKNOWN` state is:

- a valid Continuity/task packet or an explicit equivalent task-state input; and
- a valid Production Certification packet when production truth is in scope for the current task.

Optional advisory packets may be absent without causing `UNKNOWN`.

Malformed required packets fail closed to `UNKNOWN` unless they explicitly prove a blocker/corruption condition, which classifies as `BLOCKED`.

## Boundaries

Project State V1 is read-only and additive.

It must not:

- modify sports projection math;
- modify Monte Carlo behavior;
- modify sportsbook or market logic;
- modify identity reconciliation rules;
- modify Streamlit pages or routers;
- modify `app.py`;
- modify `sports_api/main.py`;
- modify `sports_api/api/health.py`;
- deploy, restart, create, delete, or update Render resources;
- enable Render auto-deploy;
- change environment variables;
- merge pull requests;
- mutate GitHub branches;
- auto-fix source code;
- make live network calls;
- replace `devsystem-final-gate`, Production Certification, or sport-specific certification/freeze workflows.

Permanent constants are:

- `PROJECTION_WEIGHT = 0.0`.
- `MAY_MODIFY_PROJECTION = False`.
- `MAY_MODIFY_SOURCE_DATA = False`.
- `MAY_MODIFY_RUNTIME = False`.
- `NETWORK_CALLS = False`.
- `AUTO_FIX = False`.

## File Plan

The implementation/certification surface is limited to four additive files:

- `sports_api/monster_project_state_v1.py` — deterministic classifier and packet builder.
- `tests/test_monster_project_state_v1.py` — unit, precedence, malformed-input, and deterministic-output contracts.
- `.github/workflows/monster-project-state-v1.yml` — focused certification lane.
- `.github/monster-project-state-v1-contract.md` — permanent safety and authority contract.

Documentation artifacts are allowed in addition to those four files:

- this approved design spec under `docs/superpowers/specs/`;
- the implementation plan under `docs/superpowers/plans/`.

No other runtime, test, workflow, configuration, or documentation file is in scope unless a later review identifies a concrete repository-required compatibility change and that change receives separate approval before implementation.

A later plan may add PostHog operational activation, but that is a separate subproject and is not part of Project State V1.

## Test Design

The focused test suite must prove at least:

1. Valid active checkpoint + GREEN production -> `ACTIVE`.
2. Explicit continuity blocker -> `BLOCKED`.
3. Production non-GREEN unsafe state -> `BLOCKED`.
4. Branch/head/main drift -> `REVALIDATE`.
5. Missing required evidence -> `UNKNOWN`.
6. Malformed required evidence -> `UNKNOWN`.
7. Explicit corruption/tampering -> `BLOCKED`.
8. Completed task -> `COMPLETE`.
9. PostHog not configured remains advisory and does not turn GREEN production into `BLOCKED`.
10. Slow/critical performance evidence remains advisory.
11. Identical inputs produce identical packets.
12. Completed and remaining step ordering is preserved.
13. Exact `next_action` from valid continuity evidence is preserved unless a higher-precedence state requires a revalidation/blocking action.
14. Safety constants remain pinned by contract.
15. The module exposes no production entrypoint and performs no network calls.

## CI and Certification

The dedicated workflow must:

- compile `sports_api/monster_project_state_v1.py`;
- run `tests/test_monster_project_state_v1.py`;
- verify that non-document implementation changes are limited to the four approved implementation/certification files;
- permit only the approved design and implementation-plan documents under `docs/superpowers/` in addition to those four files;
- verify static safety constants;
- verify no imports of network clients in the Project State module;
- run the existing Monster one-command certification contracts;
- run Production Certification V1 tests/contracts;
- run Dependency Map proof showing zero production entrypoints for the new module;
- run the permanent contract/regression shield required by the repository;
- require `devsystem-final-gate` before merge.

The implementation branch must not trigger a Render deployment. Production remains unchanged throughout this subproject.

## Error Handling

Project State never invents missing truth.

- Unknown required fields -> `UNKNOWN` with explicit reasons.
- Contradictory required safety evidence -> `BLOCKED` or `REVALIDATE` according to precedence.
- Optional/advisory source unavailable -> degraded advisory field plus reason, without fabricating healthy telemetry.
- Free-text evidence is display-only; state transitions depend on explicit normalized fields.

## Success Criteria

Project State V1 is complete when:

- the four implementation/certification files and approved docs are merged on protected `main`;
- all focused tests pass;
- permanent Monster and DevSystem gates remain GREEN;
- Production Certification remains authoritative and GREEN;
- Dependency Map confirms zero production entrypoints;
- no frozen sports/runtime files are changed;
- no production deployment or configuration change occurs;
- a deterministic sample packet can correctly summarize an ACTIVE, BLOCKED, REVALIDATE, COMPLETE, and UNKNOWN project state.

## Follow-On Subproject

After Project State V1 is certified, PostHog Operational Activation may be designed separately. Its goal will be to safely configure real Error Radar ingestion and prove live `$exception` telemetry without changing sports/model behavior. Project State V1 should then be able to report telemetry as available rather than not configured without any Project State code change.
