from pathlib import Path

import pytest

import mlb_matchup_environment_v1 as env
import mlb_matchup_player_v30 as step7


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _foundation():
    return {
        "player_id": 592450,
        "player_name": "Example Hitter",
        "team": "Away Club",
        "opponent": "Home Club",
        "game_pk": 123456,
        "season": 2026,
        "side": "away",
        "venue": "Example Park",
        "foundation_ready": True,
    }


def test_park_proxy_requires_minimum_split_sample():
    result = env.park_hit_proxy(
        {"atBats": 100, "hits": 30, "avg": ".300"},
        {"atBats": 100, "hits": 25, "avg": ".250"},
    )
    assert result["factor"] is None
    assert result["reliability"] == 0.0
    assert result["label"] == "PENDING PARK SAMPLE"


def test_park_proxy_shrinks_then_reaches_full_reliability():
    partial = env.park_hit_proxy(
        {"atBats": 500, "hits": 150, "avg": ".300"},
        {"atBats": 500, "hits": 125, "avg": ".250"},
    )
    full = env.park_hit_proxy(
        {"atBats": 900, "hits": 270, "avg": ".300"},
        {"atBats": 900, "hits": 225, "avg": ".250"},
    )
    assert 0.0 < partial["reliability"] < 1.0
    assert 1.0 < partial["factor"] < partial["raw_ratio"]
    assert full["reliability"] == pytest.approx(1.0)
    assert full["factor"] == pytest.approx(1.2)


def test_wind_parser_detects_out_in_and_crosswind():
    assert env.parse_wind("12 mph, Out To RF")["direction"] == "OUT"
    assert env.parse_wind("9 mph, In From CF")["direction"] == "IN"
    assert env.parse_wind("15 mph, L To R")["direction"] == "CROSS"
    assert env.parse_wind("12 mph, Out To RF")["mph"] == pytest.approx(12.0)


def test_indoor_roof_suppresses_weather_signal():
    result = env.weather_context(
        {"temp": 95, "condition": "Roof Closed", "wind": "20 mph, Out To CF"},
        "Retractable",
    )
    assert result["indoor"] is True
    assert result["signal"] == 0.0
    assert result["reliability"] == 1.0
    assert "SUPPRESSED" in result["label"]


def test_outdoor_weather_uses_temperature_and_wind_without_probability_math():
    hitter_friendly = env.weather_context(
        {"temp": 88, "condition": "Clear", "wind": "15 mph, Out To CF"},
        "Open",
    )
    suppressing = env.weather_context(
        {"temp": 48, "condition": "Cloudy", "wind": "15 mph, In From CF"},
        "Open",
    )
    assert hitter_friendly["signal"] > 0
    assert suppressing["signal"] < 0


def test_defense_context_treats_low_fielding_and_more_errors_as_hitter_friendly():
    soft = env.defense_context({"fielding": ".970", "errors": 70, "gamesPlayed": 100})
    strong = env.defense_context({"fielding": ".992", "errors": 25, "gamesPlayed": 100})
    assert soft["signal"] > 0
    assert strong["signal"] < 0
    assert soft["reliability"] == pytest.approx(1.0)


def test_field_dimensions_display_only_values_present_in_feed():
    result = env.field_dimensions(
        {"leftLine": "330 ft", "center": "400 ft", "rightLine": "325 ft"}
    )
    assert result["count"] == 3
    assert "LF line 330 ft" in result["summary"]
    assert "CF 400 ft" in result["summary"]
    assert "RF line 325 ft" in result["summary"]


def test_complete_environment_profile_builds_descriptive_context():
    payload = {
        "game_feed": {
            "gameData": {
                "venue": {
                    "id": 1,
                    "name": "Example Park",
                    "fieldInfo": {
                        "roofType": "Open",
                        "turfType": "Grass",
                        "leftLine": "330 ft",
                        "center": "400 ft",
                        "rightLine": "325 ft",
                    },
                },
                "weather": {
                    "temp": 86,
                    "condition": "Clear",
                    "wind": "12 mph, Out To RF",
                },
            }
        },
        "home_split": {"atBats": 950, "hits": 285, "avg": ".300"},
        "away_split": {"atBats": 950, "hits": 250, "avg": ".263"},
        "opponent_fielding": {"fielding": ".978", "errors": 60, "gamesPlayed": 110},
        "home_team_id": 10,
        "opponent_team_id": 10,
    }
    result = env.build_environment_profile(_foundation(), payload)
    assert result["park_factor_proxy"] > 1.0
    assert result["weather_signal"] > 0
    assert result["defense_fielding_pct"] == pytest.approx(0.978)
    assert result["dimension_count"] == 3
    assert result["environment_score"] is not None
    assert result["environment_score"] > 50
    assert 0 < result["environment_coverage"] <= 1.0
    assert result["environment_data_score"] > 0


def test_missing_inputs_fail_closed_without_inventing_environment_score():
    result = env.build_environment_profile(_foundation(), None)
    assert result["park_factor_proxy"] is None
    assert result["temperature"] is None
    assert result["defense_fielding_pct"] is None
    assert result["environment_score"] is None
    assert result["environment_coverage"] == 0.0


def test_step7_declares_zero_probability_impact():
    assert step7.PROBABILITY_IMPACT == "NONE"
    assert step7.STEP7_ROLE == "PARK_WEATHER_DEFENSE_CONTEXT_ONLY"
    source = _text("mlb_matchup_player_v30.py") + _text("mlb_matchup_environment_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup =",
        "p_two_plus =",
        "def fair_odds",
        "def monte_carlo",
    ):
        assert forbidden.lower() not in source.lower()


def test_steps_one_through_seven_accumulate_in_single_v2_panel():
    source = _text("mlb_matchup_player_v30.py")
    for renderer in (
        "step1._render_step1(games_df)",
        "step2._render_step2(games_df)",
        "step3._render_step3(games_df)",
        "step4._render_step4(games_df)",
        "step5._render_step5(games_df)",
        "step6._render_step6(games_df)",
        "_render_step7(games_df)",
    ):
        assert renderer in source
    assert "STEP 7 • PARK + WEATHER + DEFENSE" in source
    assert "frozen_detail.render_player_layer" in source


def test_hub_routes_to_step7_and_rankings_remain_frozen():
    hub = _text("mlb_matchup_hub_v36.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v30 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert "Steps 1-7 active" in hub
    assert "from mlb_matchup_hub_v36 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
