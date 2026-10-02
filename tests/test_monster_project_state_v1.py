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
    PROOF_BUNDLE_AUTO_MUTATE,
    PROOF_BUNDLE_MAY_MODIFY_RUNTIME,
    PROOF_BUNDLE_MUTATION_AUTHORITY,
    PROOF_BUNDLE_NETWORK_CALLS,
    UNIFIED_PROOF_BUNDLE_VERSION,
    build_project_state,
    build_unified_proof_bundle,
    protection_snapshot,
    validate_unified_proof_bundle,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
PROD_SHA = "5" * 40
PROD_BRANCH = "mlb-step17b-shared-host-cert"


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
            "github_branch": PROD_BRANCH,
            "github_commit": PROD_SHA,
            "render_branch": PROD_BRANCH,
            "render_commit": PROD_SHA,
            "health_branch": PROD_BRANCH,
            "health_commit": PROD_SHA,
        },
        "render_status": "live",
        "render_auto_deploy": "no",
        "health_status": "ok",
        "readiness": {
            "status": "ready",
            "checks": {
                "process_running": True,
                "python_runtime": True,
                "deployment_identity_available": True,
                "runtime_branch_alignment": True,
            },
            "deployment_aligned": True,
        },
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


def test_wrong_continuity_version_fails_closed_unknown():
    continuity = _continuity(version="WRONG")

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "UNKNOWN"
    assert any("continuity version" in reason.lower() for reason in report["reasons"])


def test_unrecognized_continuity_resume_status_fails_closed_unknown():
    continuity = _continuity(status="GIBBERISH")

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "UNKNOWN"
    assert any("continuity status" in reason.lower() for reason in report["reasons"])


def test_unrecognized_continuity_task_status_fails_closed_unknown():
    continuity = _continuity()
    continuity["task"]["status"] = "GIBBERISH"

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "UNKNOWN"
    assert any("task.status" in reason.lower() for reason in report["reasons"])


def test_unrecognized_continuity_step_status_fails_closed_unknown():
    continuity = _continuity()
    continuity["progress"]["step_status"] = "GIBBERISH"

    report = build_project_state(continuity=continuity, production=_production())

    assert report["state"] == "UNKNOWN"
    assert any("step_status" in reason.lower() for reason in report["reasons"])


def test_wrong_production_certification_version_fails_closed_unknown():
    production = _production(version="WRONG")

    report = build_project_state(continuity=_continuity(), production=production)

    assert report["state"] == "UNKNOWN"
    assert any("production certification version" in reason.lower() for reason in report["reasons"])


def test_incomplete_green_production_packet_fails_closed_unknown():
    production = {
        "version": "MONSTER_PRODUCTION_CERTIFICATION_V1",
        "state": "GREEN",
        "certified": True,
    }

    report = build_project_state(continuity=_continuity(), production=production)

    assert report["state"] == "UNKNOWN"
    assert any("production certification" in reason.lower() for reason in report["reasons"])



PROOF_HEAD = "7" * 40
PROOF_ARTIFACT = "8" * 40
PROOF_DEPENDENCY = "9" * 40


def _proof_lane(run_id, status="SUCCESS", head_sha=PROOF_HEAD, test_count=21):
    return {
        "run_id": run_id,
        "status": status,
        "head_sha": head_sha,
        "test_count": test_count,
    }


def _proof_bundle(**overrides):
    packet = {
        "checkpoint_id": "MONSTER_V8_STEP4",
        "repository": "kyrepeak/kyre-sports-ai",
        "expected_head_sha": PROOF_HEAD,
        "observed_head_sha": PROOF_HEAD,
        "focused_proof": _proof_lane(101),
        "devsystem_proof": _proof_lane(102),
        "terminal_receipt_digest": "sha256:" + ("a" * 64),
        "artifacts": {"sports_api/monster_project_state_v1.py": PROOF_ARTIFACT},
        "dependencies": {"devsystem/terminal_proof_receipt_v1.py": PROOF_DEPENDENCY},
        "regression_debt_state": "CLEARED",
    }
    packet.update(overrides)
    return build_unified_proof_bundle(**packet)


def test_unified_proof_bundle_green_on_complete_exact_head_evidence():
    bundle = _proof_bundle()

    assert bundle["version"] == UNIFIED_PROOF_BUNDLE_VERSION
    assert bundle["status"] == "GREEN"
    assert bundle["exact_head"] is True
    assert bundle["blockers"] == []
    assert bundle["next_legal_action"] == "CERTIFICATION_BUNDLE_GREEN"


def test_unified_proof_bundle_exact_head_mismatch_blocks():
    bundle = _proof_bundle(observed_head_sha="6" * 40)

    assert bundle["status"] == "BLOCKED"
    assert "EXACT_HEAD_MISMATCH" in bundle["blockers"]
    assert bundle["next_legal_action"] == "REFRESH_HEAD_AND_REBUILD_PROOF_BUNDLE"


def test_unified_proof_bundle_focused_failure_blocks():
    bundle = _proof_bundle(
        focused_proof=_proof_lane(101, status="FAILURE"),
    )

    assert "FOCUSED_PROOF:NOT_SUCCESS" in bundle["blockers"]
    assert bundle["next_legal_action"] == "RESOLVE_EXACT_HEAD_PROOF_FAILURE"


def test_unified_proof_bundle_devsystem_head_mismatch_blocks():
    bundle = _proof_bundle(
        devsystem_proof=_proof_lane(102, head_sha="6" * 40),
    )

    assert "DEVSYSTEM_PROOF:HEAD_MISMATCH" in bundle["blockers"]


def test_unified_proof_bundle_requires_terminal_receipt_digest():
    bundle = _proof_bundle(terminal_receipt_digest="bad")

    assert "TERMINAL_RECEIPT_DIGEST_INVALID" in bundle["blockers"]
    assert bundle["next_legal_action"] == "RESOLVE_TERMINAL_RECEIPT"


def test_unified_proof_bundle_requires_artifact_identity():
    bundle = _proof_bundle(artifacts={})

    assert "ARTIFACT_IDENTITY_MISSING_OR_INVALID" in bundle["blockers"]


def test_unified_proof_bundle_requires_dependency_identity():
    bundle = _proof_bundle(dependencies={})

    assert "DEPENDENCY_IDENTITY_MISSING_OR_INVALID" in bundle["blockers"]


def test_unified_proof_bundle_blocks_uncleared_regression_debt():
    bundle = _proof_bundle(regression_debt_state="PENDING")

    assert "REGRESSION_DEBT_NOT_CLEARED" in bundle["blockers"]
    assert bundle["next_legal_action"] == "CLEAR_REGRESSION_DEBT"


def test_unified_proof_bundle_can_require_freeze():
    bundle = _proof_bundle(require_freeze=True)

    assert "FREEZE_RECORD_REQUIRED" in bundle["blockers"]
    assert bundle["next_legal_action"] == "REGISTER_OR_REPAIR_FROZEN_CHECKPOINT"


def test_unified_proof_bundle_accepts_exact_frozen_record():
    bundle = _proof_bundle(
        require_freeze=True,
        freeze_record={
            "status": "FROZEN",
            "source_main_sha": PROOF_HEAD,
            "registry_revision": 33,
            "state_hash": "b" * 64,
        },
    )

    assert bundle["status"] == "GREEN"


def test_unified_proof_bundle_rejects_freeze_head_drift():
    bundle = _proof_bundle(
        require_freeze=True,
        freeze_record={
            "status": "FROZEN",
            "source_main_sha": "6" * 40,
            "registry_revision": 33,
            "state_hash": "b" * 64,
        },
    )

    assert "FREEZE_HEAD_MISMATCH" in bundle["blockers"]


def test_unified_proof_bundle_can_require_deployment():
    bundle = _proof_bundle(require_deployment=True)

    assert "DEPLOYMENT_EVIDENCE_REQUIRED" in bundle["blockers"]
    assert bundle["next_legal_action"] == "RESTORE_DEPLOYMENT_CERTIFICATION"


def test_unified_proof_bundle_accepts_exact_green_deployment():
    bundle = _proof_bundle(
        require_deployment=True,
        deployment_evidence={
            "status": "GREEN",
            "head_sha": PROOF_HEAD,
            "certified": True,
        },
    )

    assert bundle["status"] == "GREEN"


def test_unified_proof_bundle_rejects_wrong_deployment_head():
    bundle = _proof_bundle(
        require_deployment=True,
        deployment_evidence={
            "status": "GREEN",
            "head_sha": "6" * 40,
            "certified": True,
        },
    )

    assert "DEPLOYMENT_HEAD_MISMATCH" in bundle["blockers"]


def test_unified_proof_bundle_checks_optional_lineage_identity():
    bundle = _proof_bundle(
        lineage_evidence={
            "status": "GREEN",
            "head_sha": "6" * 40,
            "lineage_digest": "sha256:" + ("c" * 64),
        },
    )

    assert "LINEAGE_HEAD_MISMATCH" in bundle["blockers"]


def test_unified_proof_bundle_is_byte_stable():
    one = _proof_bundle()
    two = _proof_bundle()

    assert one == two
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


def test_unified_proof_bundle_digest_detects_tampering():
    bundle = _proof_bundle()
    tampered = copy.deepcopy(bundle)
    tampered["focused_proof"]["run_id"] = 999

    try:
        validate_unified_proof_bundle(tampered)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered proof bundle was accepted")


def test_unified_proof_bundle_validate_green_contract():
    bundle = _proof_bundle()

    assert validate_unified_proof_bundle(bundle, require_green=True) == bundle


def test_unified_proof_bundle_never_grants_mutation_authority():
    bundle = _proof_bundle()

    assert PROOF_BUNDLE_NETWORK_CALLS is False
    assert PROOF_BUNDLE_AUTO_MUTATE is False
    assert PROOF_BUNDLE_MAY_MODIFY_RUNTIME is False
    assert PROOF_BUNDLE_MUTATION_AUTHORITY is False
    assert bundle["mutation_authority"] is False
    assert bundle["step_2a_required"] is True


# ---------------------------------------------------------------------------
# MONSTER V8 Step 4 — Unified Proof Bundle
# ---------------------------------------------------------------------------

import pytest

from sports_api.monster_project_state_v1 import (
    UNIFIED_PROOF_BUNDLE_VERSION,
    UnifiedProofBundleError,
    build_unified_proof_bundle,
    unified_proof_bundle_summary,
    validate_unified_proof_bundle,
)


_BUNDLE_PROOF_HEAD = "1" * 40
_BUNDLE_MERGED_MAIN = "2" * 40
_BUNDLE_CHECKPOINT = "MONSTER_V8_STEP4"
_BUNDLE_WORKSTREAM = "ws:monster-v8-step4-unified-proof-bundle-v1"


def _bundle_inputs(**overrides):
    payload = {
        "repository": "kyrepeak/kyre-sports-ai",
        "checkpoint_id": _BUNDLE_CHECKPOINT,
        "workstream_id": _BUNDLE_WORKSTREAM,
        "proof_head_sha": _BUNDLE_PROOF_HEAD,
        "merged_main_sha": _BUNDLE_MERGED_MAIN,
        "focused_proof": {
            "run_id": 4101,
            "head_sha": _BUNDLE_PROOF_HEAD,
            "conclusion": "success",
            "test_count": 47,
        },
        "devsystem_proof": {
            "run_id": 4102,
            "head_sha": _BUNDLE_PROOF_HEAD,
            "conclusion": "success",
            "final_gate": "success",
        },
        "terminal_receipt": {
            "run_id": 4102,
            "head_sha": _BUNDLE_PROOF_HEAD,
            "receipt_hash": "sha256:" + ("a" * 64),
            "artifact_id": 55123,
            "artifact_zip_sha256": "b" * 64,
        },
        "artifacts": {
            "sports_api/monster_project_state_v1.py": "3" * 40,
            "tests/test_monster_project_state_v1.py": "4" * 40,
        },
        "dependencies": {
            "devsystem/terminal_proof_receipt_v1.py": "5" * 40,
        },
        "deployment": {
            "required": False,
            "status": "NOT_REQUIRED",
        },
        "lineage": {
            "checkpoint_id": _BUNDLE_CHECKPOINT,
            "root_event_id": "write:monster-v8-step4",
            "lineage_digest": "sha256:" + ("6" * 64),
            "writer_count": 2,
            "consumer_count": 3,
        },
        "regression_debt": {
            "state": "CLEARED",
            "permanent_test": "tests/test_monster_project_state_v1.py",
        },
        "freeze_receipt": {
            "status": "FROZEN",
            "checkpoint_id": _BUNDLE_CHECKPOINT,
            "source_main_sha": _BUNDLE_MERGED_MAIN,
            "registry_revision": 99,
            "registry_state_hash": "7" * 64,
            "freeze_commit_sha": "8" * 40,
        },
        "proof_reuse": {
            "decision": "REUSE_APPROVED",
            "source_head_sha": _BUNDLE_PROOF_HEAD,
            "current_head_sha": _BUNDLE_MERGED_MAIN,
            "content_fingerprint": "9" * 64,
            "all_artifact_blobs_identical": True,
            "all_dependency_blobs_identical": True,
        },
    }
    payload.update(overrides)
    return payload


def test_unified_proof_bundle_builds_one_certified_packet():
    bundle = build_unified_proof_bundle(**_bundle_inputs())

    assert bundle["version"] == UNIFIED_PROOF_BUNDLE_VERSION
    assert bundle["certification_state"] == "CERTIFIED"
    assert bundle["complete"] is True
    assert bundle["focused_proof"]["test_count"] == 47
    assert bundle["devsystem_proof"]["final_gate"] == "success"
    assert bundle["regression_debt"]["state"] == "CLEARED"
    assert bundle["freeze_receipt"]["status"] == "FROZEN"
    assert bundle["bundle_digest"].startswith("sha256:")


def test_unified_proof_bundle_is_byte_stable_for_identical_inputs():
    one = build_unified_proof_bundle(**_bundle_inputs())
    two = build_unified_proof_bundle(**_bundle_inputs())

    assert one == two
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


def test_unified_proof_bundle_round_trip_validation_is_exact():
    bundle = build_unified_proof_bundle(**_bundle_inputs())

    assert validate_unified_proof_bundle(bundle) == bundle


def test_unified_proof_bundle_tamper_is_rejected():
    bundle = build_unified_proof_bundle(**_bundle_inputs())
    tampered = copy.deepcopy(bundle)
    tampered["focused_proof"]["test_count"] = 48

    with pytest.raises(UnifiedProofBundleError, match="tampered"):
        validate_unified_proof_bundle(tampered)


def test_focused_proof_must_bind_exact_proof_head():
    inputs = _bundle_inputs()
    inputs["focused_proof"] = {
        **inputs["focused_proof"],
        "head_sha": "f" * 40,
    }

    with pytest.raises(UnifiedProofBundleError, match="focused_proof.head_sha mismatch"):
        build_unified_proof_bundle(**inputs)


def test_focused_proof_must_be_successful():
    inputs = _bundle_inputs()
    inputs["focused_proof"] = {
        **inputs["focused_proof"],
        "conclusion": "failure",
    }

    with pytest.raises(UnifiedProofBundleError, match="must be successful"):
        build_unified_proof_bundle(**inputs)


def test_focused_proof_requires_positive_test_count():
    inputs = _bundle_inputs()
    inputs["focused_proof"] = {
        **inputs["focused_proof"],
        "test_count": 0,
    }

    with pytest.raises(UnifiedProofBundleError, match="test_count must be positive"):
        build_unified_proof_bundle(**inputs)


def test_devsystem_final_gate_must_be_success():
    inputs = _bundle_inputs()
    inputs["devsystem_proof"] = {
        **inputs["devsystem_proof"],
        "final_gate": "failure",
    }

    with pytest.raises(UnifiedProofBundleError, match="final_gate must be success"):
        build_unified_proof_bundle(**inputs)


def test_terminal_receipt_run_must_match_devsystem_run():
    inputs = _bundle_inputs()
    inputs["terminal_receipt"] = {
        **inputs["terminal_receipt"],
        "run_id": 9999,
    }

    with pytest.raises(UnifiedProofBundleError, match="must match devsystem proof run"):
        build_unified_proof_bundle(**inputs)


def test_invalid_artifact_blob_fails_closed():
    inputs = _bundle_inputs()
    inputs["artifacts"] = {
        "sports_api/monster_project_state_v1.py": "not-a-blob",
    }

    with pytest.raises(UnifiedProofBundleError, match="full git SHA"):
        build_unified_proof_bundle(**inputs)


def test_artifact_and_dependency_paths_cannot_overlap():
    inputs = _bundle_inputs()
    inputs["dependencies"] = {
        "sports_api/monster_project_state_v1.py": "5" * 40,
    }

    with pytest.raises(UnifiedProofBundleError, match="must not overlap"):
        build_unified_proof_bundle(**inputs)


def test_static_work_can_explicitly_skip_deployment():
    bundle = build_unified_proof_bundle(**_bundle_inputs())

    assert bundle["deployment"] == {
        "required": False,
        "status": "NOT_REQUIRED",
        "certified": False,
    }


def test_required_deployment_must_be_green_and_certified():
    inputs = _bundle_inputs()
    inputs["deployment"] = {
        "required": True,
        "status": "FAILED",
        "certified": False,
        "certified_sha": _BUNDLE_MERGED_MAIN,
        "receipt_digest": "c" * 64,
    }

    with pytest.raises(UnifiedProofBundleError, match="must be GREEN and certified"):
        build_unified_proof_bundle(**inputs)


def test_required_deployment_must_bind_merged_main():
    inputs = _bundle_inputs()
    inputs["deployment"] = {
        "required": True,
        "status": "GREEN",
        "certified": True,
        "certified_sha": "f" * 40,
        "receipt_digest": "c" * 64,
    }

    with pytest.raises(UnifiedProofBundleError, match="certified_sha mismatch"):
        build_unified_proof_bundle(**inputs)


def test_required_deployment_can_certify_exact_merged_main():
    inputs = _bundle_inputs()
    inputs["deployment"] = {
        "required": True,
        "status": "GREEN",
        "certified": True,
        "certified_sha": _BUNDLE_MERGED_MAIN,
        "receipt_digest": "c" * 64,
    }

    bundle = build_unified_proof_bundle(**inputs)

    assert bundle["deployment"]["status"] == "GREEN"
    assert bundle["deployment"]["certified_sha"] == _BUNDLE_MERGED_MAIN


def test_lineage_must_bind_same_checkpoint():
    inputs = _bundle_inputs()
    inputs["lineage"] = {
        **inputs["lineage"],
        "checkpoint_id": "OTHER",
    }

    with pytest.raises(UnifiedProofBundleError, match="lineage.checkpoint_id mismatch"):
        build_unified_proof_bundle(**inputs)


def test_regression_debt_must_be_cleared():
    inputs = _bundle_inputs()
    inputs["regression_debt"] = {
        **inputs["regression_debt"],
        "state": "OPEN",
    }

    with pytest.raises(UnifiedProofBundleError, match="must be CLEARED"):
        build_unified_proof_bundle(**inputs)


def test_freeze_receipt_must_bind_same_checkpoint():
    inputs = _bundle_inputs()
    inputs["freeze_receipt"] = {
        **inputs["freeze_receipt"],
        "checkpoint_id": "OTHER",
    }

    with pytest.raises(UnifiedProofBundleError, match="freeze_receipt.checkpoint_id mismatch"):
        build_unified_proof_bundle(**inputs)


def test_freeze_receipt_must_bind_exact_merged_main():
    inputs = _bundle_inputs()
    inputs["freeze_receipt"] = {
        **inputs["freeze_receipt"],
        "source_main_sha": "f" * 40,
    }

    with pytest.raises(UnifiedProofBundleError, match="source_main_sha mismatch"):
        build_unified_proof_bundle(**inputs)


def test_head_movement_requires_approved_proof_reuse():
    inputs = _bundle_inputs()
    inputs["proof_reuse"] = {
        **inputs["proof_reuse"],
        "decision": "NOT_REQUIRED",
    }

    with pytest.raises(UnifiedProofBundleError, match="requires REUSE_APPROVED"):
        build_unified_proof_bundle(**inputs)


def test_proof_reuse_requires_identical_artifact_and_dependency_blobs():
    inputs = _bundle_inputs()
    inputs["proof_reuse"] = {
        **inputs["proof_reuse"],
        "all_artifact_blobs_identical": False,
    }

    with pytest.raises(UnifiedProofBundleError, match="identical artifact blobs"):
        build_unified_proof_bundle(**inputs)


def test_same_head_uses_not_required_proof_reuse():
    same = "d" * 40
    inputs = _bundle_inputs(
        proof_head_sha=same,
        merged_main_sha=same,
    )
    inputs["focused_proof"] = {
        **inputs["focused_proof"],
        "head_sha": same,
    }
    inputs["devsystem_proof"] = {
        **inputs["devsystem_proof"],
        "head_sha": same,
    }
    inputs["terminal_receipt"] = {
        **inputs["terminal_receipt"],
        "head_sha": same,
    }
    inputs["freeze_receipt"] = {
        **inputs["freeze_receipt"],
        "source_main_sha": same,
    }
    inputs["proof_reuse"] = {
        "decision": "NOT_REQUIRED",
    }

    bundle = build_unified_proof_bundle(**inputs)

    assert bundle["proof_reuse"]["decision"] == "NOT_REQUIRED"


def test_unified_proof_bundle_summary_is_small_and_authoritative():
    bundle = build_unified_proof_bundle(**_bundle_inputs())
    summary = unified_proof_bundle_summary(bundle)

    assert summary["certification_state"] == "CERTIFIED"
    assert summary["focused_test_count"] == 47
    assert summary["artifact_count"] == 2
    assert summary["dependency_count"] == 1
    assert summary["regression_debt_state"] == "CLEARED"
    assert summary["freeze_status"] == "FROZEN"
    assert summary["complete"] is True
    assert summary["mutation_authority"] is False


def test_unified_proof_bundle_never_grants_mutation_authority():
    bundle = build_unified_proof_bundle(**_bundle_inputs())

    assert bundle["network_calls"] is False
    assert bundle["auto_fix"] is False
    assert bundle["may_modify_runtime"] is False
    assert bundle["mutation_authority"] is False
