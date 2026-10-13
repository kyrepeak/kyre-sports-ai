import copy
from pathlib import Path

import pytest

from devsystem.universal_sports_source_receipt_v1 import (
    FREEZE_TOKEN,
    STEP,
    WORKSTREAM,
    build_source_receipt,
    load_source_receipt_contract,
    validate_source_receipt,
    validate_source_receipt_contract,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-source-receipt-v1.json"


def _contract():
    return load_source_receipt_contract(CONTRACT_PATH)


def _route():
    return {
        "status": "ROUTE_READY",
        "sport": "nfl",
        "field": "schedule",
        "semantic_metric_id": "SCHEDULE",
        "route_id": "ROUTE-STEP6-FIXTURE",
        "primary_provider_id": "nfl_official",
        "fallback_provider_ids": ["espn", "cbs_sports"],
        "eligible_provider_ids": ["nfl_official", "espn", "cbs_sports"],
        "active_provider_ids": [],
        "routing_unit": "DATA_FIELD",
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
    }


def _decision(status="ACCEPTED_FALLBACK_QUORUM"):
    return {
        "workstream": "universal-sports-source-finalization-v1",
        "step": "4/8",
        "status": status,
        "sport": "nfl",
        "field": "schedule",
        "semantic_metric_id": "SCHEDULE",
        "route_id": "ROUTE-STEP6-FIXTURE",
        "trust_policy_id": "USTQ-STEP6-FIXTURE",
        "active_provider_ids": ["nfl_official", "espn"],
        "selected_provider_ids": ["espn"],
        "rejected_attempts": [{"provider_id": "nfl_official", "reason": "STALE_DATA"}],
        "next_provider_ids": [],
        "accepted_value": {"date": "2026-10-18", "games": 14},
        "value_fingerprint": "VALUE-STEP6-FIXTURE",
        "minimum_quorum_satisfied": True,
        "early_stop": True,
        "expansion_reason": "",
        "routing_unit": "DATA_FIELD",
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "decision_id": "QUORUM-STEP6-FIXTURE",
    }


def _identity():
    return {
        "version": "UNIVERSAL_SPORTS_IDENTITY_HEALTH_V1",
        "workstream": "universal-sports-source-finalization-v1",
        "step": "5/8",
        "status": "IDENTITY_RESOLVED",
        "entity_type": "team",
        "canonical_entity_id": "nfl:team:was",
        "canonical_key": "WAS",
        "canonical_name": "Washington Commanders",
        "sport": "nfl",
        "provider_id": "espn",
        "provider_entity_id": "WSH",
        "aliases_used": [{"provider_id": "espn", "value": "WSH"}],
        "snapshot_id": "USIHS-STEP6-FIXTURE",
        "active_provider_ids": [],
        "network_calls": False,
        "fabrication": False,
        "identity_resolution_id": "USIHR-STEP6-FIXTURE",
    }


def _health_context():
    return {
        "status": "IDENTITY_HEALTH_READY",
        "field": "schedule",
        "provider_field_health": [
            {
                "provider_id": "nfl_official",
                "field": "schedule",
                "health_state": "DEGRADED",
                "age_seconds": 90,
                "quality_score": 0.90,
                "validation_result": "VALID",
                "reason": "freshness degraded",
                "fallback_rank": 1,
            },
            {
                "provider_id": "espn",
                "field": "schedule",
                "health_state": "HEALTHY",
                "age_seconds": 10,
                "quality_score": 0.98,
                "validation_result": "VALID",
                "reason": "healthy",
                "fallback_rank": 2,
            },
            {
                "provider_id": "cbs_sports",
                "field": "schedule",
                "health_state": "HEALTHY",
                "age_seconds": 12,
                "quality_score": 0.95,
                "validation_result": "VALID",
                "reason": "healthy",
                "fallback_rank": 3,
            },
        ],
        "active_provider_ids": [],
        "network_calls": False,
        "fabrication": False,
    }


def _observations():
    return [
        {
            "provider_id": "nfl_official",
            "semantic_metric_id": "SCHEDULE",
            "age_seconds": 90,
            "quality_score": 0.90,
            "normalized_value": {"date": "2026-10-18", "games": 13},
        },
        {
            "provider_id": "espn",
            "semantic_metric_id": "SCHEDULE",
            "age_seconds": 10,
            "quality_score": 0.98,
            "normalized_value": {"date": "2026-10-18", "games": 14},
        },
    ]


def _receipt(**overrides):
    kwargs = {
        "page": "nfl-overview",
        "source_step": "page1-schedule",
        "route": _route(),
        "quorum_decision": _decision(),
        "identity_resolution": _identity(),
        "identity_health_context": _health_context(),
        "observations": _observations(),
        "canonical_game_id": "nfl:game:ind-at-was-2026-10-18",
    }
    kwargs.update(overrides)
    return build_source_receipt(_contract(), **kwargs)


def test_valid_contract_certifies_step6():
    result = validate_source_receipt_contract(_contract())
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "6/8"
    assert result["routing_unit"] == "DATA_FIELD"
    assert result["deterministic_receipt_digest"] is True
    assert result["network_calls"] is False
    assert result["github_actions_fallback"] == 0
    assert result["freeze_token"] == FREEZE_TOKEN


def test_receipt_is_deterministic_and_provenance_complete():
    first = _receipt()
    second = _receipt()
    assert first == second
    assert first["receipt_id"].startswith("USR-")
    assert first["receipt_digest"].startswith("sha256:")
    assert first["providers_attempted"] == ["nfl_official", "espn"]
    assert first["selected_provider_ids"] == ["espn"]
    assert first["fallback_rank"] == 2
    assert first["provider_fallback_ranks"] == {"espn": 2}
    assert first["normalized_value_fingerprint"] == "VALUE-STEP6-FIXTURE"
    assert first["agreement_result"] == "ACCEPTED_FALLBACK_QUORUM"
    assert first["quorum_policy_id"] == "USTQ-STEP6-FIXTURE"
    assert first["fabrication"] is False
    assert first["network_calls"] is False


def test_receipt_preserves_rejected_attempts_aliases_and_canonical_ids():
    receipt = _receipt()
    assert receipt["rejected_attempts"] == [{"provider_id": "nfl_official", "reason": "STALE_DATA"}]
    assert receipt["aliases_used"] == [{"provider_id": "espn", "value": "WSH"}]
    assert receipt["canonical_entity_id"] == "nfl:team:was"
    assert receipt["canonical_game_id"] == "nfl:game:ind-at-was-2026-10-18"


def test_receipt_captures_freshness_and_field_health_for_every_attempt():
    receipt = _receipt()
    assert [row["provider_id"] for row in receipt["freshness_observation"]] == ["nfl_official", "espn"]
    assert receipt["freshness_observation"][1]["age_seconds"] == 10
    assert [row["provider_id"] for row in receipt["provider_health_at_decision"]] == ["nfl_official", "espn"]
    assert receipt["provider_health_at_decision"][1]["health_state"] == "HEALTHY"


def test_nonaccepted_decision_cannot_emit_accepted_source_receipt():
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_ACCEPTED_DECISION_REQUIRED"):
        _receipt(quorum_decision=_decision("DISAGREEMENT_REQUIRES_EXPANSION"))


def test_selected_provider_must_have_been_actually_attempted():
    decision = _decision()
    decision["selected_provider_ids"] = ["cbs_sports"]
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_SELECTED_PROVIDERS_INVALID"):
        _receipt(quorum_decision=decision)


def test_missing_attempt_observation_fails_closed():
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_ATTEMPT_OBSERVATION_MISSING"):
        _receipt(observations=_observations()[1:])


def test_missing_attempt_health_fails_closed():
    context = _health_context()
    context["provider_field_health"] = context["provider_field_health"][1:]
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_PROVIDER_HEALTH_MISSING"):
        _receipt(identity_health_context=context)


def test_receipt_digest_detects_tampering():
    receipt = _receipt()
    broken = copy.deepcopy(receipt)
    broken["selected_provider_ids"] = ["nfl_official"]
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_DIGEST_MISMATCH"):
        validate_source_receipt(broken)


def test_contract_fingerprint_detects_tampering():
    broken = copy.deepcopy(_contract())
    broken["fabrication"] = True
    with pytest.raises(ValueError, match="SOURCE_RECEIPT_CONTRACT_FINGERPRINT_MISMATCH"):
        validate_source_receipt_contract(broken)
