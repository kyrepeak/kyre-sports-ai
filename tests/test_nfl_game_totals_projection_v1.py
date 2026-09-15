import pytest

import sports_api.nfl_game_totals_projection_v1 as projection


FEATURE_PAYLOAD = {
    "schema_version": "nfl_game_totals_features_v1",
    "official_event_id": "401772714",
    "away_team_id": "8",
    "home_team_id": "2",
    "football_only": True,
    "sportsbook_projection_influence": 0.0,
    "sportsbook_inputs": [],
    "projection_generated": False,
    "features": {
        "away_offense_ppg": 27.5,
        "away_defense_papg": 22.0,
        "away_recent6_pf_pg": 29.0,
        "away_recent6_pa_pg": 21.5,
        "home_offense_ppg": 28.0,
        "home_defense_papg": 20.5,
        "home_recent6_pf_pg": 30.0,
        "home_recent6_pa_pg": 19.0,
        "neutral_site": False,
    },
}


def test_projection_contract_remains_market_independent():
    assert projection.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert projection.SPORTSBOOK_INPUTS == ()
    assert projection.SEASON_WEIGHT + projection.RECENT_WEIGHT == pytest.approx(1.0)
    assert projection.MODEL_VERSION.startswith("NFL GAME TOTALS PROJECTION V1")


def test_projection_returns_team_points_and_combined_total():
    out = projection.project_game_total(FEATURE_PAYLOAD)
    assert out["ready"] is True
    assert out["official_event_id"] == "401772714"
    assert out["away_team_id"] == "8"
    assert out["home_team_id"] == "2"
    assert out["projected_away_points"] == pytest.approx(24.0)
    assert out["projected_home_points"] == pytest.approx(25.1875)
    assert out["projected_total"] == pytest.approx(49.1875)
    assert out["projected_total"] == pytest.approx(
        out["projected_away_points"] + out["projected_home_points"]
    )
    assert out["sportsbook_projection_influence"] == 0.0
    assert out["sportsbook_inputs"] == []
    assert out["market_total_used"] is False


def test_projection_exposes_transparent_scoring_components():
    out = projection.project_game_total(FEATURE_PAYLOAD)
    components = out["components"]
    assert components["away_season_interaction"] == pytest.approx(24.0)
    assert components["away_recent_interaction"] == pytest.approx(24.0)
    assert components["home_season_interaction"] == pytest.approx(25.0)
    assert components["home_recent_interaction"] == pytest.approx(25.75)
    assert components["season_weight"] == projection.SEASON_WEIGHT
    assert components["recent_weight"] == projection.RECENT_WEIGHT


def test_projection_fails_closed_if_sportsbook_input_is_declared():
    payload = dict(FEATURE_PAYLOAD)
    payload["sportsbook_inputs"] = ["total"]
    with pytest.raises(projection.NFLGameTotalsProjectionError):
        projection.project_game_total(payload)


def test_projection_fails_closed_if_projection_influence_is_nonzero():
    payload = dict(FEATURE_PAYLOAD)
    payload["sportsbook_projection_influence"] = 0.01
    with pytest.raises(projection.NFLGameTotalsProjectionError):
        projection.project_game_total(payload)


def test_projection_fails_closed_on_missing_or_nonfinite_feature():
    payload = dict(FEATURE_PAYLOAD)
    features = dict(FEATURE_PAYLOAD["features"])
    features["away_offense_ppg"] = None
    payload["features"] = features
    with pytest.raises(projection.NFLGameTotalsProjectionError):
        projection.project_game_total(payload)


def test_home_away_swap_preserves_total_and_swaps_team_projections():
    original = projection.project_game_total(FEATURE_PAYLOAD)
    swapped = dict(FEATURE_PAYLOAD)
    swapped["away_team_id"] = FEATURE_PAYLOAD["home_team_id"]
    swapped["home_team_id"] = FEATURE_PAYLOAD["away_team_id"]
    f = FEATURE_PAYLOAD["features"]
    swapped["features"] = {
        "away_offense_ppg": f["home_offense_ppg"],
        "away_defense_papg": f["home_defense_papg"],
        "away_recent6_pf_pg": f["home_recent6_pf_pg"],
        "away_recent6_pa_pg": f["home_recent6_pa_pg"],
        "home_offense_ppg": f["away_offense_ppg"],
        "home_defense_papg": f["away_defense_papg"],
        "home_recent6_pf_pg": f["away_recent6_pf_pg"],
        "home_recent6_pa_pg": f["away_recent6_pa_pg"],
        "neutral_site": False,
    }
    out = projection.project_game_total(swapped)
    assert out["projected_total"] == pytest.approx(original["projected_total"])
    assert out["projected_away_points"] == pytest.approx(original["projected_home_points"])
    assert out["projected_home_points"] == pytest.approx(original["projected_away_points"])
