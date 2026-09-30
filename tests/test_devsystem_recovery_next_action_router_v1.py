from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.deployment_truth_control_plane_v1 import build_deployment_truth
from devsystem.failure_ownership_engine_v1 import classify_failure
from devsystem.recovery_next_action_router_v1 import (
    RecoveryRouteFailure,
    contract_self_test,
    route_next_action,
    validate_route,
)


MAIN = "a" * 40
OLD = "b" * 40


def _decision(owner: str):
    cases = {
        "PRODUCT": {
            "job": "wnba-critical",
            "layer": "wnba",
            "evidence_signal": "test-assertion",
        },
        "VERIFIER": {
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
        },
        "CI": {
            "job": "workflow-hygiene",
            "layer": "workflow-control",
            "evidence_signal": "cache-dependency",
        },
        "DEPLOYMENT": {
            "job": "production-verification",
            "layer": "deployment",
            "evidence_signal": "deployment-drift",
        },
        "EXTERNAL": {
            "job": "wnba-critical",
            "layer": "wnba",
            "evidence_signal": "network-upstream",
        },
    }
    return classify_failure(cases[owner])


def test_live_async_run_blocks_all_competing_actions():
    result = route_next_action(_decision("VERIFIER"), async_state="IN_PROGRESS")
    assert result["action"] == "WAIT_FOR_AUTHORITATIVE_RUN"
    assert result["mutation_authorized"] is False
    assert result["product_mutation_allowed"] is False


def test_stale_evidence_always_routes_to_refresh():
    stale = classify_failure(
        {"job": "wnba-critical", "layer": "wnba", "evidence_signal": "test-assertion"},
        evidence_freshness="STALE_MAIN",
    )
    result = route_next_action(stale, evidence_freshness="STALE_MAIN")
    assert result["action"] == "REFRESH_EVIDENCE"
    assert result["mutation_authorized"] is False


def test_verifier_patch_must_stay_in_verifier_scope():
    result = route_next_action(
        _decision("VERIFIER"),
        proposed_paths=["devsystem/browser_qa_v1.py"],
    )
    assert result["action"] == "PATCH_OWNER_SCOPE"
    assert result["mutation_authorized"] is True
    assert result["path_classes"] == ["VERIFIER"]
    assert result["product_mutation_allowed"] is False

    with pytest.raises(RecoveryRouteFailure, match="owner VERIFIER cannot mutate PRODUCT"):
        route_next_action(_decision("VERIFIER"), proposed_paths=["app.py"])


def test_product_patch_requires_exact_product_scope():
    result = route_next_action(
        _decision("PRODUCT"),
        proposed_paths=["wnba_pra_v1.py"],
    )
    assert result["mutation_authorized"] is True
    assert result["product_mutation_allowed"] is True


def test_external_failure_never_patches_repository():
    result = route_next_action(_decision("EXTERNAL"))
    assert result["action"] == "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"
    assert result["mutation_authorized"] is False


def test_deployment_stale_routes_to_redeploy_not_product_patch():
    truth = build_deployment_truth(
        github_main_sha=MAIN,
        production_sha=OLD,
        build_id="build-old",
        deploy_id="deploy-old",
        health_sha=OLD,
        readiness_sha=OLD,
        ui_proof_sha=OLD,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=True,
    )
    result = route_next_action(_decision("DEPLOYMENT"), deployment_truth=truth)
    assert result["action"] == "REFRESH_OR_REDEPLOY_PRODUCTION"
    assert result["mutation_authorized"] is False
    assert result["product_mutation_allowed"] is False


def test_deployment_owner_without_truth_collects_identity():
    result = route_next_action(_decision("DEPLOYMENT"))
    assert result["action"] == "COLLECT_DEPLOYMENT_IDENTITY"
    assert result["mutation_authorized"] is False


def test_route_fingerprint_detects_tampering():
    result = route_next_action(_decision("EXTERNAL"))
    tampered = copy.deepcopy(result)
    tampered["action"] = "PATCH_OWNER_SCOPE"
    with pytest.raises(RecoveryRouteFailure, match="fingerprint mismatch"):
        validate_route(tampered)


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["one_action_only"] is True
    assert result["live_async_waits"] is True
    assert result["verifier_scope_patch"] is True
    assert result["external_no_patch"] is True
    assert result["stale_refresh_only"] is True
    assert result["deployment_stale_redeploy"] is True
    assert result["product_runtime_mutation"] is False


def test_engine_runs_directly_as_permanent_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "recovery_next_action_router_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_RECOVERY_NEXT_ACTION_ROUTER_V1_GREEN" in completed.stdout
