import copy
import json
from pathlib import Path

import pytest

from devsystem.universal_sports_full_integration_lineage_r1 import (
    FREEZE_TOKEN,
    HISTORICAL_STEP7_FREEZE_TOKEN,
    HISTORICAL_STEP8_FREEZE_TOKEN,
    STEP7_R1_FREEZE_TOKEN,
    certify_step8_lineage_r1,
    load_step8_lineage_contract,
    validate_step8_lineage_contract,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "devsystem" / "contracts"


def _contract():
    return load_step8_lineage_contract(
        CONTRACTS / "universal-sports-full-integration-lineage-r1.json"
    )


def _historical_step8_contract():
    return json.loads(
        (CONTRACTS / "universal-sports-full-integration-v1.json").read_text(encoding="utf-8")
    )


def _evidence():
    return {
        "step7_r1_freeze_token": STEP7_R1_FREEZE_TOKEN,
        "step7_r1_candidate_sha": "fbc8d068b2892536c42c5a9840b20ffcfbf7924b",
        "step7_r1_proof_digest": "sha256:6936d9e5fde87291ab09bfc9274c9da2290eb2273d6783be326b0b003d6d3779",
        "step7_r1_record_blob_sha": "82d2b8169df66fbaae9b5f2b05018c53b755009d",
        "step7_r1_bridge_blob_sha": "217feeb49aea0f20f9f3af33f23e6698a46607da",
        "step7_r1_manifest_revision": 13,
        "step7_r1_manifest_state_hash": "c69782783af1acd88c4c1dc949aa2fcc00754f59c497ba28e494748de35d40d7",
        "step7_r1_merged_main_sha": "497a81adf227ef0e1fa4e86a9e4f9260b999aef9",
        "step7_r1_ledger_head_sha": "a597c0ed19d55a4102b46b73e83fd9d77b4e21c1",
        "step7_r1_proof_id": "universal-sports-source-finalization-v1-step7-freeze-integrity-r1-fbc8d068b2892536-a7b8dd7666f27a45",
    }


def test_step8_r1_contract_binds_historical_and_repaired_lineage():
    verified = validate_step8_lineage_contract(_contract())
    assert verified["status"] == "GREEN"
    assert verified["historical_step7_freeze_token"] == HISTORICAL_STEP7_FREEZE_TOKEN
    assert verified["historical_step8_freeze_token"] == HISTORICAL_STEP8_FREEZE_TOKEN
    assert verified["step7_r1_freeze_token"] == STEP7_R1_FREEZE_TOKEN
    assert verified["freeze_token"] == FREEZE_TOKEN
    assert verified["historical_step8_rewrite"] is False
    assert verified["historical_step7_rewrite"] is False
    assert verified["product_runtime_mutation"] is False
    assert verified["sports_model_mutation"] is False
    assert verified["render_dependency"] is False
    assert verified["github_actions_fallback"] == 0


def test_step8_r1_certifies_existing_step8_against_exact_step7_r1_evidence():
    result = certify_step8_lineage_r1(
        _contract(), _historical_step8_contract(), _evidence()
    )
    assert result["status"] == "GREEN"
    assert result["certified"] is True
    assert result["terminal_status"] == "STEP8_LINEAGE_R1_CERTIFIED"
    assert result["historical_step8_freeze_token"] == HISTORICAL_STEP8_FREEZE_TOKEN
    assert result["step7_r1_freeze_token"] == STEP7_R1_FREEZE_TOKEN
    assert result["freeze_token"] == FREEZE_TOKEN
    assert result["certification_id"].startswith("USFICR1-")


def test_step8_r1_rejects_stale_or_wrong_step7_repair_token():
    evidence = _evidence()
    evidence["step7_r1_freeze_token"] = HISTORICAL_STEP7_FREEZE_TOKEN
    with pytest.raises(ValueError, match="STEP8_LINEAGE_R1_STEP7_REPAIR_TOKEN_MISMATCH"):
        certify_step8_lineage_r1(_contract(), _historical_step8_contract(), evidence)


def test_step8_r1_rejects_exact_evidence_drift():
    evidence = _evidence()
    evidence["step7_r1_manifest_state_hash"] = "0" * 64
    with pytest.raises(ValueError, match="STEP8_LINEAGE_R1_EVIDENCE_DRIFT"):
        certify_step8_lineage_r1(_contract(), _historical_step8_contract(), evidence)


def test_step8_r1_rejects_historical_step8_contract_tamper():
    historical = _historical_step8_contract()
    historical["prior_freeze_tokens"]["step7"] = "WRONG"
    with pytest.raises(ValueError):
        certify_step8_lineage_r1(_contract(), historical, _evidence())


def test_step8_r1_contract_tamper_invalidates_fingerprint():
    contract = copy.deepcopy(_contract())
    contract["step7_r1_manifest_revision"] = 999
    with pytest.raises(ValueError, match="STEP8_LINEAGE_R1_CONTRACT_FINGERPRINT_MISMATCH"):
        validate_step8_lineage_contract(contract)
