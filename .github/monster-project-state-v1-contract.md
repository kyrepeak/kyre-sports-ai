# Monster Project State V1 Contract

Status: additive read-only engineering control layer  
Projection influence: `0.0`  
Deployment authority: none  
Runtime/source mutation authority: none

## Purpose

Monster Project State V1 reduces already-normalized Monster evidence into one deterministic current-project packet: current task, current step, completed/remaining work, blockers, drift state, production state, advisory telemetry/performance/incident context, and one exact next action.

Project State does not collect live evidence itself and does not replace any specialist Monster subsystem.

## Authority boundaries

1. Monster Continuity V1 remains the authority for checkpoint/task/resume/drift evidence.
2. Monster Production Certification V1 remains the authority for production identity/readiness truth.
3. Existing sport-specific freeze/certification workflows and `devsystem-final-gate` remain authoritative merge vetoes.
4. Monster Live Bridge, Runtime Lab, Control Plane, Error Radar/PostHog, and Performance Profiler remain specialist evidence providers.
5. Project State consumes normalized packets only. Free text never changes classification by itself.

## State precedence

Classification is deterministic and fail-closed. Higher states below take precedence over lower states:

1. `BLOCKED`
   - explicit corruption/tamper evidence;
   - recorded Continuity blocker;
   - normalized incident explicitly marks execution blocked/unsafe;
   - required Production Certification reports an explicitly unsafe non-GREEN state;
   - contradictory production evidence says `GREEN` while `certified != true`.
2. `REVALIDATE`
   - Continuity status or drift evidence requires repository identity revalidation.
3. `UNKNOWN`
   - required Continuity or required Production Certification evidence is missing, malformed, unrecognized, or cannot support a safe classification.
4. `COMPLETE`
   - Continuity/task evidence explicitly marks the task complete.
5. `ACTIVE`
   - valid current task/step exists and remaining steps are non-empty.
6. `READY`
   - required evidence is valid, no higher-precedence state applies, and no remaining steps require continuation.

`UNKNOWN` must never be upgraded optimistically to `READY` or `ACTIVE`.

## Advisory evidence

- PostHog/Error Radar `NOT_CONFIGURED`, `UNAVAILABLE`, or `STALE` is advisory and does not independently block Project State.
- Performance grades `SLOW` or `CRITICAL` are advisory and do not independently invalidate production truth.
- Control Plane diagnosis is advisory to Project State classification.
- Runtime/incident evidence blocks only when the normalized packet explicitly marks execution blocked/unsafe.

## Permanent safety invariants

Project State V1 MUST NOT:

- modify projection math, Monte Carlo, sportsbook/market logic, identity rules, source data, sports schedules, or model outputs;
- modify Streamlit pages/routers or `app.py`;
- modify `sports_api/main.py` or `sports_api/api/health.py`;
- make live network calls;
- deploy, restart, create, update, or delete Render resources;
- enable Render auto-deploy;
- change environment variables;
- mutate GitHub branches or merge pull requests;
- auto-fix source code;
- replace Production Certification V1, sport-specific certifications, or `devsystem-final-gate`.

Frozen constants:

```text
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
AUTHORITATIVE_MERGE_GATE = devsystem-final-gate
```

## Determinism contract

Identical normalized inputs MUST produce identical packet content and classification. The classifier must not read clocks, network state, environment variables, filesystem runtime state, or random values.

Completed/remaining step order from Continuity must be preserved. A valid Continuity `next_action` must be preserved for `ACTIVE`, `READY`, and `COMPLETE`; higher-precedence `BLOCKED`, `REVALIDATE`, or `UNKNOWN` may replace it with their exact safety action.

## Workflow and scope contract

The implementation/certification surface is exactly four additive files:

- `sports_api/monster_project_state_v1.py`
- `tests/test_monster_project_state_v1.py`
- `.github/workflows/monster-project-state-v1.yml`
- `.github/monster-project-state-v1-contract.md`

The only additional feature-branch files permitted are the approved design and implementation-plan documents:

- `docs/superpowers/specs/2026-09-15-monster-project-state-v1-design.md`
- `docs/superpowers/plans/2026-09-15-monster-project-state-v1.md`

The focused workflow is a verification wrapper only. State classification policy lives in the tested Python module, not duplicated in YAML/shell.

Merging this subsystem MUST NOT trigger or perform a Render deployment; Render auto-deploy remains OFF.