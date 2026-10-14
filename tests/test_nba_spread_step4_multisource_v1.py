from __future__ import annotations

import nba_spread_most_bet_v1 as step4


def _schedule() -> list[dict]:
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-14",
            "tip_phoenix": "7:00 PM",
            "status": "UPCOMING",
            "source_game_ids": {
                "nba_official": "nba-lal-phx-20261014",
                "espn": "espn-lal-phx-20261014",
            },
        }
    ]


def test_public_bet_count_route_comes_from_frozen_universal_router():
    route = step4.resolve_public_bet_count_route()

    assert route["semantic_metric_id"] == "PUBLIC_BET_COUNT"
    assert route["status"] == "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
    assert route["eligible_provider_ids"] == []
    assert route["primary_provider_id"] is None
    blocked = {row["provider_id"] for row in route["blocked_providers"]}
    assert blocked == {"direct_sportsbook_feed"}
    assert route["active_provider_ids"] == []
    assert route["page_wide_source_authority"] is False
    assert route["fabrication"] is False


def test_most_bet_feature_fails_closed_before_consulting_incompatible_public_split_sources(monkeypatch):
    def incompatible_source_must_not_run(*args, **kwargs):
        raise AssertionError("Action Network cannot own PUBLIC_BET_COUNT")

    monkeypatch.setattr(step4, "fetch_action_network_rows", incompatible_source_must_not_run)

    feature = step4.load_most_bet_feature(_schedule())

    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "PUBLIC_BET_COUNT_ROUTE_UNAVAILABLE"
    assert feature["semantic_metric_id"] == "PUBLIC_BET_COUNT"
    assert feature["active_provider_ids"] == []
    assert feature["eligible_provider_ids"] == []
    assert feature["fabrication"] is False


def test_percentages_are_never_substituted_for_absolute_bet_count():
    route = step4.resolve_public_bet_count_route()
    blocked_ids = {row["provider_id"] for row in route["blocked_providers"]}

    assert "action_network" not in route["eligible_provider_ids"]
    assert "covers" not in route["eligible_provider_ids"]
    assert "vsin" not in route["eligible_provider_ids"]
    assert "direct_sportsbook_feed" in blocked_ids


def test_frozen_page_contract_stays_outside_step4_repair_scope():
    assert step4.MAY_MODIFY_MODEL is False
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.MAY_MODIFY_PROBABILITY is False
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
