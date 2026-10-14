import copy
from pathlib import Path

import pytest

from devsystem.universal_sports_provider_registry_v1 import load_registry
from devsystem.universal_sports_field_router_v1 import (
    FREEZE_TOKEN,
    ROUTING_UNIT,
    STEP,
    WORKSTREAM,
    load_router_policy,
    route_field,
    validate_router_policy,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"
POLICY_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-field-router-v1.json"


def _registry():
    return load_registry(REGISTRY_PATH)


def _policy():
    return load_router_policy(POLICY_PATH)


def test_valid_policy_certifies_step3_field_router():
    result = validate_router_policy(_policy(), _registry())
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "3/8"
    assert result["routing_unit"] == ROUTING_UNIT == "DATA_FIELD"
    assert result["page_wide_source_authority"] is False
    assert result["network_calls"] is False
    assert result["product_runtime_mutation"] is False
    assert result["sports_model_mutation"] is False
    assert result["github_actions_fallback"] == 0
    assert result["freeze_token"] == FREEZE_TOKEN
    assert result["route_count"] == 15


def test_nba_schedule_routes_only_compatible_nba_sources_with_official_primary():
    routed = route_field(_registry(), _policy(), sport="nba", field="schedule")
    assert routed["status"] == "ROUTE_READY"
    assert routed["semantic_metric_id"] == "SCHEDULE"
    assert routed["primary_provider_id"] == "nba_official"
    assert "espn" in routed["fallback_provider_ids"]
    assert "cbs_sports" in routed["fallback_provider_ids"]
    assert "wnba_official" not in routed["eligible_provider_ids"]
    assert routed["active_provider_ids"] == []
    assert routed["page_wide_source_authority"] is False
    assert routed["network_calls"] is False
    assert routed["fabrication"] is False


def test_unconfigured_credentialed_providers_are_blocked_not_active_or_eligible():
    routed = route_field(_registry(), _policy(), sport="nba", field="sportsbook_lines")
    blocked = {row["provider_id"]: row["reason"] for row in routed["blocked_providers"]}
    assert blocked["direct_sportsbook_feed"] == "CREDENTIALS_NOT_CONFIGURED"
    assert blocked["sportradar"] == "CREDENTIALS_NOT_CONFIGURED"
    assert blocked["sportsdataio"] == "CREDENTIALS_NOT_CONFIGURED"
    assert "direct_sportsbook_feed" not in routed["eligible_provider_ids"]
    assert "sportradar" not in routed["eligible_provider_ids"]
    assert "sportsdataio" not in routed["eligible_provider_ids"]
    assert routed["primary_provider_id"] == "action_network"
    assert routed["active_provider_ids"] == []


def test_public_bet_count_never_substitutes_percentage_or_money_sources():
    routed = route_field(_registry(), _policy(), sport="nba", field="public_bet_count")
    assert routed["status"] == "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
    assert routed["semantic_metric_id"] == "PUBLIC_BET_COUNT"
    assert routed["eligible_provider_ids"] == []
    assert routed["primary_provider_id"] == ""
    assert routed["fallback_provider_ids"] == []
    blocked_ids = {row["provider_id"] for row in routed["blocked_providers"]}
    assert blocked_ids == {"direct_sportsbook_feed"}
    assert "action_network" not in blocked_ids
    assert "covers" not in blocked_ids
    assert "vsin" not in blocked_ids


def test_public_bet_percentage_routes_only_percentage_capable_sources():
    routed = route_field(_registry(), _policy(), sport="nba", field="public_bet_percentage")
    assert routed["status"] == "ROUTE_READY"
    assert routed["semantic_metric_id"] == "PUBLIC_BET_PERCENTAGE"
    assert routed["primary_provider_id"] == "action_network"
    assert set(routed["eligible_provider_ids"]) == {"action_network", "covers", "vsin"}
    assert "direct_sportsbook_feed" not in routed["eligible_provider_ids"]


def test_unknown_field_or_sport_fails_closed_without_candidates():
    unknown_field = route_field(_registry(), _policy(), sport="nba", field="not_a_metric")
    unknown_sport = route_field(_registry(), _policy(), sport="not_a_sport", field="schedule")
    for routed in (unknown_field, unknown_sport):
        assert routed["status"] == "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
        assert routed["eligible_provider_ids"] == []
        assert routed["primary_provider_id"] == ""
        assert routed["fallback_provider_ids"] == []
        assert routed["active_provider_ids"] == []
        assert routed["network_calls"] is False


def test_identical_inputs_produce_identical_route_id_and_order():
    first = route_field(_registry(), _policy(), sport="nfl", field="injuries")
    second = route_field(_registry(), _policy(), sport="nfl", field="injuries")
    assert first["route_id"] == second["route_id"]
    assert first["eligible_provider_ids"] == second["eligible_provider_ids"]
    assert first["blocked_providers"] == second["blocked_providers"]


def test_every_policy_route_matches_registry_semantic_metric_exactly():
    registry = _registry()
    policy = _policy()
    for field, route in policy["routes"].items():
        assert route["semantic_metric_id"] == registry["capabilities"][field]["semantic_metric_id"]
        assert route["compatible_substitutes"] == []


def test_tampered_policy_fingerprint_fails_closed():
    policy = _policy()
    broken = copy.deepcopy(policy)
    preferred = broken["routes"]["schedule"]["preferred_source_types"]
    preferred[0], preferred[1] = preferred[1], preferred[0]
    with pytest.raises(ValueError, match="ROUTER_FINGERPRINT"):
        validate_router_policy(broken, _registry())
