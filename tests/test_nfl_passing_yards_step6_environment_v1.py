from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_environment_v1 as environment


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step6_parses_explicit_espn_play_volume_and_pass_rate() -> None:
    payload = {
        "splits": {"categories": [{"name": "offensive", "stats": [
            {"name": "gamesPlayed", "value": 2},
            {"name": "totalOffensivePlays", "value": 130},
            {"name": "passingAttempts", "value": 78},
            {"name": "rushingAttempts", "value": 52},
        ]}]}
    }
    out = environment.parse_team_pace(payload)
    assert out["ready"] is True
    assert out["offensive_plays_per_game"] == 65.0
    assert out["pass_attempts_per_game"] == 39.0
    assert out["rush_attempts_per_game"] == 26.0
    assert out["pass_rate"] == 60.0
    assert out["plays_state"] == "VERIFIED ESPN TEAM STAT"
    assert environment.pass_tendency_label(out)[0] == "PASS-LEAN"


def test_step6_does_not_reconstruct_official_plays_when_play_field_missing() -> None:
    payload = {
        "splits": {"categories": [{"name": "offensive", "stats": [
            {"name": "gamesPlayed", "value": 2},
            {"name": "passingAttempts", "value": 70},
            {"name": "rushingAttempts", "value": 50},
        ]}]}
    }
    out = environment.parse_team_pace(payload)
    assert out["ready"] is True
    assert out["offensive_plays_per_game"] != out["offensive_plays_per_game"]
    assert out["pass_rate"] != out["pass_rate"]
    assert out["plays_state"].startswith("UNAVAILABLE")


def test_step6_parses_verified_indoor_venue_weather_and_neutral_site() -> None:
    summary = {
        "gameInfo": {
            "venue": {
                "fullName": "Test Dome",
                "indoor": True,
                "grass": False,
                "address": {"city": "Test City", "state": "TX"},
            },
            "weather": {"temperature": 72, "displayValue": "Clear", "windSpeed": "8 mph"},
        },
        "header": {"competitions": [{"neutralSite": True}]},
    }
    out = environment.parse_game_environment(summary)
    assert out["venue"] == "Test Dome"
    assert out["venue_type"] == "INDOOR"
    assert out["surface"] == "TURF"
    assert out["neutral_site"] is True
    assert out["temperature_f"] == 72.0
    assert out["wind_mph"] == 8.0
    assert environment.weather_label(out)[0] == "CONTROLLED"


def test_step6_rest_context_uses_most_recent_completed_event_only() -> None:
    schedule = {"events": [
        {"id": "100", "date": "2026-09-01T17:00:00Z", "competitions": [{"status": {"type": {"completed": True, "state": "post"}}}]},
        {"id": "101", "date": "2026-09-07T17:00:00Z", "competitions": [{"status": {"type": {"completed": True, "state": "post"}}}]},
        {"id": "102", "date": "2026-09-14T17:00:00Z", "competitions": [{"status": {"type": {"completed": False, "state": "pre"}}}]},
    ]}
    out = environment.rest_context(schedule, "2026-09-12")
    assert out["ready"] is True
    assert out["previous_game_date"] == "2026-09-07"
    assert out["turnaround_days"] == 5
    assert out["rest_label"] == "SHORT"


def test_step6_weather_watch_threshold_is_descriptive_only() -> None:
    env = {
        "indoor": False,
        "weather_available": True,
        "weather_condition": "Rain",
        "temperature_f": 54,
        "wind_mph": 22,
        "wind_gust_mph": 28,
        "precipitation_pct": 40,
    }
    label, reason = environment.weather_label(env)
    assert label == "WATCH"
    assert "notable condition" in reason


def test_step6_invalid_event_identity_fails_closed_and_keeps_zero_influence() -> None:
    out = environment.build_game_environment(
        {"game_id": "synthetic-game"},
        {"team_id": "11"},
        {"team_id": "34"},
        2026,
        2,
        "2026-09-12",
    )
    assert out["ready"] is False
    assert "official ESPN event ID" in out["reason"]
    assert out["projection_adjustment"] == 0.0


def test_router_v86_advances_only_passing_yards_step6() -> None:
    hub = _read("nfl_hub_v25.py")
    router = _read("streamlit_memory_lazy_router_v86.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v7.py")
    engine = _read("nfl_passing_yards_environment_v1.py")

    assert "import nfl_hub_v24 as base" in hub
    assert "nfl_passing_yards_hub_v7" in hub
    assert "import streamlit_memory_lazy_router_v85 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v25"' in router
    assert "streamlit_memory_lazy_router_v86" in app
    assert "STREAMLIT_MAIN_V85_NFL_PASSING_YARDS_STEP5_PERSONNEL_2026-09-11" in app
    assert "STREAMLIT_MAIN_V86_NFL_PASSING_YARDS_STEP6_ENVIRONMENT_2026-09-11" in app
    assert "STEP 6 ENVIRONMENT GREEN" in page
    assert "Steps 4–6 projection influence 0.0%" in page
    assert "sportsbook influence 0.0%" in page
    assert "does not fabricate mileage or time-zone effects" in page
    assert '"projection_adjustment": 0.0' in engine
    assert '"sportsbook_influence": 0.0' in engine
    assert "fail closed" in engine.lower()
