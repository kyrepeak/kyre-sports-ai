import copy
from pathlib import Path

import pytest

from devsystem.universal_sports_provider_registry_v1 import (
    FREEZE_TOKEN,
    ROUTING_UNIT,
    STEP,
    WORKSTREAM,
    load_registry,
    providers_for_capability,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"


def _registry():
    return load_registry(REGISTRY_PATH)


def test_valid_registry_certifies_step2_provider_pool():
    result = validate_registry(_registry())
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "2/8"
    assert result["routing_unit"] == ROUTING_UNIT == "DATA_FIELD"
    assert result["page_wide_source_authority"] is False
    assert result["approved_pool_is_active_pool"] is False
    assert result["active_provider_semantics"] == "ACTUALLY_CONSULTED_ONLY"
    assert result["network_calls"] is False
    assert result["product_runtime_mutation"] is False
    assert result["legacy_registry_mutation"] is False
    assert result["github_actions_fallback"] == 0
    assert result["provider_count"] >= 12
    assert result["freeze_token"] == FREEZE_TOKEN


def test_required_capabilities_are_explicit_and_metric_specific():
    registry = _registry()
    required = {
        "schedule",
        "game_identity",
        "team_identity",
        "player_identity",
        "rosters",
        "injuries",
        "official_stats",
        "advanced_stats",
        "matchup_history",
        "sportsbook_lines",
        "line_movement",
        "public_bet_count",
        "public_bet_percentage",
        "money_percentage",
        "news_context",
    }
    assert required <= set(registry["capabilities"])
    assert registry["capabilities"]["public_bet_count"]["semantic_metric_id"] == "PUBLIC_BET_COUNT"
    assert registry["capabilities"]["public_bet_percentage"]["semantic_metric_id"] == "PUBLIC_BET_PERCENTAGE"
    assert registry["capabilities"]["money_percentage"]["semantic_metric_id"] == "MONEY_PERCENTAGE"


def test_provider_ids_are_unique_and_duplicate_fails_closed():
    registry = _registry()
    provider_ids = [row["provider_id"] for row in registry["providers"]]
    assert len(provider_ids) == len(set(provider_ids))
    broken = copy.deepcopy(registry)
    broken["providers"].append(copy.deepcopy(broken["providers"][0]))
    with pytest.raises(ValueError, match="PROVIDER_ID"):
        validate_registry(broken)


def test_approved_pool_is_not_active_pool_and_no_page_wide_master_exists():
    registry = _registry()
    assert registry["approved_pool_is_active_pool"] is False
    assert registry["active_provider_semantics"] == "ACTUALLY_CONSULTED_ONLY"
    assert all(row["active"] is False for row in registry["providers"])
    assert all(row["page_wide_authority"] is False for row in registry["providers"])


def test_paid_or_licensed_sources_do_not_claim_configuration_or_reachability():
    registry = _registry()
    by_id = {row["provider_id"]: row for row in registry["providers"]}
    for provider_id in ("sportradar", "sportsdataio"):
        access = by_id[provider_id]["access"]
        assert access["credential_required"] is True
        assert access["configuration_state"] == "NOT_CLAIMED"
        assert access["reachability_state"] == "UNVERIFIED"


def test_official_league_sources_are_sport_scoped_not_universal():
    registry = _registry()
    by_id = {row["provider_id"]: row for row in registry["providers"]}
    official = {
        "nba_official": "nba",
        "wnba_official": "wnba",
        "nfl_official": "nfl",
        "ncaa_official": "ncaaf",
        "mlb_official": "mlb",
    }
    for provider_id, sport in official.items():
        assert by_id[provider_id]["sports"] == [sport]
        assert by_id[provider_id]["page_wide_authority"] is False


def test_capability_lookup_filters_by_exact_capability_and_sport_without_activating_sources():
    registry = _registry()
    rows = providers_for_capability(registry, capability="schedule", sport="nba")
    ids = {row["provider_id"] for row in rows}
    assert "nba_official" in ids
    assert "espn" in ids
    assert "wnba_official" not in ids
    assert "reuters" not in ids
    assert all(row["active"] is False for row in rows)


def test_semantic_metrics_are_not_silently_substituted():
    registry = _registry()
    count_ids = {
        row["provider_id"]
        for row in providers_for_capability(registry, capability="public_bet_count", sport="nba")
    }
    pct_ids = {
        row["provider_id"]
        for row in providers_for_capability(registry, capability="public_bet_percentage", sport="nba")
    }
    money_ids = {
        row["provider_id"]
        for row in providers_for_capability(registry, capability="money_percentage", sport="nba")
    }
    assert count_ids
    assert pct_ids
    assert money_ids
    assert registry["capabilities"]["public_bet_count"]["compatible_substitutes"] == []
    assert registry["capabilities"]["public_bet_percentage"]["compatible_substitutes"] == []
    assert registry["capabilities"]["money_percentage"]["compatible_substitutes"] == []


def test_unknown_capability_or_sport_fails_closed_to_empty_pool():
    registry = _registry()
    assert providers_for_capability(registry, capability="not_a_metric", sport="nba") == []
    assert providers_for_capability(registry, capability="schedule", sport="not_a_sport") == []


def test_tampered_registry_fingerprint_fails_closed():
    registry = _registry()
    broken = copy.deepcopy(registry)
    broken["providers"][0]["display_name"] += " changed"
    with pytest.raises(ValueError, match="REGISTRY_FINGERPRINT"):
        validate_registry(broken)
