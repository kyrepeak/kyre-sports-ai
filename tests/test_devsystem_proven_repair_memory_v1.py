from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.proven_repair_memory_v1 import (
    RepairMemoryFailure,
    contract_self_test,
    load_catalog,
    lookup_exact,
    lookup_for_failure,
    validate_catalog,
)

CATALOG = Path("devsystem/proven_repair_memory_catalog_v1.json")


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_hit_reuses_pattern"] is True
    assert result["hit_never_grants_mutation"] is True
    assert result["unproven_repair_rejected"] is True


def test_repository_catalog_is_valid_and_seeded_with_real_proven_repairs():
    catalog = load_catalog(CATALOG)
    assert catalog["revision"] == 1
    assert len(catalog["records"]) >= 2
    checkpoints = {record["proof"]["checkpoint_id"] for record in catalog["records"]}
    assert {"MONSTER_V6_STEP1", "MONSTER_V6_STEP2"} <= checkpoints


def test_exact_action_ledger_failure_hits_proven_repair():
    catalog = load_catalog(CATALOG)
    result = lookup_for_failure(
        catalog,
        failure_code="ACTION_LEDGER_V2_INVALID",
        failure={
            "job": "permanent-contract",
            "layer": "control-plane",
            "evidence_signal": "contract-invalid",
            "diagnosis": "Action Ledger V2 mismatch",
        },
    )
    assert result["status"] == "HIT"
    assert result["fresh_ownership"]["owner"] == "VERIFIER"
    assert result["repair"]["proof"]["conclusion"] == "SUCCESS"
    assert result["mutation_authority"] is False


def test_exact_package_bootstrap_failure_hits_proven_repair():
    catalog = load_catalog(CATALOG)
    result = lookup_for_failure(
        catalog,
        failure_code="PYTHON_PACKAGE_BOOTSTRAP_MISSING",
        failure={
            "job": "preflight",
            "layer": "workflow-control",
            "evidence_signal": "module-import",
            "diagnosis": "No module named devsystem",
        },
    )
    assert result["status"] == "HIT"
    assert result["fresh_ownership"]["owner"] == "CI"
    assert result["repair"]["proof"]["workflow_run_id"] == 36929552958


def test_nonexact_failure_does_not_get_fuzzy_patch():
    catalog = load_catalog(CATALOG)
    result = lookup_exact(
        catalog,
        {
            "owner": "CI",
            "failure_code": "PYTHON_PACKAGE_BOOTSTRAP_MISSING",
            "surface": "workflow-control",
            "evidence_signal": "different-signal",
        },
    )
    assert result["status"] == "MISS"
    assert result["repair"] is None
    assert result["next_legal_action"] == "DIAGNOSE_FRESH_FAILURE"


def test_stale_failure_never_reuses_repair_for_mutation():
    catalog = load_catalog(CATALOG)
    result = lookup_for_failure(
        catalog,
        failure_code="PYTHON_PACKAGE_BOOTSTRAP_MISSING",
        failure={
            "job": "preflight",
            "layer": "workflow-control",
            "evidence_signal": "module-import",
        },
        evidence_freshness="STALE_HEAD",
    )
    assert result["status"] == "BLOCKED"
    assert result["repair"] is None
    assert result["next_legal_action"] == "REFRESH_EVIDENCE"


def test_catalog_tamper_fails_closed():
    catalog = load_catalog(CATALOG)
    tampered = deepcopy(catalog)
    tampered["records"][0]["root_cause"] += " tampered"
    with pytest.raises(RepairMemoryFailure):
        validate_catalog(tampered)


def test_duplicate_signature_is_forbidden():
    catalog = load_catalog(CATALOG)
    raw = deepcopy(catalog)
    raw["records"].append(deepcopy(raw["records"][0]))
    with pytest.raises(RepairMemoryFailure):
        validate_catalog(raw)
