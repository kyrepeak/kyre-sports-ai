import copy
import math
from pathlib import Path

import pytest

from devsystem.universal_sports_identity_health_v1 import (
    FREEZE_TOKEN,
    STEP,
    WORKSTREAM,
    build_identity_health_context,
    load_identity_health_contract,
    resolve_canonical_identity,
    seal_identity_health_snapshot,
    validate_identity_health_contract,
    validate_identity_health_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-identity-health-v1.json"


def _contract():
    return load_identity_health_contract(CONTRACT_PATH)


def _health(provider, field, state, *, age=10, quality=1.0, validation="VALID", reason="fixture"):
    return {
        "provider_id": provider,
        "field": field,
        "health_state": state,
        "age_seconds": age,
        "quality_score": quality,
        "validation_result": validation,
        "reason": reason,
    }


def _snapshot():
    raw = {
        "version": "UNIVERSAL_SPORTS_IDENTITY_HEALTH_SNAPSHOT_V1",
        "workstream": "universal-sports-source-finalization-v1",
        "revision": 1,
        "routing_unit": "DATA_FIELD",
        "entities": [
            {
                "canonical_id": "nfl:team:was",
                "entity_type": "team",
                "sport": "nfl",
                "canonical_key": "WAS",
                "canonical_name": "Washington Commanders",
                "provider_ids": {"espn": "WSH", "nfl_official": "WAS", "cbs_sports": "WAS"},
                "aliases": [
                    {"provider_id": "*", "value": "Washington Commanders"},
                    {"provider_id": "espn", "value": "WSH"},
                ],
            },
            {
                "canonical_id": "nfl:player:example-qb",
                "entity_type": "player",
                "sport": "nfl",
                "canonical_key": "example-qb",
                "canonical_name": "Example Quarterback",
                "provider_ids": {"espn": "athlete-100", "nfl_official": "player-100"},
                "aliases": [{"provider_id": "*", "value": "Example QB"}],
            },
            {
                "canonical_id": "nfl:game:ind-at-was-2026-10-18",
                "entity_type": "game",
                "sport": "nfl",
                "canonical_key": "IND@WAS:2026-10-18",
                "canonical_name": "Indianapolis at Washington 2026-10-18",
                "provider_ids": {"espn": "event-100", "nfl_official": "game-100"},
                "aliases": [{"provider_id": "espn", "value": "event-100"}],
            },
        ],
        "provider_health": [
            _health("nfl_official", "schedule", "HEALTHY", age=5, quality=1.0),
            _health("espn", "schedule", "UNHEALTHY", age=30, quality=0.8, reason="schedule endpoint failing"),
            _health("cbs_sports", "schedule", "DEGRADED", age=20, quality=0.9),
            _health("nfl_official", "injuries", "UNHEALTHY", age=5, quality=1.0, reason="injury feed unavailable"),
            _health("espn", "injuries", "HEALTHY", age=15, quality=0.95),
            _health("cbs_sports", "injuries", "UNKNOWN", age=0, quality=0.0, validation="UNKNOWN", reason="not checked"),
        ],
        "network_calls": False,
        "fabrication": False,
        "mutation_authority": False,
    }
    return seal_identity_health_snapshot(raw)


def _route(field="schedule"):
    return {
        "status": "ROUTE_READY",
        "sport": "nfl",
        "field": field,
        "semantic_metric_id": field.upper(),
        "primary_provider_id": "nfl_official",
        "fallback_provider_ids": ["espn", "cbs_sports"],
        "eligible_provider_ids": ["nfl_official", "espn", "cbs_sports"],
        "blocked_providers": [],
        "active_provider_ids": [],
        "routing_unit": "DATA_FIELD",
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "route_id": "ROUTE-STEP5-FIXTURE",
    }


def test_valid_contract_certifies_step5():
    result = validate_identity_health_contract(_contract())
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "5/8"
    assert result["routing_unit"] == "DATA_FIELD"
    assert result["provider_health_scope"] == "DATA_FIELD"
    assert result["canonical_ids_owned_internally"] is True
    assert result["health_inspection_activates_provider"] is False
    assert result["network_calls"] is False
    assert result["github_actions_fallback"] == 0
    assert result["freeze_token"] == FREEZE_TOKEN


def test_provider_specific_team_alias_resolves_to_internal_canonical_id():
    result = resolve_canonical_identity(_contract(), _snapshot(), entity_type="team", value="WSH", provider_id="espn")
    assert result["status"] == "IDENTITY_RESOLVED"
    assert result["canonical_entity_id"] == "nfl:team:was"
    assert result["canonical_key"] == "WAS"
    assert result["provider_entity_id"] == "WSH"
    assert result["aliases_used"] == [{"provider_id": "espn", "value": "WSH"}]


def test_player_and_game_identity_types_are_canonical():
    player = resolve_canonical_identity(_contract(), _snapshot(), entity_type="player", value="Example QB")
    game = resolve_canonical_identity(_contract(), _snapshot(), entity_type="game", value="event-100", provider_id="espn")
    assert player["canonical_entity_id"] == "nfl:player:example-qb"
    assert game["canonical_entity_id"] == "nfl:game:ind-at-was-2026-10-18"


def test_unresolved_identity_fails_closed_without_provider_activity():
    result = resolve_canonical_identity(_contract(), _snapshot(), entity_type="team", value="not-a-team", provider_id="espn")
    assert result["status"] == "IDENTITY_UNRESOLVED_FAIL_CLOSED"
    assert result["active_provider_ids"] == []
    assert result["fabrication"] is False


def test_ambiguous_provider_alias_fails_closed():
    snapshot = _snapshot()
    raw = copy.deepcopy(snapshot)
    raw.pop("snapshot_id")
    raw["entities"].append({
        "canonical_id": "nfl:team:other",
        "entity_type": "team",
        "sport": "nfl",
        "canonical_key": "OTHER",
        "canonical_name": "Other Team",
        "provider_ids": {"espn": "WSH"},
        "aliases": [{"provider_id": "espn", "value": "WSH"}],
    })
    ambiguous = seal_identity_health_snapshot(raw)
    result = resolve_canonical_identity(_contract(), ambiguous, entity_type="team", value="WSH", provider_id="espn")
    assert result["status"] == "AMBIGUOUS_IDENTITY_FAIL_CLOSED"
    assert result["active_provider_ids"] == []


def test_field_health_is_capability_specific_and_preserves_route_order():
    schedule = build_identity_health_context(
        _contract(), _snapshot(), _route("schedule"), entity_type="team", value="WSH", provider_id="espn"
    )
    injuries = build_identity_health_context(
        _contract(), _snapshot(), _route("injuries"), entity_type="team", value="WSH", provider_id="espn"
    )
    assert schedule["status"] == "IDENTITY_HEALTH_READY"
    assert schedule["usable_provider_ids"] == ["nfl_official", "cbs_sports"]
    assert [x["provider_id"] for x in schedule["provider_field_health"]] == ["nfl_official", "espn", "cbs_sports"]
    assert schedule["provider_field_health"][0]["fallback_rank"] == 1
    assert schedule["provider_field_health"][2]["fallback_rank"] == 3
    assert schedule["rejected_providers"] == [{"provider_id": "espn", "reason": "PROVIDER_FIELD_UNHEALTHY"}]
    assert injuries["usable_provider_ids"] == ["espn"]
    assert injuries["rejected_providers"] == [
        {"provider_id": "nfl_official", "reason": "PROVIDER_FIELD_UNHEALTHY"},
        {"provider_id": "cbs_sports", "reason": "PROVIDER_FIELD_HEALTH_UNKNOWN"},
    ]


def test_health_inspection_never_marks_providers_active():
    context = build_identity_health_context(
        _contract(), _snapshot(), _route(), entity_type="team", value="WAS"
    )
    assert context["active_provider_ids"] == []
    assert context["network_calls"] is False
    assert context["page_wide_source_authority"] is False


def test_missing_field_health_is_unknown_and_fail_closed_for_that_provider_only():
    route = _route("official_stats")
    context = build_identity_health_context(_contract(), _snapshot(), route, entity_type="team", value="WAS")
    assert context["usable_provider_ids"] == []
    assert context["rejected_providers"] == [
        {"provider_id": "nfl_official", "reason": "PROVIDER_FIELD_HEALTH_UNKNOWN"},
        {"provider_id": "espn", "reason": "PROVIDER_FIELD_HEALTH_UNKNOWN"},
        {"provider_id": "cbs_sports", "reason": "PROVIDER_FIELD_HEALTH_UNKNOWN"},
    ]


def test_invalid_validation_result_blocks_otherwise_healthy_provider():
    raw = _snapshot()
    raw = copy.deepcopy(raw)
    raw.pop("snapshot_id")
    raw["provider_health"][0]["validation_result"] = "INVALID"
    raw["provider_health"][0]["reason"] = "schema validation failed"
    snapshot = seal_identity_health_snapshot(raw)
    context = build_identity_health_context(_contract(), snapshot, _route(), entity_type="team", value="WAS")
    assert context["usable_provider_ids"] == ["cbs_sports"]
    assert context["rejected_providers"][0] == {"provider_id": "nfl_official", "reason": "PROVIDER_FIELD_VALIDATION_FAILED"}


def test_context_and_identity_ids_are_deterministic():
    first = build_identity_health_context(_contract(), _snapshot(), _route(), entity_type="team", value="WSH", provider_id="espn")
    second = build_identity_health_context(_contract(), _snapshot(), _route(), entity_type="team", value="WSH", provider_id="espn")
    identity = resolve_canonical_identity(_contract(), _snapshot(), entity_type="team", value="WSH", provider_id="espn")
    assert first["context_id"] == second["context_id"]
    assert first["identity_resolution_id"] == identity["identity_resolution_id"]


def test_snapshot_fingerprint_tamper_is_rejected():
    snapshot = _snapshot()
    broken = copy.deepcopy(snapshot)
    broken["provider_health"][0]["health_state"] = "DEGRADED"
    with pytest.raises(ValueError, match="IDENTITY_HEALTH_SNAPSHOT_FINGERPRINT_MISMATCH"):
        validate_identity_health_snapshot(broken)


def test_contract_fingerprint_tamper_is_rejected():
    broken = copy.deepcopy(_contract())
    broken["provider_health_scope"] = "GLOBAL"
    with pytest.raises(ValueError, match="IDENTITY_HEALTH_CONTRACT_FINGERPRINT_MISMATCH"):
        validate_identity_health_contract(broken)


@pytest.mark.parametrize("field,value", [("age_seconds", float("nan")), ("quality_score", float("inf"))])
def test_non_finite_field_health_numbers_are_rejected(field, value):
    raw = _snapshot()
    raw = copy.deepcopy(raw)
    raw.pop("snapshot_id")
    raw["provider_health"][0][field] = value
    snapshot = seal_identity_health_snapshot(raw)
    with pytest.raises(ValueError, match="IDENTITY_HEALTH_NUMERIC_INVALID"):
        validate_identity_health_snapshot(snapshot)
