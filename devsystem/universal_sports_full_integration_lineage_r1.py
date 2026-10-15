from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from devsystem.universal_sports_full_integration_certifier_v1 import (
    FREEZE_TOKEN as HISTORICAL_STEP8_FREEZE_TOKEN,
    validate_full_integration_contract,
)

VERSION = "UNIVERSAL_SPORTS_FULL_INTEGRATION_LINEAGE_R1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "8/8"
HISTORICAL_STEP7_FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_FROZEN"
STEP7_R1_FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_R1_FROZEN"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP8_FULL_INTEGRATION_CERTIFICATION_LINEAGE_R1_FROZEN"

STEP7_R1_CANDIDATE_SHA = "fbc8d068b2892536c42c5a9840b20ffcfbf7924b"
STEP7_R1_MERGED_MAIN_SHA = "497a81adf227ef0e1fa4e86a9e4f9260b999aef9"
STEP7_R1_PROOF_DIGEST = "sha256:6936d9e5fde87291ab09bfc9274c9da2290eb2273d6783be326b0b003d6d3779"
STEP7_R1_RECORD_BLOB_SHA = "82d2b8169df66fbaae9b5f2b05018c53b755009d"
STEP7_R1_BRIDGE_BLOB_SHA = "217feeb49aea0f20f9f3af33f23e6698a46607da"
STEP7_R1_MANIFEST_REVISION = 13
STEP7_R1_MANIFEST_STATE_HASH = "c69782783af1acd88c4c1dc949aa2fcc00754f59c497ba28e494748de35d40d7"
STEP7_R1_LEDGER_HEAD_SHA = "a597c0ed19d55a4102b46b73e83fd9d77b4e21c1"
STEP7_R1_PROOF_ID = "universal-sports-source-finalization-v1-step7-freeze-integrity-r1-fbc8d068b2892536-a7b8dd7666f27a45"

_REQUIRED = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "historical_step7_freeze_token": HISTORICAL_STEP7_FREEZE_TOKEN,
    "historical_step8_freeze_token": HISTORICAL_STEP8_FREEZE_TOKEN,
    "step7_r1_freeze_token": STEP7_R1_FREEZE_TOKEN,
    "step7_r1_candidate_sha": STEP7_R1_CANDIDATE_SHA,
    "step7_r1_merged_main_sha": STEP7_R1_MERGED_MAIN_SHA,
    "step7_r1_proof_digest": STEP7_R1_PROOF_DIGEST,
    "step7_r1_record_blob_sha": STEP7_R1_RECORD_BLOB_SHA,
    "step7_r1_bridge_blob_sha": STEP7_R1_BRIDGE_BLOB_SHA,
    "step7_r1_manifest_revision": STEP7_R1_MANIFEST_REVISION,
    "step7_r1_manifest_state_hash": STEP7_R1_MANIFEST_STATE_HASH,
    "step7_r1_ledger_head_sha": STEP7_R1_LEDGER_HEAD_SHA,
    "step7_r1_proof_id": STEP7_R1_PROOF_ID,
    "historical_step8_rewrite": False,
    "historical_step7_rewrite": False,
    "legacy_registry_mutation": False,
    "product_runtime_mutation": False,
    "sports_model_mutation": False,
    "render_dependency": False,
    "github_actions_fallback": 0,
    "freeze_token": FREEZE_TOKEN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Mapping[str, Any], prefix: str) -> str:
    digest = hashlib.sha256(_canonical(dict(value)).encode("utf-8")).hexdigest()[:24].upper()
    return prefix + digest


def load_step8_lineage_contract(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("STEP8_LINEAGE_R1_CONTRACT_NOT_OBJECT")
    return value


def validate_step8_lineage_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise ValueError("STEP8_LINEAGE_R1_CONTRACT_NOT_OBJECT")
    raw = deepcopy(dict(contract))
    supplied_id = str(raw.pop("contract_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USFI8R1-")
    if supplied_id != expected_id:
        raise ValueError("STEP8_LINEAGE_R1_CONTRACT_FINGERPRINT_MISMATCH")
    for key, expected in _REQUIRED.items():
        if raw.get(key) != expected:
            raise ValueError(f"STEP8_LINEAGE_R1_CONTRACT_DRIFT:{key}")
    verified = deepcopy(raw)
    verified["contract_id"] = supplied_id
    verified["status"] = "GREEN"
    return verified


def certify_step8_lineage_r1(
    lineage_contract: Mapping[str, Any],
    historical_step8_contract: Mapping[str, Any],
    step7_r1_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    contract = validate_step8_lineage_contract(lineage_contract)
    historical = validate_full_integration_contract(historical_step8_contract)
    if historical.get("freeze_token") != HISTORICAL_STEP8_FREEZE_TOKEN:
        raise ValueError("STEP8_LINEAGE_R1_HISTORICAL_STEP8_TOKEN_DRIFT")
    if (historical.get("prior_freeze_tokens") or {}).get("step7") != HISTORICAL_STEP7_FREEZE_TOKEN:
        raise ValueError("STEP8_LINEAGE_R1_HISTORICAL_STEP7_LINEAGE_DRIFT")

    if str(step7_r1_evidence.get("step7_r1_freeze_token") or "") != STEP7_R1_FREEZE_TOKEN:
        raise ValueError("STEP8_LINEAGE_R1_STEP7_REPAIR_TOKEN_MISMATCH")

    evidence_fields = {
        "step7_r1_candidate_sha": STEP7_R1_CANDIDATE_SHA,
        "step7_r1_merged_main_sha": STEP7_R1_MERGED_MAIN_SHA,
        "step7_r1_proof_digest": STEP7_R1_PROOF_DIGEST,
        "step7_r1_record_blob_sha": STEP7_R1_RECORD_BLOB_SHA,
        "step7_r1_bridge_blob_sha": STEP7_R1_BRIDGE_BLOB_SHA,
        "step7_r1_manifest_revision": STEP7_R1_MANIFEST_REVISION,
        "step7_r1_manifest_state_hash": STEP7_R1_MANIFEST_STATE_HASH,
        "step7_r1_ledger_head_sha": STEP7_R1_LEDGER_HEAD_SHA,
        "step7_r1_proof_id": STEP7_R1_PROOF_ID,
    }
    for key, expected in evidence_fields.items():
        if step7_r1_evidence.get(key) != expected:
            raise ValueError(f"STEP8_LINEAGE_R1_EVIDENCE_DRIFT:{key}")
        if contract.get(key) != expected:
            raise ValueError(f"STEP8_LINEAGE_R1_CONTRACT_EVIDENCE_DRIFT:{key}")

    result = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "status": "GREEN",
        "certified": True,
        "terminal_status": "STEP8_LINEAGE_R1_CERTIFIED",
        "historical_step7_freeze_token": HISTORICAL_STEP7_FREEZE_TOKEN,
        "historical_step8_freeze_token": HISTORICAL_STEP8_FREEZE_TOKEN,
        "step7_r1_freeze_token": STEP7_R1_FREEZE_TOKEN,
        **evidence_fields,
        "historical_step8_contract_id": historical["contract_id"],
        "historical_step8_rewrite": False,
        "historical_step7_rewrite": False,
        "legacy_registry_mutation": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "freeze_token": FREEZE_TOKEN,
    }
    result["certification_id"] = _fingerprint(result, "USFICR1-")
    return result


__all__ = [
    "FREEZE_TOKEN",
    "HISTORICAL_STEP7_FREEZE_TOKEN",
    "HISTORICAL_STEP8_FREEZE_TOKEN",
    "STEP7_R1_FREEZE_TOKEN",
    "certify_step8_lineage_r1",
    "load_step8_lineage_contract",
    "validate_step8_lineage_contract",
]
