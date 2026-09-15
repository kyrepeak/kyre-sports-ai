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
        "task": {
            "id": "project-state-v1",
            "title": "Monster Project State V1",
            "status": "ACTIVE",
        },
        "source": {
            "branch": "monster-project-state-v1",
            "commit": SHA_A,
            "main_commit": SHA_B,
            "pr_number": None,
        },
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
        "scope": {
            "in_scope": ["Project State V1"],
            "forbidden": ["sports projection math", "production runtime"],
        },
        "drift": {
            "status": "ALIGNED",
            "requires_revalidation": False,
            "reasons": [],
        },
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
        "identity": {
            "github_branch": "mlb-step17b-shared-host-cert",
            "github_commit": "5" * 40,
        },
        "render_status": "live",
        "render_auto_deploy": "no",
        "health_status": "ok",
        "readiness": {"status": "ready", "deployment_aligned": True},
        "guards": {
            "devsystem-final-gate": "green",
            "permanent-freeze": "green",
            "regression-shield": "green",
        },
        "reasons": [],
    }
    packet.update(overrides)
    return packet


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
    production = _production(
        state="IDENTITY_CONFLICT",
        certified=False,
        reasons=["runtime identity conflict"],
    )

    report = build_project_state(continuity=_continuity(), production=production)

    assert report["state"] == "BLOCKED"
    assert report["next_action"] == (
        "Restore Production Certification to GREEN before editing or merging."
    )


def test_continuity_drift_requires_revalidation():
    continuity = _continuity()
    continuity["status"] = "REVALIDATE"
    continuity["drift"] = {
        "status": "DRIFT",
        "requires_revalidation": True,
        "reasons": ["main advanced"],
    }

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "REVALIDATE"
    assert report["next_action"] == (
        "Revalidate repository identity and certification evidence before editing."
    )


def test_missing_required_continuity_is_unknown():
    report = build_project_state(continuity=None, production=_production())

    assert report["state"] == "UNKNOWN"
    assert report["next_action"] == (
        "Supply valid required Project State evidence before continuing."
    )


def test_malformed_required_continuity_is_unknown():
    report = build_project_state(
        continuity={"status": "READY_TO_RESUME"},
        production=_production(),
    )

    assert report["state"] == "UNKNOWN"
    assert report["reasons"]


def test_explicit_tamper_signal_is_blocked():
    continuity = _continuity(tampered=True)

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "BLOCKED"
    assert any("tamper" in reason.lower() for reason in report["reasons"])


def test_completed_task_is_complete():
    continuity = _continuity(status="COMPLETE")
    continuity["task"] = {
        "id": "project-state-v1",
        "title": "Monster Project State V1",
        "status": "COMPLETE",
    }
    continuity["progress"]["remaining_steps"] = []
    continuity["next_action"] = "Do not redo completed work."

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "COMPLETE"
    assert report["next_action"] == "Do not redo completed work."


def test_valid_idle_checkpoint_is_ready():
    continuity = _continuity()
    continuity["progress"]["remaining_steps"] = []
    continuity["progress"]["step_status"] = "GREEN"
    continuity["next_action"] = "Start the next approved task."

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "READY"
    assert report["next_action"] == "Start the next approved task."


def test_posthog_not_configured_is_advisory_not_blocking():
    telemetry = {
        "source": "posthog",
        "status": "NOT_CONFIGURED",
        "data": {"active_issue_count": 0},
    }

    report = build_project_state(
        continuity=_continuity(),
        production=_production(),
        telemetry=telemetry,
    )

    assert report["state"] == "ACTIVE"
    assert report["telemetry"]["status"] == "NOT_CONFIGURED"
    assert any("telemetry advisory" in reason.lower() for reason in report["reasons"])


def test_critical_performance_is_advisory_not_blocking():
    performance = {
        "version": "MONSTER_PERFORMANCE_PROFILER_V1",
        "grade": "CRITICAL",
        "bottleneck": "bootstrap.router",
    }

    report = build_project_state(
        continuity=_continuity(),
        production=_production(),
        performance=performance,
    )

    assert report["state"] == "ACTIVE"
    assert report["performance"]["grade"] == "CRITICAL"
    assert any("performance advisory" in reason.lower() for reason in report["reasons"])


def test_explicit_blocking_incident_blocks():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(),
        incident={
            "status": "BLOCKED",
            "blocking": True,
            "next_action": "Capture fresh runtime evidence.",
        },
    )

    assert report["state"] == "BLOCKED"
    assert report["next_action"] == "Capture fresh runtime evidence."


def test_unknown_production_stays_unknown_instead_of_becoming_ready():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(
            state="UNKNOWN",
            certified=False,
            reasons=["required guard evidence missing"],
        ),
    )

    assert report["state"] == "UNKNOWN"


def test_green_state_without_certified_true_is_blocked_as_contradictory():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(certified=False),
    )

    assert report["state"] == "BLOCKED"
    assert any("contradict" in reason.lower() for reason in report["reasons"])


def test_unrecognized_production_state_is_unknown():
    report = build_project_state(
        continuity=_continuity(),
        production=_production(state="MAYBE", certified=False),
    )

    assert report["state"] == "UNKNOWN"


def test_optional_production_can_be_absent_when_explicitly_out_of_scope():
    report = build_project_state(
        continuity=_continuity(),
        production=None,
        production_required=False,
    )

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
