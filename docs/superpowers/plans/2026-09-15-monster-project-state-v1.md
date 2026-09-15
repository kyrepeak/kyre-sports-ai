# Monster Project State V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one deterministic, read-only Monster Project State V1 conductor that reduces normalized Continuity, Production Certification, Live Bridge/PostHog, Performance, Runtime Lab, and Control Plane evidence into a single current-project packet with an exact state and next action.

**Architecture:** `sports_api/monster_project_state_v1.py` is a pure classifier and packet builder. Callers supply already-normalized dictionaries; the module performs no network calls, does not import live connector clients, and never mutates sports/runtime state. Continuity owns task/checkpoint truth, Production Certification owns production truth, and all telemetry/performance/incident inputs remain advisory unless an existing normalized packet explicitly says execution is blocked or unsafe.

**Tech Stack:** Python 3.12 standard library, pytest, GitHub Actions, existing Monster Dependency Map, Monster One-Command Certification, Monster Production Certification tests, and protected `devsystem-final-gate`.

**Spec:** `docs/superpowers/specs/2026-09-15-monster-project-state-v1-design.md`

## Global Constraints

- `PROJECTION_WEIGHT = 0.0`.
- `MAY_MODIFY_PROJECTION = False`.
- `MAY_MODIFY_SOURCE_DATA = False`.
- `MAY_MODIFY_RUNTIME = False`.
- `NETWORK_CALLS = False`.
- `AUTO_FIX = False`.
- Project State V1 must not modify `app.py`, sports pages/routers/models/schedules/odds, `sports_api/main.py`, or `sports_api/api/health.py`.
- Project State V1 must not deploy/restart/create/update/delete Render resources, enable auto-deploy, change environment variables, merge pull requests, mutate branches, or auto-fix source code.
- Existing sport-specific freeze/certification workflows, Monster Production Certification V1, and `devsystem-final-gate` remain authoritative.
- PostHog/Error Radar and Monster Performance Profiler remain advisory and may not independently make production GREEN or Project State BLOCKED.
- Missing or malformed required evidence fails closed; Project State never invents missing truth.
- The implementation surface is exactly four additive implementation/certification files. The approved design and this plan are the only additional documentation files allowed on this feature branch.

---

## File Structure

- Create: `sports_api/monster_project_state_v1.py`
  - Pure normalization, validation, precedence classification, packet construction, and safety snapshot.
- Create: `tests/test_monster_project_state_v1.py`
  - Behavioral contracts for every state, precedence, advisory degradation, determinism, ordering, input immutability, and safety.
- Create: `.github/monster-project-state-v1-contract.md`
  - Permanent authority, state-precedence, advisory, determinism, and no-touch contract.
- Create: `.github/workflows/monster-project-state-v1.yml`
  - Focused compile/test/scope/static-safety/dependency/certification lane; no duplicated state-classification policy.
- Existing approved docs only:
  - `docs/superpowers/specs/2026-09-15-monster-project-state-v1-design.md`
  - `docs/superpowers/plans/2026-09-15-monster-project-state-v1.md`

The implementation module exposes only these public interfaces:

```python
PROJECT_STATE_VERSION = "MONSTER_PROJECT_STATE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"


def build_project_state(
    *,
    continuity: Mapping[str, Any] | None,
    production: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    performance: Mapping[str, Any] | None = None,
    incident: Mapping[str, Any] | None = None,
    control_plane: Mapping[str, Any] | None = None,
    production_required: bool = True,
) -> dict[str, Any]: ...


def protection_snapshot() -> dict[str, Any]: ...
```

The output contract is:

```python
{
    "version": "MONSTER_PROJECT_STATE_V1",
    "state": "READY|ACTIVE|BLOCKED|REVALIDATE|COMPLETE|UNKNOWN",
    "current_task": str,
    "current_step": str,
    "completed_steps": list[str],
    "remaining_steps": list[str],
    "last_green_evidence": list[str],
    "repository": dict,
    "production": dict,
    "telemetry": dict,
    "performance": dict,
    "incident": dict,
    "control_plane": dict,
    "blockers": list[str],
    "forbidden_scope": list[str],
    "next_action": str,
    "reasons": list[str],
    "projection_weight": 0.0,
    "may_modify_projection": False,
    "may_modify_source_data": False,
    "may_modify_runtime": False,
    "network_calls": False,
    "auto_fix": False,
    "authoritative_merge_gate": "devsystem-final-gate",
}
```

### Task 1: RED — Define Core Project-State Behavior

**Files:**
- Create: `tests/test_monster_project_state_v1.py`

**Interfaces:**
- Consumes: wished-for `build_project_state(...)` and safety constants from `sports_api.monster_project_state_v1`.
- Produces: executable behavioral requirements for the implementation in Task 2.

- [ ] **Step 1: Create the first failing behavioral tests**

Start the test file with deterministic packet helpers that mirror the already-certified normalized contracts:

```python
from __future__ import annotations

import copy
import json

from sports_api.monster_project_state_v1 import (
    AUTHORITATIVE_MERGE_GATE,
    AUTO_FIX,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_RUNTIME,
    MAY_MODIFY_SOURCE_DATA,
    NETWORK_CALLS,
    PROJECT_STATE_VERSION,
    PROJECTION_WEIGHT,
    build_project_state,
    protection_snapshot,
)

SHA_A = "a" * 40
SHA_B = "b" * 40


def _continuity(**overrides):
    packet = {
        "version": "MONSTER_CONTINUITY_V1",
        "status": "READY_TO_RESUME",
        "checkpoint_id": "MCP-0123456789ABCDEF",
        "task": {"id": "project-state-v1", "title": "Monster Project State V1", "status": "ACTIVE"},
        "source": {"branch": "monster-project-state-v1", "commit": SHA_A, "main_commit": SHA_B, "pr_number": None},
        "progress": {
            "current_step": "Implementation",
            "step_title": "TDD build",
            "step_status": "IN_PROGRESS",
            "completed_steps": ["P2.1", "P2.2", "P2.3", "P2.4", "P2.5"],
            "remaining_steps": ["Implementation", "Certification", "Integration"],
        },
        "last_green_evidence": ["Production Certification V1 GREEN"],
        "blockers": [],
        "next_action": "Write the Project State behavioral tests.",
        "scope": {"in_scope": ["Project State V1"], "forbidden": ["sports projection math", "production runtime"]},
        "drift": {"status": "ALIGNED", "requires_revalidation": False, "reasons": []},
        "resume_instruction": "Resume the approved Project State build.",
        "protections": {
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "may_modify_source_data": False,
            "may_modify_runtime": False,
            "network_calls": False,
            "auto_fix": False,
        },
    }
    packet.update(overrides)
    return packet


def _production(**overrides):
    packet = {
        "version": "MONSTER_PRODUCTION_CERTIFICATION_V1",
        "state": "GREEN",
        "certified": True,
        "identity": {"github_branch": "mlb-step17b-shared-host-cert", "github_commit": "5" * 40},
        "render_status": "live",
        "render_auto_deploy": "no",
        "health_status": "ok",
        "readiness": {"status": "ready", "deployment_aligned": True},
        "guards": {"devsystem-final-gate": "green", "permanent-freeze": "green", "regression-shield": "green"},
        "reasons": [],
    }
    packet.update(overrides)
    return packet
```

Then add these first tests:

```python
def test_active_checkpoint_with_green_production_is_active():
    report = build_project_state(continuity=_continuity(), production=_production())
    assert report["version"] == PROJECT_STATE_VERSION
    assert report["state"] == "ACTIVE"
    assert report["current_task"] == "Monster Project State V1"
    assert report["current_step"] == "Implementation"
    assert report["next_action"] == "Write the Project State behavioral tests."


def test_recorded_continuity_blocker_has_highest_blocking_precedence():
    continuity = _continuity()
    continuity["status"] = "BLOCKED"
    continuity["blockers"] = ["Focused CI is red"]
    report = build_project_state(continuity=continuity, production=_production())
    assert report["state"] == "BLOCKED"
    assert report["blockers"] == ["Focused CI is red"]
    assert report["next_action"] == "Resolve the recorded blocker before editing."


def test_non_green_production_blocks_when_production_is_required():
    production = _production(state="IDENTITY_CONFLICT", certified=False, reasons=["runtime identity conflict"])
    report = build_project_state(continuity=_continuity(), production=production)
    assert report["state"] == "BLOCKED"
    assert report["next_action"] == "Restore Production Certification to GREEN before editing or merging."
```

- [ ] **Step 2: Verify RED before any production implementation**

Run:

```bash
python -m pytest -q tests/test_monster_project_state_v1.py
```

Expected: collection fails because `sports_api.monster_project_state_v1` does not exist yet. This is the intentional RED proof. Do not create the production module before this failure has been observed.

- [ ] **Step 3: Commit the RED contract**

```bash
git add tests/test_monster_project_state_v1.py
git commit -m "test: define Monster Project State V1 core states"
```

### Task 2: GREEN — Implement the Minimal Classifier

**Files:**
- Create: `sports_api/monster_project_state_v1.py`
- Test: `tests/test_monster_project_state_v1.py`

**Interfaces:**
- Consumes: normalized dictionaries described by the spec; does not import or call Continuity, Live Bridge, Runtime Lab, Production Certification, PostHog, or Performance modules.
- Produces: `build_project_state(...) -> dict[str, Any]` and `protection_snapshot() -> dict[str, Any]`.

- [ ] **Step 1: Implement only enough normalization for the first three tests**

The module begins with standard-library imports only:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PROJECT_STATE_VERSION = "MONSTER_PROJECT_STATE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"

_UNSAFE_PRODUCTION_STATES = {
    "DEPLOY_FAILED",
    "RUNTIME_PROOF_FAILED",
    "NOT_READY",
    "IDENTITY_CONFLICT",
    "PRODUCTION_LAG",
    "GUARD_FAILED",
}
```

Implement tiny pure helpers for mapping/list/text extraction and `protection_snapshot()`. `build_project_state(...)` must copy data out of the input mappings, never mutate them, and satisfy the three RED tests without adding unrelated behavior.

- [ ] **Step 2: Verify GREEN for the core tests**

Run:

```bash
python -m pytest -q tests/test_monster_project_state_v1.py
```

Expected: the first three tests PASS.

- [ ] **Step 3: Commit the minimal GREEN classifier**

```bash
git add sports_api/monster_project_state_v1.py tests/test_monster_project_state_v1.py
git commit -m "feat: add Monster Project State V1 core classifier"
```

### Task 3: RED → GREEN — Complete Precedence, Advisory, and Determinism Contracts

**Files:**
- Modify: `tests/test_monster_project_state_v1.py`
- Modify: `sports_api/monster_project_state_v1.py`

**Interfaces:**
- Consumes: the Task 2 API unchanged.
- Produces: complete state precedence and stable output contract.

- [ ] **Step 1: Add the next failing tests one behavior at a time**

Add these behavioral cases:

```python
def test_continuity_drift_requires_revalidation():
    continuity = _continuity()
    continuity["status"] = "REVALIDATE"
    continuity["drift"] = {"status": "DRIFT", "requires_revalidation": True, "reasons": ["main advanced"]}
    report = build_project_state(continuity=continuity, production=_production())
    assert report["state"] == "REVALIDATE"
    assert report["next_action"] == "Revalidate repository identity and certification evidence before editing."


def test_missing_required_continuity_is_unknown():
    report = build_project_state(continuity=None, production=_production())
    assert report["state"] == "UNKNOWN"
    assert report["next_action"] == "Supply valid required Project State evidence before continuing."


def test_malformed_required_continuity_is_unknown():
    report = build_project_state(continuity={"status": "READY_TO_RESUME"}, production=_production())
    assert report["state"] == "UNKNOWN"


def test_explicit_tamper_signal_is_blocked():
    continuity = _continuity(tampered=True)
    report = build_project_state(continuity=continuity, production=_production())
    assert report["state"] == "BLOCKED"
    assert any("tamper" in reason.lower() for reason in report["reasons"])


def test_completed_task_is_complete():
    continuity = _continuity(status="COMPLETE")
    continuity["task"] = {"id": "project-state-v1", "title": "Monster Project State V1", "status": "COMPLETE"}
    continuity["progress"]["remaining_steps"] = []
    continuity["next_action"] = "Do not redo completed work."
    report = build_project_state(continuity=continuity, production=_production())
    assert report["state"] == "COMPLETE"


def test_posthog_not_configured_is_advisory_not_blocking():
    telemetry = {"source": "posthog", "status": "NOT_CONFIGURED", "data": {"active_issue_count": 0}}
    report = build_project_state(continuity=_continuity(), production=_production(), telemetry=telemetry)
    assert report["state"] == "ACTIVE"
    assert report["telemetry"]["status"] == "NOT_CONFIGURED"
    assert any("telemetry advisory" in reason.lower() for reason in report["reasons"])


def test_critical_performance_is_advisory_not_blocking():
    performance = {"version": "MONSTER_PERFORMANCE_PROFILER_V1", "grade": "CRITICAL", "bottleneck": "bootstrap.router"}
    report = build_project_state(continuity=_continuity(), production=_production(), performance=performance)
    assert report["state"] == "ACTIVE"
    assert report["performance"]["grade"] == "CRITICAL"


def test_explicit_blocking_incident_blocks():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(),
        incident={"status": "BLOCKED", "blocking": True, "next_action": "Capture fresh runtime evidence."},
    )
    assert report["state"] == "BLOCKED"


def test_unknown_production_stays_unknown_instead_of_becoming_ready():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(state="UNKNOWN", certified=False, reasons=["required guard evidence missing"]),
    )
    assert report["state"] == "UNKNOWN"


def test_green_state_without_certified_true_is_blocked_as_contradictory():
    report = build_project_state(continuity=_continuity(), production=_production(certified=False))
    assert report["state"] == "BLOCKED"


def test_optional_production_can_be_absent_when_explicitly_out_of_scope():
    report = build_project_state(continuity=_continuity(), production=None, production_required=False)
    assert report["state"] == "ACTIVE"


def test_step_order_and_exact_next_action_are_preserved():
    continuity = _continuity()
    report = build_project_state(continuity=continuity, production=_production())
    assert report["completed_steps"] == continuity["progress"]["completed_steps"]
    assert report["remaining_steps"] == continuity["progress"]["remaining_steps"]
    assert report["next_action"] == continuity["next_action"]


def test_identical_inputs_produce_byte_stable_json():
    inputs = {"continuity": _continuity(), "production": _production()}
    one = build_project_state(**inputs)
    two = build_project_state(**inputs)
    assert one == two
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


def test_inputs_are_not_mutated():
    continuity = _continuity()
    production = _production()
    before = copy.deepcopy((continuity, production))
    build_project_state(continuity=continuity, production=production)
    assert (continuity, production) == before
```

Add a READY case with a valid checkpoint that has no remaining steps, is not complete, has no blocker/drift, and supplies a safe exact next action.

- [ ] **Step 2: Run the focused suite and confirm each newly added test is RED for missing behavior**

Run:

```bash
python -m pytest -q tests/test_monster_project_state_v1.py
```

Expected before implementation changes: one or more of the new tests fail for the missing precedence/advisory behavior.

- [ ] **Step 3: Implement deterministic precedence exactly in this order**

```text
BLOCKED
  explicit corruption/tamper
  explicit continuity blocker
  explicit blocking incident
  explicit unsafe non-GREEN production
  contradictory GREEN-but-not-certified production
REVALIDATE
  continuity REVALIDATE or drift.requires_revalidation == True
UNKNOWN
  missing/malformed required continuity
  missing required production when production_required=True
  production state UNKNOWN or unrecognized
COMPLETE
  continuity/task explicitly complete
ACTIVE
  valid current step + remaining steps
READY
  valid evidence, no higher state, no remaining steps, not complete
```

State-specific next actions are exact constants:

```python
_BLOCKED_CONTINUITY_ACTION = "Resolve the recorded blocker before editing."
_BLOCKED_PRODUCTION_ACTION = "Restore Production Certification to GREEN before editing or merging."
_REVALIDATE_ACTION = "Revalidate repository identity and certification evidence before editing."
_UNKNOWN_ACTION = "Supply valid required Project State evidence before continuing."
```

For `ACTIVE`, `READY`, and `COMPLETE`, preserve the exact valid Continuity `next_action`. Do not synthesize a different action when Continuity already has one.

Advisory packet defaults:

```python
telemetry -> {"status": "UNAVAILABLE"} when absent
performance -> {"status": "UNAVAILABLE"} when absent
incident -> {"status": "UNAVAILABLE", "blocking": False} when absent
control_plane -> {"status": "UNAVAILABLE"} when absent
```

- [ ] **Step 4: Verify the full focused suite is GREEN**

Run:

```bash
python -m pytest -q tests/test_monster_project_state_v1.py
python -m py_compile sports_api/monster_project_state_v1.py
```

Expected: all Project State tests PASS and compile is clean.

- [ ] **Step 5: Commit the complete deterministic classifier**

```bash
git add sports_api/monster_project_state_v1.py tests/test_monster_project_state_v1.py
git commit -m "feat: complete Monster Project State V1 precedence"
```

### Task 4: Add Permanent Safety Contract and Focused Certification Workflow

**Files:**
- Create: `.github/monster-project-state-v1-contract.md`
- Create: `.github/workflows/monster-project-state-v1.yml`
- Test: `tests/test_monster_project_state_v1.py`

**Interfaces:**
- Consumes: the stable Project State API from Tasks 2–3.
- Produces: repository-level certification and scope protection without adding runtime authority.

- [ ] **Step 1: Write the permanent contract**

The contract must state verbatim-equivalent rules for:

```text
Purpose: read-only current-project truth conductor.
Only normalized input packets are consumed; no live collection belongs here.
Production Certification V1 remains production-truth authority.
Continuity remains checkpoint/task-truth authority.
PostHog and Performance remain advisory.
State precedence: BLOCKED > REVALIDATE > UNKNOWN > COMPLETE > ACTIVE > READY.
Only explicit normalized blocker/unsafe fields may block; free text never changes state.
No production entrypoints, network calls, auto-fix, source/model/runtime mutation, deploys, merges, env changes, or auto-deploy changes.
Projection influence is exactly 0.0%.
devsystem-final-gate remains the authoritative merge veto.
```

- [ ] **Step 2: Create the focused workflow wrapper**

The workflow paths are exactly the four implementation/certification files plus the two approved docs. It must:

1. check out the PR with enough history to compare against the base;
2. use Python 3.12;
3. install repository requirements and pytest;
4. compile `sports_api/monster_project_state_v1.py`;
5. run `python -m pytest -q tests/test_monster_project_state_v1.py`;
6. run an AST source-safety check that rejects imports rooted at `requests`, `urllib`, `http`, `socket`, or `subprocess` in the Project State module;
7. assert `protection_snapshot()` exactly matches the frozen safety constants;
8. build one deterministic ACTIVE sample with GREEN production and `PostHog=NOT_CONFIGURED`, proving telemetry is advisory;
9. run Dependency Map and require `impacted_entrypoints == []` for the new module;
10. run `python -m sports_api.monster_certification_v1 --json` and require PASS / zero failed checks;
11. run `python -m pytest -q tests/test_monster_production_certification_snapshot_v1.py`;
12. enforce the exact branch surface below.

Exact allowed branch paths relative to protected `main`:

```text
.github/monster-project-state-v1-contract.md
.github/workflows/monster-project-state-v1.yml
docs/superpowers/specs/2026-09-15-monster-project-state-v1-design.md
docs/superpowers/plans/2026-09-15-monster-project-state-v1.md
sports_api/monster_project_state_v1.py
tests/test_monster_project_state_v1.py
```

The scope check must fail for any seventh path and must separately assert that the four non-doc implementation/certification paths are exactly the approved four-file surface.

The workflow must not deploy Render, alter Render configuration, write environment variables, modify protected `main`, or duplicate the Python state-precedence policy in YAML/shell.

- [ ] **Step 3: Add source-level contract assertions to the focused test file**

Add tests that inspect only the new module and contract, not frozen sports files:

```python
def test_safety_constants_never_authorize_mutation():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert MAY_MODIFY_RUNTIME is False
    assert NETWORK_CALLS is False
    assert AUTO_FIX is False
    assert AUTHORITATIVE_MERGE_GATE == "devsystem-final-gate"
    assert protection_snapshot() == {
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "may_modify_source_data": False,
        "may_modify_runtime": False,
        "network_calls": False,
        "auto_fix": False,
        "authoritative_merge_gate": "devsystem-final-gate",
    }
```

- [ ] **Step 4: Run focused local verification**

Run:

```bash
python -m py_compile sports_api/monster_project_state_v1.py
python -m pytest -q tests/test_monster_project_state_v1.py
python -m pytest -q tests/test_monster_production_certification_snapshot_v1.py
python -m sports_api.monster_certification_v1 --json
```

Expected: all commands complete successfully; Monster certification reports `status=PASS` and `failed_check_count=0`.

- [ ] **Step 5: Commit workflow and permanent contract**

```bash
git add .github/monster-project-state-v1-contract.md .github/workflows/monster-project-state-v1.yml tests/test_monster_project_state_v1.py
git commit -m "ci: certify Monster Project State V1"
```

### Task 5: PR Certification, Exact-Scope Review, and Protected-Main Handoff

**Files:**
- No new implementation files.
- Review the six allowed branch paths only.

**Interfaces:**
- Consumes: complete Project State branch.
- Produces: a reviewable PR that protected repository checks may either certify or reject.

- [ ] **Step 1: Verify branch scope before opening the PR**

Compare the feature branch against protected `main` and require exactly these six paths:

```text
.github/monster-project-state-v1-contract.md
.github/workflows/monster-project-state-v1.yml
docs/superpowers/specs/2026-09-15-monster-project-state-v1-design.md
docs/superpowers/plans/2026-09-15-monster-project-state-v1.md
sports_api/monster_project_state_v1.py
tests/test_monster_project_state_v1.py
```

Confirm specifically that none of these changed:

```text
app.py
sports_api/main.py
sports_api/api/health.py
sports models/projections/Monte Carlo modules
sportsbook/market collectors
active Streamlit routers/pages
Render configuration
```

- [ ] **Step 2: Open a PR to protected `main`**

The PR body must include:

```text
Purpose: additive read-only Monster Project State V1.
State precedence: BLOCKED > REVALIDATE > UNKNOWN > COMPLETE > ACTIVE > READY.
Four implementation/certification files + two approved docs only.
No production deployment.
No frozen sports/runtime edits.
Production Certification V1 remains authoritative.
PostHog and Performance remain advisory.
```

- [ ] **Step 3: Review focused CI and protected permanent gates**

Required proof before any merge claim:

```text
Monster Project State V1 focused workflow: GREEN
Project State tests: GREEN
Production Certification V1 tests: GREEN
Monster one-command certification: PASS
Dependency Map: impacted_entrypoints=[]
permanent contract/regression/freeze lanes required by repository: GREEN
devsystem-final-gate: GREEN
unresolved review blockers: 0
```

If any check fails, write a failing regression test when behavior is involved, fix only the smallest scoped cause, and re-run the exact gate. Do not broaden scope or touch frozen sports/runtime code to make CI green.

- [ ] **Step 4: Verify no production action occurred**

Confirm Render still has auto-deploy OFF and that this Project State branch/PR did not trigger a Render deployment or configuration mutation. Production Certification V1 may be read for proof; Project State itself performs no production action.

- [ ] **Step 5: Final pre-merge checkpoint**

Before saying the subproject is complete, record:

```text
feature branch exact head SHA
protected main SHA
PR number
focused test count/result
production-certification test result
Monster certification result
Dependency Map entrypoint result
protected final-gate result
exact changed-file list
Render live commit and auto-deploy state
```

Only after all required checks are GREEN may protected-main integration proceed. PostHog Operational Activation remains a separate follow-on subproject and must not be folded into this PR.

---

## Plan Self-Review

- **Spec coverage:** every required output field, precedence state, advisory rule, no-touch boundary, deterministic requirement, and certification requirement maps to Tasks 1–5.
- **Placeholder scan:** no TBD/TODO/“implement later” instructions are present.
- **Type consistency:** the only production entry interface is `build_project_state(...)`; all tasks use the same parameter names and dictionary return type.
- **Scope check:** PostHog Operational Activation is explicitly excluded and remains its own future design/plan.
