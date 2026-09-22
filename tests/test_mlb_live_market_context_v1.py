from copy import deepcopy

import pytest

from sports_api.mlb_live_market_context_v1 import (
    attach_live_market_context,
    market_context_from_game,
)
from sports_api.mlb_official_game_id_join_v1 import MLBOfficialGameIDJoinError


def market_game(game_id=777001, *, sportsbook="FanDuel"):
    return {
        "official_game_id": game_id,
        "sportsbook": sportsbook,
        "scheduled_start_utc": "2026-08-31T19:05:00+00:00",
        "source_event_id": "fd-abc",
        "away_team": {"name": "Away Same"},
        "home_team": {"name": "Home Same"},
        "markets": {
            "moneyline": {"away_odds": 120, "home_odds": -142},
            "run_line": {
                "away_line": 1.5,
                "away_odds": -175,
                "home_line": -1.5,
                "home_odds": 145,
            },
            "total": {"line": 8.5, "over_odds": -105, "under_odds": -115},
        },
    }


def test_complete_fanduel_market_context_preserves_raw_values():
    row = market_game()
    ctx = market_context_from_game(row)
    assert ctx["official_game_id"] == 777001
    assert ctx["moneyline"] == {"away_odds": 120, "home_odds": -142}
    assert ctx["run_line"]["away_line"] == 1.5
    assert ctx["total"] == {"line": 8.5, "over_odds": -105, "under_odds": -115}
    assert ctx["match_method"] == "official_mlb_game_id_exact"
    assert ctx["fallback_matching_used"] is False


def test_exact_id_join_attaches_when_order_is_reversed():
    models = [{"game_pk": 777001}, {"game_pk": 777002}]
    markets = [market_game(777002), market_game(777001)]
    result = attach_live_market_context(models, markets)
    assert result["attached_count"] == 2
    assert sorted(result["contexts_by_game_id"]) == [777001, 777002]
    assert result["fallback_matching_used"] is False


def test_wrong_id_same_team_names_never_attaches():
    models = [{"game_pk": 777099, "away_team": "Away Same", "home_team": "Home Same"}]
    markets = [market_game(777001)]
    result = attach_live_market_context(models, markets)
    assert result["attached_count"] == 0
    assert result["unmatched_model_game_ids"] == [777099]
    assert result["unmatched_market_game_ids"] == [777001]


def test_missing_model_id_never_attaches():
    result = attach_live_market_context([{"game_pk": None}], [market_game()])
    assert result["attached_count"] == 0
    assert len(result["invalid_model_identities"]) == 1


def test_missing_market_id_never_attaches():
    row = market_game()
    row.pop("official_game_id")
    result = attach_live_market_context([{"game_pk": 777001}], [row])
    assert result["attached_count"] == 0
    assert len(result["invalid_market_identities"]) == 1


def test_duplicate_model_id_fails_closed():
    with pytest.raises(MLBOfficialGameIDJoinError):
        attach_live_market_context(
            [{"game_pk": 777001}, {"game_pk": 777001}],
            [market_game()],
        )


def test_duplicate_market_id_fails_closed():
    with pytest.raises(MLBOfficialGameIDJoinError):
        attach_live_market_context(
            [{"game_pk": 777001}],
            [market_game(), market_game()],
        )


@pytest.mark.parametrize(
    ("market", "field"),
    [
        ("moneyline", "away_odds"),
        ("moneyline", "home_odds"),
        ("run_line", "away_line"),
        ("run_line", "away_odds"),
        ("run_line", "home_line"),
        ("run_line", "home_odds"),
        ("total", "line"),
        ("total", "over_odds"),
        ("total", "under_odds"),
    ],
)
def test_missing_required_market_value_is_not_fabricated(market, field):
    row = market_game()
    row["markets"][market][field] = None
    assert market_context_from_game(row) is None
    result = attach_live_market_context([{"game_pk": 777001}], [row])
    assert result["exact_id_matched_count"] == 1
    assert result["attached_count"] == 0
    assert result["unusable_matched_game_ids"] == [777001]


def test_non_fanduel_row_is_not_attached():
    row = market_game(sportsbook="OtherBook")
    assert market_context_from_game(row) is None


def test_inputs_are_not_mutated():
    models = [{"game_pk": 777001, "probability": 0.6123, "score": 82.4}]
    markets = [market_game()]
    model_before = deepcopy(models)
    market_before = deepcopy(markets)
    result = attach_live_market_context(models, markets)
    assert result["attached_count"] == 1
    assert models == model_before
    assert markets == market_before


def test_projection_fields_are_not_written_into_context():
    model = {"game_pk": 777001, "probability": 0.6123, "score": 82.4, "projection": 4.7}
    result = attach_live_market_context([model], [market_game()])
    ctx = result["contexts_by_game_id"][777001]
    assert "probability" not in ctx
    assert "score" not in ctx
    assert "projection" not in ctx


def test_output_declares_exact_id_contract():
    result = attach_live_market_context([{"game_pk": "777001"}], [market_game()])
    assert result["data_type"] == "mlb_live_market_context_v1"
    assert result["schema_version"] == 1
    assert result["source"] == "FanDuel"
    assert result["transport"] == "anonymous_public_get_only"
    assert result["model_game_id_field"] == "game_pk"
    assert result["market_game_id_field"] == "official_game_id"
    assert result["match_method"] == "official_mlb_game_id_exact"
    assert result["fallback_matching_used"] is False
