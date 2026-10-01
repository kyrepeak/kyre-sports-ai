from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.unified_data_identity_provider_health_graph_v1 import (
    UnifiedDataIdentityHealthFailure,
    contract_self_test,
    load_cases,
    resolve_identity,
    route_field,
    seal_graph,
    validate_graph,
)

CASES = Path("devsystem/unified_data_identity_provider_health_cases_v1.json")


def _graph():
    return load_cases(CASES)["reference_graph"]


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["unhealthy_primary_falls_back"] is True
    assert result["source_lock_forbidden"] is True
    assert result["team_player_event_supported"] is True


def test_repository_cases_are_grounded_in_existing_router_contracts():
    payload = load_cases(CASES)
    sources = {row["source"] for row in payload["historical_basis"]}
    assert {
        "cfb_top_picks_source_router_v1.py",
        "sports_api/nfl_data_router_v1.py",
        "nfl_prop_analytics_roster_truth_v1.py",
        "sports_api/wnba_prop_feed_failover.py",
    } <= sources


def test_washington_espn_alias_resolves_to_canonical_was():
    result = resolve_identity(
        _graph(),
        entity_type="team",
        value="WSH",
        provider_id="espn",
    )
    assert result["ready"] is True
    assert result["entity_id"] == "nfl:team:was"
    assert result["canonical_key"] == "WAS"
    assert result["provider_entity_id"] == "WSH"


def test_unhealthy_primary_falls_back_at_data_field_level():
    result = route_field(_graph(), entity_id="nfl:team:was", field="active_roster")
    assert result["ready"] is True
    assert result["unit_of_work"] == "DATA_FIELD"
    assert result["selected_provider_id"] == "nflverse"
    assert result["fallback_rank"] == 2
    assert result["attempts"][0]["reason"] == "PROVIDER_UNHEALTHY"
    assert result["provenance"]["field_proof"]["conclusion"] == "SUCCESS"


def test_second_field_can_use_different_provider_without_source_loyalty():
    result = route_field(_graph(), entity_id="nfl:team:was", field="schedule")
    assert result["ready"] is True
    assert result["selected_provider_id"] == "cbs"
    assert result["fallback_rank"] == 2
    assert result["no_source_loyalty"] is True


def test_all_provider_exhaustion_never_fabricates():
    result = route_field(_graph(), entity_id="nfl:team:was", field="injury_report")
    assert result["ready"] is False
    assert result["state"] == "UNAVAILABLE_AFTER_SOURCE_EXHAUSTION"
    assert result["fabricated"] is False
    assert result["selected_provider_id"] == ""


def test_source_lock_is_rejected():
    with pytest.raises(UnifiedDataIdentityHealthFailure, match="SOURCE_LOYALTY_FORBIDDEN"):
        route_field(
            _graph(),
            entity_id="nfl:team:was",
            field="active_roster",
            source_lock="espn",
        )


def test_usable_provider_requires_successful_last_proof():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    provider = next(row for row in graph["providers"] if row["provider_id"] == "nflverse")
    provider.pop("last_successful_proof", None)
    graph = seal_graph(graph)
    with pytest.raises(UnifiedDataIdentityHealthFailure):
        validate_graph(graph)


def test_ambiguous_alias_fails_closed():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph["entities"].append(
        {
            "entity_id": "nfl:team:other",
            "entity_type": "team",
            "canonical_key": "OTH",
            "canonical_name": "Other Team",
            "aliases": [{"value": "Washington Commanders", "provider_id": "*"}],
            "provider_ids": {"espn": "OTH"},
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(UnifiedDataIdentityHealthFailure):
        validate_graph(graph)


def test_graph_tamper_fails_closed():
    graph = deepcopy(_graph())
    graph["revision"] = 999
    with pytest.raises(UnifiedDataIdentityHealthFailure, match="fingerprint"):
        validate_graph(graph)


def test_reference_graph_supports_team_player_event_identity():
    graph = _graph()
    assert {row["entity_type"] for row in graph["entities"]} == {"team", "player", "event"}
