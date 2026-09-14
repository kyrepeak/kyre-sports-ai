from __future__ import annotations

from pathlib import Path

from sports_api.monster_runtime_lab_v1 import run_runtime_lab

ROOT = Path(__file__).resolve().parents[1]


def test_exact_cfb_503_reproduces_old_failure_and_produces_targeted_plan():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="503",
        target="devsystem/production_verify_v1.py",
        sport="CFB",
        title="CFB verifier protected 503",
        symptom="generic helper raises before CFB body contract",
    )
    assert report["status"] == "READY_TO_PATCH"
    assert report["reproduction"]["legacy_helper"]["outcome"] == "raised_http_error"
    assert report["reproduction"]["legacy_helper"]["status_code"] == 503
    assert report["reproduction"]["body_aware_helper"]["outcome"] == "returned"
    assert report["reproduction"]["body_aware_helper"]["status_code"] == 503
    assert report["fix_plan"]["status"] == "PLAN_READY"
    assert "devsystem/production_verify_v1.py" in report["fix_plan"]["edit_candidates"]
    assert "tests/test_devsystem_production_verify_v1.py" in report["fix_plan"]["edit_candidates"]
    assert report["protections"]["projection_weight"] == 0.0
    assert report["protections"]["auto_fix"] is False
    assert report["protections"]["network_calls"] is False


def test_healthy_200_does_not_invent_a_code_fix_without_other_evidence():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="200",
        target="sports_api/monster_runtime_lab_v1.py",
        sport="CFB",
        title="Healthy request",
    )
    assert report["reproduction"]["legacy_helper"]["outcome"] == "returned"
    assert report["reproduction"]["body_aware_helper"]["outcome"] == "returned"
    assert report["status"] == "NEED_MORE_EVIDENCE"


def test_parity_drift_blocks_even_when_replay_is_actionable():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="503",
        target="devsystem/production_verify_v1.py",
        sport="CFB",
        source_branch="main",
        source_commit="new",
        runtime_branch="cert-runtime",
        runtime_commit="old",
        expected_runtime_branch="cert-runtime",
    )
    assert report["status"] == "BLOCKED"
    assert report["fix_plan"]["status"] == "BLOCKED_BY_PARITY"
    assert report["fix_plan"]["edit_candidates"] == []


def test_timeout_is_reproduced_without_network_access():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="timeout",
        target="sports_api/monster_runtime_lab_v1.py",
    )
    assert report["reproduction"]["legacy_helper"]["outcome"] == "timeout"
    assert report["reproduction"]["body_aware_helper"]["outcome"] == "timeout"
    assert report["protections"]["network_calls"] is False


def test_malformed_json_is_reproduced_and_not_misclassified_as_fix_ready():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="malformed_json",
        target="sports_api/monster_runtime_lab_v1.py",
    )
    assert report["reproduction"]["body_aware_helper"]["outcome"] == "raised"
    assert report["status"] == "NEED_MORE_EVIDENCE"


def test_exact_historical_failure_signature_can_upgrade_plan_confidence():
    report = run_runtime_lab(
        repo_root=ROOT,
        scenario="200",
        target="streamlit_memory_lazy_router_v77.py",
        sport="CFB",
        failure_signature="cfb ou cold start eagerly imports historical router spine before active page",
    )
    assert report["status"] == "READY_TO_PATCH"
    assert report["incident_packet"]["signals"]["failure_memory"]["exact"] is True
    assert report["fix_plan"]["root_cause_confidence"] == "HIGH"
