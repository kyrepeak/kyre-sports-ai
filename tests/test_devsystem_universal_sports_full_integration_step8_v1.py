import copy
import json
from pathlib import Path

import pytest

from devsystem.universal_sports_full_integration_certifier_v1 import (
    FREEZE_TOKEN,
    STEP,
    WORKSTREAM,
    certify_full_integration,
    load_full_integration_contract,
    validate_full_integration_contract,
)
from devsystem.universal_sports_identity_health_v1 import seal_identity_health_snapshot

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "devsystem" / "contracts"


def _json(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _inputs():
    return {
        "integration_contract": load_full_integration_contract(CONTRACTS / "universal-sports-full-integration-v1.json"),
        "registry": _json("universal-sports-provider-registry-v1.json"),
        "router_policy": _json("universal-sports-field-router-v1.json"),
        "trust_policy": _json("universal-sports-trust-quorum-v1.json"),
        "identity_health_contract": _json("universal-sports-identity-health-v1.json"),
        "source_receipt_contract": _json("universal-sports-source-receipt-v1.json"),
    }


def _snapshot():
    return seal_identity_health_snapshot(
        {
            "version": "UNIVERSAL_SPORTS_IDENTITY_HEALTH_SNAPSHOT_V1",
            "workstream": "universal-sports-source-finalization-v1",
            "revision": 1,
            "routing_unit": "DATA_FIELD",
            "network_calls": False,
            "fabrication": False,
            "mutation_authority": False,
            "entities": [
                {
                    "canonical_id": "nba:team:phx",
                    "entity_type": "team",
                    "sport": "nba",
                    "canonical_key": "PHX",
                    "canonical_name": "Phoenix Suns",
                    "provider_ids": {
                        "nba_official": "1610612756",
                        "official_team_sites": "suns",
                        "cbs_sports": "PHO",
                        "espn": "PHX",
                    },
                    "aliases": [
                        {"provider_id": "*", "value": "Phoenix Suns"},
                        {"provider_id": "cbs_sports", "value": "PHO"},
                    ],
                }
            ],
            "provider_health": [
                {
                    "provider_id": "nba_official",
                    "field": "injuries",
                    "health_state": "UNHEALTHY",
                    "age_seconds": 20,
                    "quality_score": 0.99,
                    "validation_result": "VALID",
                    "reason": "field endpoint unhealthy",
                },
                {
                    "provider_id": "official_team_sites",
                    "field": "injuries",
                    "health_state": "HEALTHY",
                    "age_seconds": 30,
                    "quality_score": 0.98,
                    "validation_result": "VALID",
                    "reason": "fresh official team report",
                },
                {
                    "provider_id": "cbs_sports",
                    "field": "injuries",
                    "health_state": "HEALTHY",
                    "age_seconds": 45,
                    "quality_score": 0.95,
                    "validation_result": "VALID",
                    "reason": "fresh corroborating report",
                },
                {
                    "provider_id": "espn",
                    "field": "injuries",
                    "health_state": "HEALTHY",
                    "age_seconds": 60,
                    "quality_score": 0.94,
                    "validation_result": "VALID",
                    "reason": "healthy fallback",
                },
            ],
        }
    )


def _scenario():
    injury_value = {"player": "Example Player", "status": "OUT"}
    return {
        "sport": "nba",
        "field": "injuries",
        "page": "nba-integration-certification",
        "source_step": "step8-full-integration",
        "entity_type": "team",
        "identity_value": "PHO",
        "identity_provider_id": "cbs_sports",
        "canonical_game_id": "nba:game:step8-certification",
        "observations": [
            {
                "provider_id": "nba_official",
                "semantic_metric_id": "INJURIES",
                "age_seconds": 10,
                "quality_score": 0.99,
                "normalized_value": injury_value,
            },
            {
                "provider_id": "official_team_sites",
                "semantic_metric_id": "INJURIES",
                "age_seconds": 20,
                "quality_score": 0.98,
                "normalized_value": injury_value,
            },
            {
                "provider_id": "cbs_sports",
                "semantic_metric_id": "INJURIES",
                "age_seconds": 25,
                "quality_score": 0.96,
                "normalized_value": injury_value,
            },
        ],
    }


def _certify(scenario=None):
    values = _inputs()
    return certify_full_integration(
        values["integration_contract"],
        values["registry"],
        values["router_policy"],
        values["trust_policy"],
        values["identity_health_contract"],
        _snapshot(),
        values["source_receipt_contract"],
        scenario or _scenario(),
    )


def test_step8_contract_binds_all_prior_freezes_and_safety_invariants():
    result = validate_full_integration_contract(_inputs()["integration_contract"])
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "8/8"
    assert result["program_steps"] == 8
    assert result["routing_unit"] == "DATA_FIELD"
    assert result["prior_steps_frozen"] is True
    assert set(result["prior_freeze_tokens"]) == {f"step{i}" for i in range(1, 8)}
    assert result["render_dependency"] is False
    assert result["github_actions_fallback"] == 0
    assert result["freeze_token"] == FREEZE_TOKEN


def test_full_integration_filters_unhealthy_primary_and_early_stops_on_fallback_quorum():
    result = _certify()
    assert result["status"] == "GREEN"
    assert result["certified"] is True
    assert result["route_primary_provider_id"] == "nba_official"
    assert result["active_provider_ids"] == ["official_team_sites", "cbs_sports"]
    assert result["selected_provider_ids"] == ["official_team_sites", "cbs_sports"]
    assert result["decision_status"] == "ACCEPTED_FALLBACK_QUORUM"
    assert result["minimum_quorum_satisfied"] is True
    assert result["early_stop"] is True
    assert result["receipt"]["agreement_result"] == "ACCEPTED_FALLBACK_QUORUM"
    assert result["receipt"]["fallback_rank"] == 3
    assert result["receipt"]["canonical_entity_id"] == "nba:team:phx"
    assert result["network_calls"] is False
    assert result["fabrication"] is False


def test_unhealthy_primary_observation_never_becomes_active():
    result = _certify()
    assert "nba_official" not in result["active_provider_ids"]
    assert {row["provider_id"] for row in result["health_rejected_providers"]} == {"nba_official"}


def test_certification_and_receipt_are_deterministic():
    first = _certify()
    second = _certify()
    assert first == second
    assert first["certification_id"].startswith("USFIC-")
    assert first["receipt"]["receipt_digest"].startswith("sha256:")


def test_unresolved_identity_fails_closed_without_receipt():
    scenario = _scenario()
    scenario["identity_value"] = "Definitely Not A Team"
    result = _certify(scenario)
    assert result["certified"] is False
    assert result["status"] == "FAIL_CLOSED"
    assert result["terminal_status"] == "IDENTITY_UNRESOLVED_FAIL_CLOSED"
    assert result["receipt"] is None
    assert result["active_provider_ids"] == []


def test_insufficient_healthy_quorum_fails_closed_without_receipt():
    scenario = _scenario()
    scenario["observations"] = [
        row for row in scenario["observations"] if row["provider_id"] != "cbs_sports"
    ]
    result = _certify(scenario)
    assert result["certified"] is False
    assert result["status"] == "FAIL_CLOSED"
    assert result["minimum_quorum_satisfied"] is False
    assert result["receipt"] is None


def test_off_route_observation_fails_closed_before_quorum():
    scenario = _scenario()
    scenario["observations"].append(
        {
            "provider_id": "action_network",
            "semantic_metric_id": "INJURIES",
            "age_seconds": 5,
            "quality_score": 0.99,
            "normalized_value": {"player": "Example Player", "status": "OUT"},
        }
    )
    with pytest.raises(ValueError, match="FULL_INTEGRATION_OFF_ROUTE_OBSERVATION"):
        _certify(scenario)


def test_step8_contract_tamper_invalidates_certification():
    contract = copy.deepcopy(_inputs()["integration_contract"])
    contract["prior_freeze_tokens"]["step7"] = "WRONG"
    with pytest.raises(ValueError, match="FULL_INTEGRATION_CONTRACT_FINGERPRINT_MISMATCH"):
        validate_full_integration_contract(contract)
