from __future__ import annotations

import importlib
from pathlib import Path


MODULE_PATH = Path("nba_spread_sharp_money_v1.py")
PAGE_PATH = Path("nba_spread_page_v1.py")


def _module():
    assert MODULE_PATH.is_file(), "Step 5 RED: nba_spread_sharp_money_v1.py must be implemented"
    return importlib.import_module("nba_spread_sharp_money_v1")


def _verified_schedule():
    return [
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "away_name": "Boston Celtics",
            "home_name": "New York Knicks",
            "game_date_phoenix": "2026-10-13",
            "tip_phoenix": "4:30 PM",
            "status": "UPCOMING",
        },
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
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "away_name": "Denver Nuggets",
            "home_name": "Golden State Warriors",
            "game_date_phoenix": "2026-10-15",
            "tip_phoenix": "7:30 PM",
            "status": "FINAL",
        },
    ]


def test_selects_largest_verified_money_vs_bet_divergence_with_positive_volume():
    module = _module()
    rows = [
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "bet_count": 8200,
            "away_bet_pct": 45,
            "home_bet_pct": 55,
            "away_money_pct": 52,
            "home_money_pct": 48,
        },
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "bet_count": 12500,
            "away_bet_pct": 31,
            "home_bet_pct": 69,
            "away_money_pct": 68,
            "home_money_pct": 32,
        },
        {
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "bet_count": 30000,
            "away_bet_pct": 20,
            "home_bet_pct": 80,
            "away_money_pct": 75,
            "home_money_pct": 25,
        },
    ]

    feature = module.select_sharp_money_game(rows, _verified_schedule())

    assert feature["verification"] == "VERIFIED"
    assert feature["away_tricode"] == "LAL"
    assert feature["home_tricode"] == "PHX"
    assert feature["sharp_side_tricode"] == "LAL"
    assert feature["sharp_side_name"] == "Los Angeles Lakers"
    assert feature["sharp_bet_pct"] == 31
    assert feature["sharp_money_pct"] == 68
    assert feature["sharp_gap_pct"] == 37
    assert feature["bet_count"] == 12500
    assert feature["tip_phoenix"] == "7:00 PM"
    assert feature["game_date_phoenix"] == "2026-10-14"


def test_requires_positive_authoritative_volume_instead_of_inventing_a_threshold():
    module = _module()
    rows = [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_bet_pct": 31,
            "home_bet_pct": 69,
            "away_money_pct": 68,
            "home_money_pct": 32,
        }
    ]

    feature = module.select_sharp_money_game(rows, _verified_schedule())

    assert feature == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "SHARP_VOLUME_UNVERIFIED",
    }


def test_fails_closed_on_invalid_betting_splits():
    module = _module()
    rows = [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "bet_count": 12500,
            "away_bet_pct": 80,
            "home_bet_pct": 30,
            "away_money_pct": 68,
            "home_money_pct": 32,
        }
    ]

    feature = module.select_sharp_money_game(rows, _verified_schedule())

    assert feature == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "INVALID_BETTING_SPLITS",
    }


def test_fails_closed_when_row_does_not_match_frozen_step3_schedule():
    module = _module()
    rows = [
        {
            "away_tricode": "MIA",
            "home_tricode": "ORL",
            "bet_count": 50000,
            "away_bet_pct": 20,
            "home_bet_pct": 80,
            "away_money_pct": 75,
            "home_money_pct": 25,
        }
    ]

    feature = module.select_sharp_money_game(rows, _verified_schedule())

    assert feature == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_VERIFIED_SCHEDULE_MATCH",
    }


def test_equal_top_divergence_is_ambiguous_and_never_guessed():
    module = _module()
    rows = [
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "bet_count": 8200,
            "away_bet_pct": 30,
            "home_bet_pct": 70,
            "away_money_pct": 65,
            "home_money_pct": 35,
        },
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "bet_count": 12500,
            "away_bet_pct": 31,
            "home_bet_pct": 69,
            "away_money_pct": 66,
            "home_money_pct": 34,
        },
    ]

    feature = module.select_sharp_money_game(rows, _verified_schedule())

    assert feature == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "AMBIGUOUS_SHARP_MONEY_GAME",
    }


def test_current_universal_routes_fail_closed_when_authoritative_volume_is_unavailable():
    module = _module()

    routes = module.resolve_sharp_money_routes()
    feature = module.load_sharp_money_feature(_verified_schedule())

    assert routes["public_bet_percentage"]["status"] == "ROUTE_READY"
    assert routes["money_percentage"]["status"] == "ROUTE_READY"
    assert routes["public_bet_count"]["status"] == "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
    assert routes["public_bet_count"]["semantic_metric_id"] == "PUBLIC_BET_COUNT"
    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "SHARP_VOLUME_ROUTE_UNAVAILABLE"
    assert feature["fabrication"] is False
    assert feature["page_wide_source_authority"] is False


def test_step5_does_not_activate_later_model_injury_probability_or_ranking_layers():
    module = _module()

    assert module.SHARP_MONEY_LABEL == "💰 Sharp Money Game"
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_ACTIVATE_INJURIES is False
    assert module.MAY_ACTIVATE_RANKING is False
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_page_adds_step5_marker_while_preserving_frozen_step4_source_contract():
    _module()
    page = PAGE_PATH.read_text()

    assert 'data-testid="nba-spread-step4-most-bet-active"' in page
    assert 'data-testid="nba-spread-step5-sharp-money-active"' in page
    assert "SHARP_MONEY_LABEL" in page
    assert "Sharp Money Game" not in page
    assert "Kyre Fair Spread" not in page
    assert "Cover Probability" not in page
