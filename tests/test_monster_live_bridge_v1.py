from __future__ import annotations

from pathlib import Path

import pytest

from sports_api.monster_continuity_v1 import CheckpointInput, build_checkpoint
from sports_api.monster_incident_autopacket_v1 import IncidentInput
from sports_api.monster_live_bridge_v1 import (
    AUTO_FIX,
    FUZZY_MATCHING,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_RUNTIME,
    MAY_MODIFY_SOURCE_DATA,
    NETWORK_CALLS,
    PROJECTION_WEIGHT,
    SourceEvidence,
    build_live_bridge,
    compare_deployment_parity,
    github_evidence,
    posthog_evidence,
    render_evidence,
    unavailable_source,
)

ROOT = Path(__file__).resolve().parents[1]
SHA_A = "a" * 40
SHA_B = "b" * 40
STAMP = "2026-09-14T23:00:00Z"


def _github(*, gate: str = "SUCCESS", sha: str = SHA_A, reviews: int = 0):
    return github_evidence(
        main_sha=sha,
        working_branch="main",
        working_sha=sha,
        final_gate=gate,
        unresolved_review_threads=reviews,
        expected_deploy_sha=sha,
        expected_deploy_branch="main",
        observed_at_utc=STAMP,
    )


def _render(*, sha: str = SHA_A, branch: str = "main", deploy_status: str = "LIVE"):
    return render_evidence(
        service_id="srv-test",
        service_name="kyre-api",
        branch=branch,
        deployed_commit=sha,
        deploy_id="dep-test",
        deploy_status=deploy_status,
        observed_at_utc=STAMP,
    )


def _posthog(*, issues: int = 0, slow: int = 0):
    return posthog_evidence(
        project="test-project",
        active_issue_count=issues,
        slow_request_count=slow,
        observed_at_utc=STAMP,
    )


def _cert(status: str = "PASS", failed: int = 0):
    return {
        "status": status,
        "passed_check_count": 7 if not failed else 6,
        "required_check_count": 7,
        "failed_check_count": failed,
    }


def _health_incident():
    return IncidentInput(title="live health", symptom="")


def _checkpoint(*, main_sha: str = SHA_A, task_status: str = "ACTIVE", blockers=()):
    return build_checkpoint(
        CheckpointInput(
            task_id="bridge-test",
            task_title="Bridge Test",
            repo="kyrepeak/kyre-sports-ai",
            source_branch="main",
            source_commit=SHA_A,
            main_commit=main_sha,
            current_step="G",
            step_title="Live proof",
            next_action="Continue certification",
            task_status=task_status,
            step_status="COMPLETE" if task_status == "COMPLETE" else "IN_PROGRESS",
            blockers=tuple(blockers),
            created_at_utc=STAMP,
        )
    )


def test_source_evidence_recursively_redacts_credentials():
    evidence = SourceEvidence(
        source="posthog",
        status="AVAILABLE",
        observed_at_utc=STAMP,
        data={
            "Authorization": "Bearer top-secret",
            "nested": [
                "Bearer abc123",
                {"password": "hunter2", "url": "https://user:pass@example.com/x?token=abc"},
            ],
        },
        note="Basic Zm9vOmJhcg==",
    ).as_dict()
    assert evidence["data"]["Authorization"] == "<redacted>"
    assert evidence["data"]["nested"][0] == "<redacted>"
    assert evidence["data"]["nested"][1]["password"] == "<redacted>"
    assert "user:pass" not in evidence["data"]["nested"][1]["url"]
    assert "token=abc" not in evidence["data"]["nested"][1]["url"]
    assert evidence["note"] == "<redacted>"


def test_invalid_source_state_fails_closed():
    with pytest.raises(ValueError):
        SourceEvidence(source="x", status="MAYBE")


def test_deployment_parity_aligned():
    result = compare_deployment_parity(_github(), _render())
    assert result["status"] == "ALIGNED"
    assert result["blocking"] is False


def test_deployment_commit_drift_blocks():
    result = compare_deployment_parity(_github(), _render(sha=SHA_B))
    assert result["status"] == "DRIFT"
    assert result["blocking"] is True
    assert any("commit drift" in item for item in result["reasons"])


def test_deployment_branch_drift_blocks():
    result = compare_deployment_parity(_github(), _render(branch="old-branch"))
    assert result["status"] == "DRIFT"
    assert any("branch drift" in item for item in result["reasons"])


def test_unavailable_render_makes_parity_unknown_not_fabricated():
    result = compare_deployment_parity(_github(), unavailable_source("render"))
    assert result["status"] == "UNKNOWN"
    assert result["blocking"] is False


def test_all_green_live_health_is_healthy_and_release_ready():
    report = build_live_bridge(
        _health_incident(),
        github=_github(),
        render=_render(),
        posthog=_posthog(),
        certification_receipt=_cert(),
        repo_root=ROOT,
    )
    assert report["status"] == "HEALTHY"
    assert report["release"]["status"] == "READY"
    assert report["deployment_parity"]["status"] == "ALIGNED"
    assert report["next_action"].startswith("No immediate action")


def test_missing_certification_never_claims_release_ready():
    report = build_live_bridge(
        _health_incident(),
        github=_github(),
        render=_render(),
        posthog=_posthog(),
        certification_receipt=None,
        repo_root=ROOT,
    )
    assert report["release"]["status"] == "UNKNOWN"
    assert report["status"] == "DEGRADED"


def test_failed_final_gate_blocks():
    report = build_live_bridge(
        _health_incident(), github=_github(gate="FAILURE"), render=_render(),
        posthog=_posthog(), certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "BLOCKED"
    assert report["release"]["status"] == "BLOCKED"
    assert any("devsystem-final-gate" in item for item in report["release"]["blockers"])


def test_unresolved_review_thread_blocks():
    report = build_live_bridge(
        _health_incident(), github=_github(reviews=2), render=_render(),
        posthog=_posthog(), certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "BLOCKED"
    assert any("unresolved review" in item for item in report["release"]["blockers"])


def test_render_deploy_failure_blocks():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(deploy_status="FAILED"),
        posthog=_posthog(), certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "BLOCKED"
    assert any("Render deploy status" in item for item in report["release"]["blockers"])


def test_certification_failure_blocks():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=_posthog(),
        certification_receipt=_cert(status="FAIL", failed=1), repo_root=ROOT,
    )
    assert report["status"] == "BLOCKED"
    assert report["certification"]["blocking"] is True


def test_render_unavailable_degrades_gracefully():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=unavailable_source("render"),
        posthog=_posthog(), certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "DEGRADED"
    assert report["deployment_parity"]["status"] == "UNKNOWN"
    assert any("render evidence is UNAVAILABLE" in item for item in report["release"]["warnings"])


def test_posthog_not_configured_degrades_gracefully():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=None,
        certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "DEGRADED"
    assert report["sources"]["posthog"]["status"] == "NOT_CONFIGURED"


def test_posthog_active_errors_require_action():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=_posthog(issues=3),
        certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "ACTION_REQUIRED"
    assert any("3 active error" in item for item in report["signals"])


def test_posthog_slow_requests_require_action():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=_posthog(slow=5),
        certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["status"] == "ACTION_REQUIRED"
    assert any("5 slow request" in item for item in report["signals"])


def test_continuity_aligned_does_not_block():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=_posthog(),
        certification_receipt=_cert(), continuity_checkpoint=_checkpoint(),
        current_branch="main", current_commit=SHA_A, current_main_commit=SHA_A,
        repo_root=ROOT,
    )
    assert report["continuity"]["status"] == "READY_TO_RESUME"
    assert report["status"] == "HEALTHY"


def test_continuity_main_drift_blocks_for_revalidation():
    report = build_live_bridge(
        _health_incident(), github=_github(sha=SHA_B), render=_render(sha=SHA_B), posthog=_posthog(),
        certification_receipt=_cert(), continuity_checkpoint=_checkpoint(main_sha=SHA_A),
        current_branch="main", current_commit=SHA_A, current_main_commit=SHA_B,
        repo_root=ROOT,
    )
    assert report["continuity"]["status"] == "REVALIDATE"
    assert report["status"] == "BLOCKED"
    assert any("Continuity checkpoint" in item for item in report["release"]["blockers"])


def test_complete_continuity_checkpoint_does_not_create_fake_incident():
    report = build_live_bridge(
        _health_incident(), github=_github(), render=_render(), posthog=_posthog(),
        certification_receipt=_cert(), continuity_checkpoint=_checkpoint(task_status="COMPLETE"),
        current_branch="main", current_commit=SHA_A, current_main_commit=SHA_A,
        repo_root=ROOT,
    )
    assert report["continuity"]["status"] == "COMPLETE"
    assert report["incident"]["active"] is False
    assert report["status"] == "HEALTHY"


def test_active_unknown_incident_is_degraded_not_healthy():
    report = build_live_bridge(
        IncidentInput(title="mystery", symptom="something broke"),
        github=_github(), render=_render(), posthog=_posthog(),
        certification_receipt=_cert(), repo_root=ROOT,
    )
    assert report["incident"]["active"] is True
    assert report["incident"]["fix_plan"]["status"] == "NEED_MORE_EVIDENCE"
    assert report["status"] == "DEGRADED"
    assert "evidence" in report["next_action"].lower() or "capture" in report["next_action"].lower()


def test_protection_constants_never_authorize_mutation():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert MAY_MODIFY_RUNTIME is False
    assert NETWORK_CALLS is False
    assert AUTO_FIX is False
    assert FUZZY_MATCHING is False
