import math

import pytest

from sports_api.collectors import nfl_game_totals_features_v1 as features


GAME = {
    "official_event_id": "401772714",
    "away": {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
    "home": {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"},
    "neutral_site": False,
    "venue": {"available": True, "indoor": False},
}

AWAY_PROFILE = {
    "ready": True,
    "official_team_id": "8",
    "abbr": "DET",
    "prior_games": 17,
    "current_games": 2,
    "current_weight": 0.25,
    "ppg": 27.5,
    "papg": 22.0,
    "recent6_pf_pg": 29.0,
    "recent6_pa_pg": 21.5,
}

HOME_PROFILE = {
    "ready": True,
    "official_team_id": "2",
    "abbr": "BUF",
    "prior_games": 17,
    "current_games": 2,
    "current_weight": 0.25,
    "ppg": 28.0,
    "papg": 20.5,
    "recent6_pf_pg": 30.0,
    "recent6_pa_pg": 19.0,
}


def test_feature_contract_is_football_only():
    assert features.SCHEMA_VERSION == "nfl_game_totals_features_v1"
    assert features.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert features.SPORTSBOOK_INPUTS == ()
    assert "total" in features.FORBIDDEN_MARKET_KEYS
    assert "over_price" in features.FORBIDDEN_MARKET_KEYS
    assert "under_price" in features.FORBIDDEN_MARKET_KEYS


def test_build_feature_vector_preserves_exact_identity_and_scoring_inputs():
    payload = features.build_game_totals_feature_vector(GAME, AWAY_PROFILE, HOME_PROFILE)
    assert payload["official_event_id"] == "401772714"
    assert payload["away_team_id"] == "8"
    assert payload["home_team_id"] == "2"
    assert payload["sportsbook_projection_influence"] == 0.0
    assert payload["sportsbook_inputs"] == []
    expected = {
        "away_offense_ppg",
        "away_defense_papg",
        "away_recent6_pf_pg",
        "away_recent6_pa_pg",
        "home_offense_ppg",
        "home_defense_papg",
        "home_recent6_pf_pg",
        "home_recent6_pa_pg",
        "neutral_site",
    }
    assert set(payload["features"]) == expected
    assert all(
        isinstance(value, (int, float, bool)) and (isinstance(value, bool) or math.isfinite(float(value)))
        for value in payload["features"].values()
    )
    assert payload["quality"]["away_prior_games"] == 17
    assert payload["quality"]["home_prior_games"] == 17


def test_feature_vector_contains_no_market_keys():
    payload = features.build_game_totals_feature_vector(GAME, AWAY_PROFILE, HOME_PROFILE)
    normalized = {str(key).casefold() for key in payload["features"]}
    assert normalized.isdisjoint(features.FORBIDDEN_MARKET_KEYS)


def test_feature_builder_fails_closed_if_market_data_is_injected():
    contaminated = dict(GAME)
    contaminated["total"] = 48.5
    with pytest.raises(features.NFLGameTotalsFeatureError):
        features.build_game_totals_feature_vector(contaminated, AWAY_PROFILE, HOME_PROFILE)


def test_feature_builder_fails_closed_on_team_identity_mismatch():
    bad = dict(AWAY_PROFILE)
    bad["official_team_id"] = "999"
    with pytest.raises(features.NFLGameTotalsFeatureError):
        features.build_game_totals_feature_vector(GAME, bad, HOME_PROFILE)


def test_feature_builder_fails_closed_on_incomplete_profile():
    bad = dict(HOME_PROFILE)
    bad["ppg"] = None
    with pytest.raises(features.NFLGameTotalsFeatureError):
        features.build_game_totals_feature_vector(GAME, AWAY_PROFILE, bad)
