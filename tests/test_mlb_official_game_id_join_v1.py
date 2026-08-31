from __future__ import annotations

import pytest

from sports_api.mlb_official_game_id_join_v1 import (
    MATCH_METHOD,
    MLBOfficialGameIDJoinError,
    canonical_official_game_id,
    join_model_games_to_markets,
)


def test_exact_game_id_join_ignores_order_and_names():
    model = [
        {"game_pk": 824911, "away_team": "MODEL NAME A", "home_team": "MODEL NAME B"},
        {"game_pk": 824473, "away_team": "MODEL NAME C", "home_team": "MODEL NAME D"},
    ]
    market = [
        {"official_game_id": 824473, "away_team": {"name": "Different C"}, "home_team": {"name": "Different D"}},
        {"official_game_id": 824911, "away_team": {"name": "Different A"}, "home_team": {"name": "Different B"}},
    ]

    result = join_model_games_to_markets(model, market)

    assert result["matched_count"] == 2
    assert [row["official_game_id"] for row in result["matched_games"]] == [824473, 824911]
    assert result["match_method"] == MATCH_METHOD
    assert result["fallback_matching_used"] is False


def test_digit_string_and_integer_are_same_exact_identity():
    result = join_model_games_to_markets(
        [{"game_pk": "824911"}],
        [{"official_game_id": 824911}],
    )
    assert result["matched_count"] == 1
    assert result["matched_games"][0]["official_game_id"] == 824911


def test_same_teams_with_different_game_ids_never_match():
    model = [{"game_pk": 111111, "away_team": "Giants", "home_team": "Braves"}]
    market = [{"official_game_id": 222222, "away_team": {"name": "Giants"}, "home_team": {"name": "Braves"}}]

    result = join_model_games_to_markets(model, market)

    assert result["matched_count"] == 0
    assert result["unmatched_model_game_ids"] == [111111]
    assert result["unmatched_market_game_ids"] == [222222]
    assert result["fallback_matching_used"] is False


def test_missing_identity_is_recorded_and_never_matched():
    result = join_model_games_to_markets(
        [{"game_pk": None, "away_team": "A", "home_team": "B"}],
        [{"official_game_id": 824911, "away_team": {"name": "A"}, "home_team": {"name": "B"}}],
    )
    assert result["matched_count"] == 0
    assert len(result["invalid_model_identities"]) == 1
    assert result["invalid_model_identities"][0]["field"] == "game_pk"


def test_duplicate_model_identity_raises_fail_closed():
    with pytest.raises(MLBOfficialGameIDJoinError, match="duplicate model MLB game ID 824911"):
        join_model_games_to_markets(
            [{"game_pk": 824911}, {"game_pk": "824911"}],
            [{"official_game_id": 824911}],
        )


def test_duplicate_market_identity_raises_fail_closed():
    with pytest.raises(MLBOfficialGameIDJoinError, match="duplicate market MLB game ID 824911"):
        join_model_games_to_markets(
            [{"game_pk": 824911}],
            [{"official_game_id": 824911}, {"official_game_id": "824911"}],
        )


@pytest.mark.parametrize("value", [True, False, 0, -1, 824911.0, "824911.0", "", "abc", None])
def test_unsafe_or_noncanonical_identity_values_are_rejected(value):
    with pytest.raises(MLBOfficialGameIDJoinError):
        canonical_official_game_id(value)


def test_output_contract_is_explicitly_exact_and_no_fallback():
    result = join_model_games_to_markets([], [])
    assert result["data_type"] == "mlb_model_market_official_id_join_v1"
    assert result["schema_version"] == 1
    assert result["model_game_id_field"] == "game_pk"
    assert result["market_game_id_field"] == "official_game_id"
    assert result["match_method"] == "official_mlb_game_id_exact"
    assert result["fallback_matching_used"] is False
