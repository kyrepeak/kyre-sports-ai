from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.api2_exact_deployment_sha_gate_v1 import (
    ExactDeploymentGateFailure,
    build_exact_deployment_gate,
    contract_self_test,
    require_exact_deployment_gate,
)


CURRENT = "a" * 40
OLD = "b" * 40


def _evidence(**overrides):
    value = {
        "expected_sha": CURRENT,
        "production_sha": CURRENT,
        "build_id": "build-123",
        "deploy_id": "deploy-123",
        "health_sha": CURRENT,
        "readiness_sha": CURRENT,
        "ui_proof_sha": CURRENT,
        "health_ok": True,
        "readiness_ok": True,
        "ui_proof_ok": True,
    }
    value.update(overrides)
    return value


def test_exact_deployment_parity_opens_public_product_proof_gate():
    result = build_exact_deployment_gate(**_evidence())
    assert result["state"] == "DEPLOYMENT_PARITY"
    assert result["gate_open"] is True
    assert result["public_product_proof_allowed"] is True
    assert result["next_legal_action"] == "PROCEED_PUBLIC_PRODUCT_PROOF"


def test_stale_production_is_deployment_wait_not_product_patch():
    result = build_exact_deployment_gate(**_evidence(
        production_sha=OLD,
        health_sha=OLD,
        readiness_sha=OLD,
        ui_proof_sha=OLD,
    ))
    assert result["state"] == "STALE_DEPLOYMENT"
    assert result["gate_open"] is False
    assert result["public_product_proof_allowed"] is False
    assert result["product_patch_allowed"] is False
    assert result["product_mutation_allowed"] is False
    assert result["owner"] == "DEPLOYMENT"
    assert result["next_legal_action"] == "WAIT_FOR_EXACT_DEPLOYMENT"


def test_identity_conflict_blocks_expensive_product_proof():
    result = build_exact_deployment_gate(**_evidence(health_sha=OLD))
    assert result["state"] == "IDENTITY_CONFLICT"
    assert result["gate_open"] is False
    assert result["next_legal_action"] == "RECONCILE_DEPLOYMENT_IDENTITY"


def test_missing_identity_fails_closed_before_product_proof():
    result = build_exact_deployment_gate(**_evidence(
        production_sha="",
        build_id="",
        deploy_id="",
        health_sha="",
        readiness_sha="",
        ui_proof_sha="",
    ))
    assert result["state"] == "INCOMPLETE"
    assert result["gate_open"] is False
    assert result["public_product_proof_allowed"] is False


def test_runtime_or_ui_proof_failure_does_not_authorize_product_patch():
    result = build_exact_deployment_gate(**_evidence(ui_proof_ok=False))
    assert result["state"] == "PROOF_FAILED"
    assert result["gate_open"] is False
    assert result["product_patch_allowed"] is False
    assert result["next_legal_action"] == "RESTORE_DEPLOYMENT_PROOF"


def test_require_gate_raises_on_stale_deployment():
    with pytest.raises(ExactDeploymentGateFailure, match="STALE_DEPLOYMENT"):
        require_exact_deployment_gate(**_evidence(
            production_sha=OLD,
            health_sha=OLD,
            readiness_sha=OLD,
            ui_proof_sha=OLD,
        ))


def test_contract_self_test_is_green_and_read_only():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_parity_opens_gate"] is True
    assert result["stale_deployment_blocks_product_proof"] is True
    assert result["missing_identity_fails_closed"] is True
    assert result["network_calls"] is False
    assert result["product_runtime_mutation"] is False
    assert result["frozen_parent_version"] == "MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1"


def test_gate_runs_directly_as_dependency_light_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "api2_exact_deployment_sha_gate_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "API2_PROOF_ARCHITECTURE_V1_STEP1_EXACT_DEPLOYMENT_SHA_GATE_GREEN" in completed.stdout
