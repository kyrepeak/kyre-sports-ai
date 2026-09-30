from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.failure_ownership_engine_v1 import (
    OwnershipFailure,
    authorize_mutation,
    classify_failure,
    contract_self_test,
    validate_decision,
)


def _failure(**overrides):
    value = {
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "test-assertion",
        "diagnosis": "protected product contract mismatch",
        "confidence": "high",
    }
    value.update(overrides)
    return value


def test_product_failure_is_owned_by_product():
    decision = classify_failure(_failure())
    assert decision["owner"] == "PRODUCT"
    assert decision["failure_class"] == "PRODUCT"
    assert decision["patch_allowed"] is True
    assert decision["product_mutation_allowed"] is True
    assert decision["next_legal_action"] == "PATCH_OWNER_SCOPE"


def test_browser_selector_failure_is_owned_by_verifier():
    decision = classify_failure(_failure(
        job="browser-qa",
        layer="ui-browser",
        evidence_signal="browser-selector-race",
        diagnosis="locator readiness mismatch",
    ))
    assert decision["owner"] == "VERIFIER"
    assert decision["product_mutation_allowed"] is False


def test_ci_dependency_failure_is_owned_by_ci():
    decision = classify_failure(_failure(
        job="permanent-contract",
        layer="workflow-control",
        evidence_signal="cache-dependency",
        diagnosis="dependency provisioning failure",
    ))
    assert decision["owner"] == "CI"
    assert decision["product_mutation_allowed"] is False


def test_production_failure_is_owned_by_deployment():
    decision = classify_failure(_failure(
        job="production-verification",
        layer="production",
        evidence_signal="deployment-identity",
        diagnosis="deployed commit mismatch",
    ))
    assert decision["owner"] == "DEPLOYMENT"
    assert decision["product_mutation_allowed"] is False


def test_network_upstream_failure_is_owned_by_external():
    decision = classify_failure(_failure(
        job="wnba-critical",
        layer="wnba",
        evidence_signal="network-upstream",
        diagnosis="503 service unavailable",
    ))
    assert decision["owner"] == "EXTERNAL"
    assert decision["patch_allowed"] is False
    assert decision["next_legal_action"] == "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"


def test_stale_evidence_has_absolute_precedence():
    decision = classify_failure(_failure(), evidence_freshness="STALE_HEAD")
    assert decision["owner"] == "STALE"
    assert decision["patch_allowed"] is False
    assert decision["next_legal_action"] == "REFRESH_EVIDENCE"


def test_ambiguous_failure_fails_safe_to_verifier_not_product():
    decision = classify_failure(_failure(
        job="mystery",
        layer="unknown",
        evidence_signal="unclassified-evidence",
        diagnosis="insufficient evidence",
        confidence="low",
    ))
    assert decision["owner"] == "VERIFIER"
    assert decision["product_mutation_allowed"] is False
    assert decision["classification_basis"] == "INSUFFICIENT_EVIDENCE_FAIL_SAFE"


def test_verifier_owner_cannot_modify_product_code():
    decision = classify_failure(_failure(
        job="browser-qa",
        layer="ui-browser",
        evidence_signal="browser-selector-race",
    ))
    with pytest.raises(OwnershipFailure, match="owner VERIFIER cannot mutate PRODUCT"):
        authorize_mutation(decision, ["app.py"])


def test_verifier_owner_can_modify_verifier_scope_only():
    decision = classify_failure(_failure(
        job="browser-qa",
        layer="ui-browser",
        evidence_signal="browser-selector-race",
    ))
    result = authorize_mutation(
        decision,
        ["tests/test_devsystem_browser_qa_v1.py", "devsystem/browser_qa_v1.py"],
    )
    assert result["authorized"] is True
    assert result["owner"] == "VERIFIER"
    assert result["path_classes"] == ["VERIFIER", "VERIFIER"]


def test_external_and_stale_owners_cannot_patch_anything():
    external = classify_failure(_failure(evidence_signal="network-upstream"))
    with pytest.raises(OwnershipFailure, match="does not permit repository mutation"):
        authorize_mutation(external, ["tests/test_example.py"])

    stale = classify_failure(_failure(), evidence_freshness="STALE_MAIN")
    with pytest.raises(OwnershipFailure, match="does not permit repository mutation"):
        authorize_mutation(stale, ["devsystem/production_targets_v1.json"])


def test_decision_fingerprint_detects_tampering():
    decision = classify_failure(_failure())
    tampered = copy.deepcopy(decision)
    tampered["owner"] = "VERIFIER"
    with pytest.raises(OwnershipFailure, match="fingerprint mismatch"):
        validate_decision(tampered)


def test_step4_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["owners"] == ["CI", "DEPLOYMENT", "EXTERNAL", "PRODUCT", "STALE", "VERIFIER"]
    assert result["classify_before_patch"] is True
    assert result["owner_scope_enforcement"] is True
    assert result["verifier_product_mutation_blocked"] is True
    assert result["stale_patch_blocked"] is True
    assert result["external_patch_blocked"] is True
    assert result["product_runtime_mutation"] is False


def test_step4_engine_runs_directly_as_permanent_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "failure_ownership_engine_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_FAILURE_OWNERSHIP_ENGINE_V1_GREEN" in completed.stdout
