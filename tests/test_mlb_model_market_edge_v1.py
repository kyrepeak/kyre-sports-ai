from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_model_market_edge_v1 import (
    DATA_TYPE,
    MLBModelMarketEdgeError,
    SCHEMA_VERSION,
    american_odds_profit_per_unit,
    expected_value_per_unit,
    model_market_edge,
    probability_to_american_odds,
    resolve_candidate_market_side,
)


def _context(game_id: int = 824911) -> dict:
    return {
        "data_type": "mlb_market_probability_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": game_id,
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "probability_method": "proportional_two_way_no_vig",
        "moneyline": {
            "hold_probability": 0.04,
            "away": {"odds": 120, "implied_probability": 0.4545454545, "no_vig_probability": 0.44},
            "home": {"odds": -142, "implied_probability": 0.5867768595, "no_vig_probability": 0.56},
        },
        "run_line": {
            "hold_probability": 0.05,
            "away": {"line": 1.5, "odds": -165, "implied_probability": 0.6226415094, "no_vig_probability": 0.60},
            "home": {"line": -1.5, "odds": 140, "implied_probability": 0.4166666667, "no_vig_probability": 0.40},
        },
        "total": {
            "line": 8.5,
            "hold_probability": 0.047,
            "over": {"odds": -105, "implied_probability": 0.5121951220, "no_vig_probability": 0.49},
            "under": {"odds": -115, "implied_probability": 0.5348837209, "no_vig_probability": 0.51},
        },
    }


def _candidate(market="Moneyline", probability=0.60, *, game_id=824911, side=None, name=None, team=None, line=None):
    return {
        "game_pk": game_id,
        "market": market,
        "probability": probability,
        "side": side,
        "name": name,
        "team": team,
        "line": line,
        "score": 80.0,
    }


def test_probability_to_american_even_money():
    assert probability_to_american_odds(0.5) == pytest.approx(-100.0)


def test_probability_to_american_favorite():
    assert probability_to_american_odds(0.60) == pytest.approx(-150.0)


def test_probability_to_american_underdog():
    assert probability_to_american_odds(0.40) == pytest.approx(150.0)


def test_profit_per_unit_positive_odds():
    assert american_odds_profit_per_unit(150) == pytest.approx(1.5)


def test_profit_per_unit_negative_odds():
    assert american_odds_profit_per_unit(-200) == pytest.approx(0.5)


def test_expected_value_per_unit_positive():
    # 60% model probability at +120: 0.60*1.20 - 0.40 = +0.32 units.
    assert expected_value_per_unit(0.60, 120) == pytest.approx(0.32)


def test_expected_value_per_unit_negative():
    assert expected_value_per_unit(0.40, -150) == pytest.approx(-1.0 / 3.0)


@pytest.mark.parametrize("p", [None, True, False, 0, 1, -0.1, 1.1, float("nan")])
def test_invalid_probability_fails_closed(p):
    with pytest.raises(MLBModelMarketEdgeError):
        probability_to_american_odds(p)


@pytest.mark.parametrize("odds", [None, True, False, 0, 99, -99, float("nan")])
def test_invalid_odds_fail_closed(odds):
    with pytest.raises(MLBModelMarketEdgeError):
        american_odds_profit_per_unit(odds)


def test_resolve_total_over():
    c = _candidate("Total", side="Over 8.5")
    assert resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers") == "over"


def test_resolve_total_under_case_insensitive():
    c = _candidate("Total", side="UNDER 8.5")
    assert resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers") == "under"


def test_resolve_moneyline_from_exact_team_name():
    c = _candidate("Moneyline", name="Brewers")
    assert resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers") == "home"


def test_resolve_runline_from_exact_team_field():
    c = _candidate("Run Line", team="Cubs", line=1.5)
    assert resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers") == "away"


def test_resolve_team_market_from_explicit_away_token():
    c = _candidate("Moneyline", side="Away")
    assert resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers") == "away"


def test_resolve_team_market_ambiguous_fails_closed():
    c = _candidate("Moneyline", side="Pick")
    with pytest.raises(MLBModelMarketEdgeError):
        resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers")


def test_unsupported_player_market_fails_closed():
    c = _candidate("Home Run", name="Player")
    with pytest.raises(MLBModelMarketEdgeError):
        resolve_candidate_market_side(c, away_team="Cubs", home_team="Brewers")


def test_moneyline_edge_contract():
    c = _candidate("Moneyline", probability=0.60, name="Brewers")
    result = model_market_edge(c, _context(), away_team="Cubs", home_team="Brewers")
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source"] == "FanDuel"
    assert result["official_game_id"] == 824911
    assert result["market"] == "Moneyline"
    assert result["selected_side"] == "home"
    assert result["model_probability"] == pytest.approx(0.60)
    assert result["market_no_vig_probability"] == pytest.approx(0.56)
    assert result["edge_probability"] == pytest.approx(0.04)
    assert result["edge_percentage_points"] == pytest.approx(4.0)
    assert result["market_odds"] == pytest.approx(-142)
    assert result["model_fair_american_odds"] == pytest.approx(-150)
    assert result["expected_value_per_unit"] == pytest.approx(0.60 * (100 / 142) - 0.40)
    assert result["comparison_only"] is True


def test_runline_edge_preserves_selected_market_line():
    c = _candidate("Run Line", probability=0.64, team="Cubs", line=1.5)
    result = model_market_edge(c, _context(), away_team="Cubs", home_team="Brewers")
    assert result["selected_side"] == "away"
    assert result["market_line"] == pytest.approx(1.5)
    assert result["market_no_vig_probability"] == pytest.approx(0.60)
    assert result["edge_probability"] == pytest.approx(0.04)


def test_total_edge_preserves_total_line():
    c = _candidate("Total", probability=0.55, side="Over 8.5", line=8.5)
    result = model_market_edge(c, _context(), away_team="Cubs", home_team="Brewers")
    assert result["selected_side"] == "over"
    assert result["market_line"] == pytest.approx(8.5)
    assert result["market_no_vig_probability"] == pytest.approx(0.49)
    assert result["edge_probability"] == pytest.approx(0.06)


def test_negative_model_market_edge_is_preserved_not_clipped():
    c = _candidate("Moneyline", probability=0.50, name="Brewers")
    result = model_market_edge(c, _context(), away_team="Cubs", home_team="Brewers")
    assert result["edge_probability"] == pytest.approx(-0.06)


def test_candidate_and_context_game_id_mismatch_fails_closed():
    c = _candidate("Moneyline", name="Brewers", game_id=824912)
    with pytest.raises(MLBModelMarketEdgeError):
        model_market_edge(c, _context(824911), away_team="Cubs", home_team="Brewers")


def test_fallback_context_fails_closed():
    context = _context()
    context["fallback_matching_used"] = True
    c = _candidate("Moneyline", name="Brewers")
    with pytest.raises(MLBModelMarketEdgeError):
        model_market_edge(c, context, away_team="Cubs", home_team="Brewers")


def test_wrong_sportsbook_fails_closed():
    context = _context()
    context["source"] = "OtherBook"
    c = _candidate("Moneyline", name="Brewers")
    with pytest.raises(MLBModelMarketEdgeError):
        model_market_edge(c, context, away_team="Cubs", home_team="Brewers")


def test_missing_selected_side_block_fails_closed():
    context = _context()
    context["moneyline"].pop("home")
    c = _candidate("Moneyline", name="Brewers")
    with pytest.raises(MLBModelMarketEdgeError):
        model_market_edge(c, context, away_team="Cubs", home_team="Brewers")


def test_model_market_edge_does_not_mutate_inputs():
    c = _candidate("Moneyline", probability=0.60, name="Brewers")
    context = _context()
    c_before = deepcopy(c)
    context_before = deepcopy(context)
    model_market_edge(c, context, away_team="Cubs", home_team="Brewers")
    assert c == c_before
    assert context == context_before
