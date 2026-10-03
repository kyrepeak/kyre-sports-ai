from __future__ import annotations

import copy

import pytest

from devsystem.api2_failure_domain_router_v1 import (
    FailureDomainError,
    authorize_domain_mutation,
    classify_api2_failure,
    contract_self_test,
    validate_domain_decision,
)
from devsystem.upstream_blocker_short_circuit_v1 import evaluate_upstream_dependency


def test_real_frozen_registry_failure_is_control_plane_not_product():
    decision = classify_api2_failure({
        "job": "permanent-contract",
        "layer": "control-plane",
        "evidence_signal": "frozen-registry-mismatch",
        "diagnosis": "frozen artifact mismatch without exact thaw grant",
        "confidence": "high",
    })
    assert decision["domain"] == "CONTROL_PLANE"
    assert decision["product_mutation_allowed"] is False
    assert decision["next_legal_action"] == "PATCH_CONTROL_PLANE_OWNER"


def test_step4_upstream_block_routes_to_upstream_owner_and_real_gate_is_state_aware():
    real_gate = evaluate_upstream_dependency("wnba-pra-repair-v1-step3-public")
    assert real_gate["status"] in {"UPSTREAM_BLOCKED", "GREEN"}
    if real_gate["status"] == "GREEN":
        assert real_gate["decision"] == "PROCEED_DOWNSTREAM_PROOF"
        assert real_gate["downstream_proof_allowed"] is True
    else:
        assert real_gate["decision"] == "UPSTREAM_BLOCKED"
        assert real_gate["downstream_proof_allowed"] is False

    blocked_gate = copy.deepcopy(real_gate)
    blocked_gate.update(
        {
            "status": "UPSTREAM_BLOCKED",
            "decision": "UPSTREAM_BLOCKED",
            "downstream_proof_allowed": False,
            "expensive_proof_allowed": False,
            "green_plus_frozen_claimed": False,
            "reason": "GREEN_PLUS_FROZEN_NOT_CLAIMED",
        }
    )
    decision = classify_api2_failure(
        {
            "job": "wnba-step3-public-production",
            "layer": "wnba",
            "evidence_signal": "no-tappable-players",
            "diagnosis": "Page 3 cannot traverse uncertified Page 2",
        },
        upstream_gate=blocked_gate,
    )
    assert decision["domain"] == "UPSTREAM_DEPENDENCY"
    assert decision["upstream_owner"] == "wnba-pra-repair-v1-step2-team-identity"
    assert decision["patch_allowed"] is False
    assert decision["product_mutation_allowed"] is False
    assert decision["next_legal_action"] == "ROUTE_TO_UPSTREAM_OWNER"


def test_product_failure_is_the_only_domain_that_can_mutate_product():
    product = classify_api2_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "test-assertion",
        "diagnosis": "product invariant mismatch",
    })
    assert product["domain"] == "PRODUCT"
    assert product["product_mutation_allowed"] is True
    assert authorize_domain_mutation(product, ["app.py"])["authorized"] is True

    control = classify_api2_failure({
        "job": "workflow-hygiene",
        "layer": "workflow-control",
        "evidence_signal": "workflow-contract",
    })
    with pytest.raises(FailureDomainError, match="cannot mutate PRODUCT"):
        authorize_domain_mutation(control, ["app.py"])


def test_deployment_failure_cannot_mutate_product():
    decision = classify_api2_failure({
        "job": "production-verification",
        "layer": "production",
        "evidence_signal": "deployment-identity",
    })
    assert decision["domain"] == "DEPLOYMENT"
    assert decision["product_mutation_allowed"] is False
    with pytest.raises(FailureDomainError, match="cannot mutate PRODUCT"):
        authorize_domain_mutation(decision, ["app.py"])


def test_browser_selector_race_is_proof_verifier():
    decision = classify_api2_failure({
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
    })
    assert decision["domain"] == "PROOF_VERIFIER"
    assert decision["product_mutation_allowed"] is False
    assert authorize_domain_mutation(
        decision, ["tests/test_devsystem_browser_qa_v1.py"]
    )["authorized"] is True


def test_stale_evidence_never_authorizes_patch():
    decision = classify_api2_failure(
        {
            "job": "wnba-critical",
            "layer": "wnba",
            "evidence_signal": "test-assertion",
        },
        evidence_freshness="STALE_HEAD",
    )
    assert decision["domain"] == "CONTROL_PLANE"
    assert decision["patch_allowed"] is False
    assert decision["next_legal_action"] == "REFRESH_EVIDENCE"


def test_external_failure_is_observe_only():
    decision = classify_api2_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "network-upstream",
    })
    assert decision["domain"] == "EXTERNAL"
    assert decision["patch_allowed"] is False
    assert decision["next_legal_action"] == "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"


def test_decision_fingerprint_detects_tampering():
    decision = classify_api2_failure({
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
    })
    tampered = copy.deepcopy(decision)
    tampered["domain"] = "PRODUCT"
    with pytest.raises(FailureDomainError, match="fingerprint mismatch"):
        validate_domain_decision(tampered)


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["domains"] == [
        "CONTROL_PLANE",
        "DEPLOYMENT",
        "EXTERNAL",
        "PRODUCT",
        "PROOF_VERIFIER",
        "UPSTREAM_DEPENDENCY",
    ]
    assert result["classify_before_patch"] is True
    assert result["single_failure_domain"] is True
    assert result["control_plane_product_mutation_blocked"] is True
    assert result["upstream_downstream_mutation_blocked"] is True
    assert result["stale_patch_blocked"] is True
