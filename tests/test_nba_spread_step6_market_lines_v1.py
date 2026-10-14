from __future__ import annotations

import importlib
from pathlib import Path


MODULE_PATH = Path("nba_spread_market_lines_v1.py")
PAGE_PATH = Path("nba_spread_page_v1.py")


def _module():
    assert MODULE_PATH.is_file(), "Step 6 RED: nba_spread_market_lines_v1.py must be implemented"
    return importlib.import_module("nba_spread_market_lines_v1")


def _verified_schedule():
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-14",
            "tip_phoenix": "7:00 PM",
            "status": "UPCOMING",
        },
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "away_name": "Boston Celtics",
            "home_name": "New York Knicks",
            "game_date_phoenix": "2026-10-15",
            "tip_phoenix": "4:30 PM",
            "status": "UPCOMING",
        },
        {
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "away_name": "Denver Nuggets",
            "home_name": "Golden State Warriors",
            "game_date_phoenix": "2026-10-15",
            "tip_phoenix": "7:30 PM",
            "status": "FINAL",
        },
    ]


def _quotes():
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "sportsbook": "BookA",
            "away_spread": 2.5,
            "home_spread": -2.5,
        },
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "sportsbook": "BookB",
            "away_spread": 3.5,
            "home_spread": -3.5,
        },
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "sportsbook": "BookC",
            "away_spread": 3.0,
            "home_spread": -3.0,
        },
    ]


def test_consensus_is_median_of_unique_verified_books_and_best_lines_are_side_specific():
    module = _module()
    result = module.build_spread_market_context(_quotes(), _verified_schedule())

    assert result["verification"] == "VERIFIED"
    assert result["away_tricode"] == "LAL"
    assert result["home_tricode"] == "PHX"
    assert result["consensus_away_spread"] == 3.0
    assert result["consensus_home_spread"] == -3.0
    assert result["sportsbook_count"] == 3
    assert result["best_away"] == {"sportsbook": "BookB", "spread": 3.5}
    assert result["best_home"] == {"sportsbook": "BookA", "spread": -2.5}
    assert result["tip_phoenix"] == "7:00 PM"
    assert result["game_date_phoenix"] == "2026-10-14"


def test_consensus_requires_at_least_two_independent_sportsbooks():
    module = _module()
    result = module.build_spread_market_context(_quotes()[:1], _verified_schedule())
    assert result == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "CONSENSUS_QUORUM_NOT_MET",
    }


def test_duplicate_sportsbook_quote_for_same_game_fails_closed():
    module = _module()
    rows = _quotes()[:2] + [dict(_quotes()[0])]
    result = module.build_spread_market_context(rows, _verified_schedule())
    assert result == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "DUPLICATE_SPORTSBOOK_QUOTE",
    }


def test_invalid_spread_pair_fails_closed_instead_of_inventing_other_side():
    module = _module()
    rows = _quotes()
    rows[0] = {**rows[0], "away_spread": 2.5, "home_spread": -3.5}
    result = module.build_spread_market_context(rows, _verified_schedule())
    assert result == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "INVALID_SPREAD_PAIR",
    }


def test_market_rows_must_match_frozen_step3_upcoming_schedule_exactly():
    module = _module()
    rows = [
        {
            "away_tricode": "MIA",
            "home_tricode": "ORL",
            "sportsbook": "BookA",
            "away_spread": 1.5,
            "home_spread": -1.5,
        },
        {
            "away_tricode": "MIA",
            "home_tricode": "ORL",
            "sportsbook": "BookB",
            "away_spread": 2.0,
            "home_spread": -2.0,
        },
    ]
    result = module.build_spread_market_context(rows, _verified_schedule())
    assert result == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_VERIFIED_SCHEDULE_MATCH",
    }


def test_final_games_are_not_eligible_for_step6_pregame_market_context():
    module = _module()
    rows = [
        {
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "sportsbook": "BookA",
            "away_spread": 4.0,
            "home_spread": -4.0,
        },
        {
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "sportsbook": "BookB",
            "away_spread": 4.5,
            "home_spread": -4.5,
        },
    ]
    result = module.build_spread_market_context(rows, _verified_schedule())
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "NO_VERIFIED_SCHEDULE_MATCH"


def test_universal_route_is_exact_sportsbook_lines_semantics_and_not_page_wide_authority():
    module = _module()
    route = module.resolve_spread_market_route()
    assert route["status"] == "ROUTE_READY"
    assert route["semantic_metric_id"] == "SPORTSBOOK_LINES"
    assert route["page_wide_source_authority"] is False
    assert "action_network" in route["eligible_provider_ids"]
    assert "covers" in route["eligible_provider_ids"]
    assert "vsin" in route["eligible_provider_ids"]


def test_production_loader_fails_closed_until_exact_market_observations_are_verified():
    module = _module()
    result = module.load_spread_market_features(_verified_schedule())
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SPORTSBOOK_OBSERVATIONS_NOT_VERIFIED"
    assert result["semantic_metric_id"] == "SPORTSBOOK_LINES"
    assert result["fabrication"] is False
    assert result["page_wide_source_authority"] is False


def test_step6_market_context_does_not_activate_later_decision_layers():
    module = _module()
    assert module.MARKET_SECTION_LABEL == "Market Spread"
    assert module.MAY_ACTIVATE_MARKET_LINES is True
    assert module.MAY_ACTIVATE_INJURIES is False
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_ACTIVATE_RANKING is False
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_page_adds_step6_market_marker_and_preserves_step5_without_later_layer_leakage():
    _module()
    page = PAGE_PATH.read_text()
    assert 'data-testid="nba-spread-step5-sharp-money-active"' in page
    assert 'data-testid="nba-spread-step6-market-lines-active"' in page
    assert "Consensus Spread" in page
    assert "Best Available" in page
    assert "Kyre Fair Spread" not in page
    assert "Cover Probability" not in page
