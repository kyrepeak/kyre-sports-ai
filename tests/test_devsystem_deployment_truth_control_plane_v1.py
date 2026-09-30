from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.deployment_truth_control_plane_v1 import (
    DeploymentTruthFailure,
    build_deployment_truth,
    contract_self_test,
    validate_deployment_truth,
)


MAIN = "a" * 40
OLD = "b" * 40


def _evidence(**overrides):
    value = {
        "github_main_sha": MAIN,
        "production_sha": MAIN,
        "build_id": "build-123",
        "deploy_id": "dep-123",
        "health_sha": MAIN,
        "readiness_sha": MAIN,
        "ui_proof_sha": MAIN,
        "health_ok": True,
        "readiness_ok": True,
        "ui_proof_ok": True,
    }
    value.update(overrides)
    return value


def test_exact_main_to_public_identity_is_deployment_parity():
    result = build_deployment_truth(**_evidence())
    assert result["state"] == "DEPLOYMENT_PARITY"
    assert result["parity"] is True
    assert result["certified"] is True
    assert result["owner"] == "DEPLOYMENT"
    assert result["product_mutation_allowed"] is False
    assert result["next_legal_action"] == "FREEZE_DEPLOYMENT_TRUTH"


def test_consistently_old_production_is_stale_deployment_not_product_failure():
    result = build_deployment_truth(**_evidence(
        production_sha=OLD,
        health_sha=OLD,
        readiness_sha=OLD,
        ui_proof_sha=OLD,
    ))
    assert result["state"] == "STALE_DEPLOYMENT"
    assert result["parity"] is False
    assert result["certified"] is False
    assert result["owner"] == "DEPLOYMENT"
    assert result["product_mutation_allowed"] is False
    assert result["patch_product_allowed"] is False
    assert result["next_legal_action"] == "REFRESH_OR_REDEPLOY_PRODUCTION"


def test_internal_production_identity_disagreement_is_identity_conflict():
    result = build_deployment_truth(**_evidence(
        production_sha=MAIN,
        health_sha=OLD,
    ))
    assert result["state"] == "IDENTITY_CONFLICT"
    assert result["certified"] is False
    assert result["owner"] == "DEPLOYMENT"
    assert result["patch_product_allowed"] is False


@pytest.mark.parametrize("field", ["build_id", "deploy_id"])
def test_build_and_deploy_ids_are_required(field):
    values = _evidence()
    values[field] = ""
    result = build_deployment_truth(**values)
    assert result["state"] == "INCOMPLETE"
    assert result["certified"] is False
    assert result["patch_product_allowed"] is False


@pytest.mark.parametrize("field", ["health_ok", "readiness_ok", "ui_proof_ok"])
def test_runtime_and_ui_proof_must_be_green(field):
    values = _evidence()
    values[field] = False
    result = build_deployment_truth(**values)
    assert result["state"] == "PROOF_FAILED"
    assert result["certified"] is False
    assert result["patch_product_allowed"] is False


def test_ui_proof_sha_must_match_public_runtime_identity():
    result = build_deployment_truth(**_evidence(ui_proof_sha=OLD))
    assert result["state"] == "IDENTITY_CONFLICT"
    assert result["certified"] is False


def test_invalid_sha_fails_closed():
    result = build_deployment_truth(**_evidence(github_main_sha="abc"))
    assert result["state"] == "INCOMPLETE"
    assert result["certified"] is False


def test_decision_fingerprint_detects_tampering():
    result = build_deployment_truth(**_evidence())
    tampered = copy.deepcopy(result)
    tampered["state"] = "STALE_DEPLOYMENT"
    with pytest.raises(DeploymentTruthFailure, match="fingerprint mismatch"):
        validate_deployment_truth(tampered)


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_main_sha_parity"] is True
    assert result["stale_deployment_classification"] is True
    assert result["build_deploy_identity_required"] is True
    assert result["health_ready_ui_chain_required"] is True
    assert result["product_patch_blocked_on_deployment_failure"] is True
    assert result["product_runtime_mutation"] is False


def test_engine_runs_directly_as_permanent_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "deployment_truth_control_plane_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1_GREEN" in completed.stdout
