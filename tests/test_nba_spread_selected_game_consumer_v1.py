from __future__ import annotations

import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("nba_spread_selected_game_consumer_v1")
    assert spec is not None, "nba_spread_selected_game_consumer_v1 must exist"
    return importlib.import_module("nba_spread_selected_game_consumer_v1")


def _games():
    return [
        {
            "game_key": "BOS@DET:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "BOS",
            "home_tricode": "DET",
            "status": "UPCOMING",
            "step9_fair_spread": {"verification": "VERIFIED", "pregame_model": {"verification": "VERIFIED", "fair_away_spread": -3.0, "fair_home_spread": 3.0}},
            "step10_decision": {"verification": "VERIFIED", "decision_state": "PLAY", "pick_text": "BOS -1.5"},
        },
        {
            "game_key": "PHI@NYK:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "PHI",
            "home_tricode": "NYK",
            "status": "UPCOMING",
            "step9_fair_spread": {"verification": "UNAVAILABLE"},
            "step10_decision": {"verification": "UNAVAILABLE", "decision_state": "NO_PLAY"},
        },
    ]


def test_exact_date_and_game_id_resolve_one_selected_game():
    mod = _module()
    result = mod.resolve_selected_game(_games(), date="2026-10-20", game_id="BOS@DET:2026-10-20")
    assert result["verification"] == "VERIFIED"
    assert result["game"]["away_tricode"] == "BOS"
    assert result["game"]["home_tricode"] == "DET"
    assert result["game"]["game_key"] == "BOS@DET:2026-10-20"


def test_mismatched_date_fails_closed_instead_of_fuzzy_matching():
    mod = _module()
    result = mod.resolve_selected_game(_games(), date="2026-10-21", game_id="BOS@DET:2026-10-20")
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SELECTED_GAME_IDENTITY_MISMATCH"
    assert result.get("game") is None


def test_missing_or_ambiguous_identity_fails_closed():
    mod = _module()
    missing = mod.resolve_selected_game(_games(), date="2026-10-20", game_id="")
    assert missing["verification"] == "UNAVAILABLE"
    assert missing["diagnostic_state"] == "SELECTED_GAME_ID_MISSING"

    duplicate = _games() + [dict(_games()[0])]
    ambiguous = mod.resolve_selected_game(duplicate, date="2026-10-20", game_id="BOS@DET:2026-10-20")
    assert ambiguous["verification"] == "UNAVAILABLE"
    assert ambiguous["diagnostic_state"] == "SELECTED_GAME_IDENTITY_AMBIGUOUS"


def test_consumer_state_delegates_frozen_step9_and_step10_without_recomputing():
    mod = _module()
    result = mod.build_selected_game_state(_games(), date="2026-10-20", game_id="BOS@DET:2026-10-20")
    assert result["verification"] == "VERIFIED"
    assert result["fair_record"]["pregame_model"]["fair_home_spread"] == 3.0
    assert result["decision_record"]["pick_text"] == "BOS -1.5"
    assert result["sportsbook_projection_influence"] == 0.0
    assert result["may_modify_model"] is False
    assert result["may_modify_projection"] is False
    assert result["may_modify_probability"] is False
    assert result["may_modify_ranking"] is False


def test_back_route_clears_only_selected_game_identity():
    mod = _module()
    query = {"sport": "nba", "market": "spread", "date": "2026-10-20", "game_id": "BOS@DET:2026-10-20", "foo": "keep"}
    result = mod.build_back_query(query)
    assert result["sport"] == "nba"
    assert result["market"] == "spread"
    assert "game_id" not in result
    assert "date" not in result
    assert result["foo"] == "keep"
