from __future__ import annotations

from pathlib import Path

from sports_api.monster_incident_autopacket_v1 import IncidentInput, build_incident_packet
from sports_api.monster_runtime_capture_v1 import capture_response
from sports_api.monster_runtime_trace_v1 import ParityIdentity
from sports_api.monster_targeted_fix_planner_v1 import build_fix_plan

ROOT = Path(__file__).resolve().parents[1]


def _cfb_503_artifact():
    return capture_response(
        route_key="cfb_odds",
        url="https://api.test/api/v1/cfb/odds",
        status_code=503,
        headers={"X-Request-ID": "req-503"},
        json_body={
            "detail": "CFB odds endpoint is not ready: market identity coverage is incomplete"
        },
    )


def test_exact_protected_503_produces_verifier_only_plan():
    packet = build_incident_packet(
        IncidentInput(
            title="CFB protected 503",
            symptom="Verifier treats legitimate protected 503 as outage",
            target="devsystem/production_verify_v1.py",
            sport="CFB",
            replay_artifact=_cfb_503_artifact(),
        ),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert plan["status"] == "PLAN_READY"
    assert plan["root_cause_confidence"] == "HIGH"
    assert "generic HTTP error handling" in plan["root_cause"]
    assert "devsystem/production_verify_v1.py" in plan["edit_candidates"]
    assert "tests/test_devsystem_production_verify_v1.py" in plan["edit_candidates"]
    assert "tests/test_devsystem_production_verify_v1.py" in plan["required_tests"]
    assert "cfb-critical" in plan["required_tests"]
    assert "browser-qa" in plan["required_tests"]
    assert "devsystem-final-gate" in plan["required_tests"]
    assert any("wrong 503 detail" in item for item in plan["proof_before_merge"])


def test_parity_drift_blocks_logic_edits():
    packet = build_incident_packet(
        IncidentInput(
            title="stale deploy",
            symptom="source and runtime differ",
            parity_identity=ParityIdentity(
                source_branch="main",
                source_commit="new",
                runtime_branch="runtime",
                runtime_commit="old",
                expected_runtime_branch="runtime",
            ),
        ),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert plan["status"] == "BLOCKED_BY_PARITY"
    assert plan["edit_candidates"] == []
    assert "Align/verify" in plan["next_action"]


def test_unknown_incident_refuses_to_guess_a_fix():
    packet = build_incident_packet(
        IncidentInput(title="mystery", symptom="something seems off"),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert plan["status"] == "NEED_MORE_EVIDENCE"
    assert plan["root_cause_confidence"] == "LOW"
    assert plan["edit_candidates"] == []
    assert "Capture/replay" in plan["next_action"]


def test_unproven_named_target_is_inspection_only_not_edit_candidate():
    packet = build_incident_packet(
        IncidentInput(
            title="unproven target",
            symptom="caller suspects one file but has no deterministic evidence",
            target="sports_api/main.py",
        ),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert plan["status"] == "NEED_MORE_EVIDENCE"
    assert "sports_api/main.py" in plan["inspect_first"]
    assert plan["edit_candidates"] == []
    assert "before editing code" in plan["next_action"]


def test_exact_failure_memory_can_diagnose_without_inventing_edit_files():
    packet = build_incident_packet(
        IncidentInput(
            title="known cold start",
            symptom="cold start is slow",
            failure_signature="cfb ou cold start eagerly imports historical router spine before active page",
            target="streamlit_memory_lazy_router_v77.py",
            sport="CFB",
        ),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert plan["status"] == "PLAN_READY"
    assert plan["root_cause_confidence"] == "HIGH"
    assert any(item.startswith("exact_failure_memory:") for item in plan["evidence"])
    assert "streamlit_memory_lazy_router_v77.py" in plan["inspect_first"]
    # This historical record does not curate edit files, so the caller-supplied
    # target must stay inspection-only despite the high-confidence diagnosis.
    assert plan["edit_candidates"] == []


def test_planner_never_authorizes_fuzzy_identity_or_projection_mutation():
    packet = build_incident_packet(
        IncidentInput(title="x", symptom="x"),
        repo_root=ROOT,
    )
    plan = build_fix_plan(packet)
    assert any("fuzzy" in item for item in plan["forbidden_scope"])
    assert any("synthetic official IDs" in item for item in plan["forbidden_scope"])
    assert plan["protections"] == {
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "may_modify_source_data": False,
        "may_modify_runtime": False,
        "auto_fix": False,
        "fuzzy_matching": False,
    }
