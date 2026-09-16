from __future__ import annotations

import inspect

import pandas as pd

import sports_api.nfl_game_totals_environment_context_v1 as environment
import sports_api.nfl_game_totals_explosive_context_v1 as explosive
import sports_api.nfl_game_totals_pace_context_v1 as pace
import sports_api.nfl_game_totals_red_zone_drive_context_v1 as redzone
import sports_api.nfl_game_totals_scoring_context_v1 as scoring
from sports_api.nfl_game_totals_total_projection_v1 import build_total_projection


def _scoring_games(season: int, team: str, count: int) -> list[dict]:
    return [
        {
            "date": f"{season}-10-{(index % 20) + 1:02d}",
            "pf": 24.0 + (1.0 if team == "BUF" else 0.0),
            "pa": 20.0 + (1.0 if team == "MIA" else 0.0),
            "opponent_abbr": "OPP",
        }
        for index in range(count)
    ]


def _ready_route(metric: str, data: dict, provider: str = "nflverse", rank: int = 1) -> dict:
    return {
        "ready": True,
        "metric": metric,
        "data": data,
        "provider_used": provider,
        "fallback_rank": rank,
        "data_freshness": "2026-09-15T22:00:00Z",
        "fields_verified": list(data),
        "quality": "HIGH",
        "diagnostics": [],
        "provider_attempts": [],
    }


def _unavailable_route() -> dict:
    return {
        "ready": False,
        "data": {},
        "provider_used": "",
        "fallback_rank": 0,
        "data_freshness": "",
        "fields_verified": [],
        "quality": "UNAVAILABLE",
        "diagnostics": ["all certified providers failed"],
        "provider_attempts": [],
    }


def test_step3_router_result_preserves_projection_fields_and_blending(monkeypatch):
    calls: list[tuple[str, int, str]] = []

    def fake_scoring_route(team_abbr: str, season: int, cutoff_day: str):
        calls.append((team_abbr, season, cutoff_day))
        count = 16 if season == 2025 else 1
        return _ready_route(
            "scoring_games",
            {"games": _scoring_games(season, team_abbr, count)},
        )

    monkeypatch.setattr(scoring, "route_scoring_games", fake_scoring_route)

    result = scoring.build_matchup_scoring_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["away"]["offense_ppg"] == 25.0
    assert result["home"]["offense_ppg"] == 24.0
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["current"]["provider_used"] == "nflverse"
    assert result["provenance"]["home"]["prior"]["fallback_rank"] == 1
    assert len(calls) == 4


def test_step3_provider_failure_stays_fail_closed(monkeypatch):
    monkeypatch.setattr(scoring, "route_scoring_games", lambda *args: _unavailable_route())
    result = scoring.build_matchup_scoring_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is False
    assert result["sportsbook_projection_weight"] == 0.0


def test_step4_router_result_preserves_projection_fields_and_provenance(monkeypatch):
    def fake_pace_route(team_abbr: str, season: int):
        return _ready_route(
            "pace",
            {
                "games_played": 2,
                "plays_per_game": 66.0 if team_abbr == "BUF" else 64.0,
                "possession_seconds_per_game": 1820.0,
            },
        )

    monkeypatch.setattr(pace, "route_pace", fake_pace_route)
    result = pace.build_matchup_pace_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["matchup"]["average_plays_per_game"] == 65.0
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["provider_used"] == "nflverse"
    assert result["provenance"]["home"]["fallback_rank"] == 1


def test_step4_router_can_preserve_valid_espn_fallback_without_direct_http(monkeypatch):
    def fallback_route(team_abbr: str, season: int):
        return _ready_route(
            "pace",
            {
                "plays_per_game": 64.0,
                "possession_seconds_per_game": 1800.0,
            },
            provider="ESPN NFL team statistics",
            rank=2,
        )

    monkeypatch.setattr(pace, "route_pace", fallback_route)
    result = pace.build_matchup_pace_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["provenance"]["away"]["fallback_rank"] == 2
    assert result["provider"].startswith("MULTI-SOURCE")


def test_step3_and_step4_acquisition_no_longer_call_requests_directly():
    scoring_source = inspect.getsource(scoring)
    pace_source = inspect.getsource(pace)
    assert "requests.get(" not in scoring_source
    assert "requests.get(" not in pace_source
    assert "route_metric(" in scoring_source
    assert "route_metric(" in pace_source
    assert "nflverse.fetch_scoring_games" in scoring_source
    assert "espn.fetch_scoring_games" in scoring_source
    assert "nflverse.fetch_pace" in pace_source
    assert "espn.fetch_pace" in pace_source


def test_step5_router_result_preserves_explosive_projection_field_and_provenance(monkeypatch):
    def fake_explosive_route(team_abbr: str, season: int):
        rate = 4.0 if team_abbr == "BUF" else 3.0
        return _ready_route(
            "explosive",
            {
                "games_played": 2,
                "rushing_big_plays": 3.0,
                "receiving_big_plays": 5.0,
                "total_big_plays": 8.0,
                "rushing_big_plays_per_game": 1.5,
                "receiving_big_plays_per_game": 2.5,
                "explosive_plays_per_game": rate,
            },
        )

    monkeypatch.setattr(explosive, "route_explosive", fake_explosive_route)
    result = explosive.build_matchup_explosive_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["matchup"]["average_explosive_plays_per_game"] == 3.5
    assert result["matchup"]["signal"] == "BALANCED"
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["provider_used"] == "nflverse"


def test_step6_router_preserves_existing_projection_fields_and_adds_real_drive_context(monkeypatch):
    def fake_red_zone_route(team_abbr: str, season: int):
        data = {
            "red_zone_td_pct": 60.0 if team_abbr == "BUF" else 50.0,
            "third_down_conv_pct": 45.0 if team_abbr == "BUF" else 40.0,
            "first_downs_per_game": 23.0 if team_abbr == "BUF" else 21.0,
            "drives_per_game": 11.0 if team_abbr == "BUF" else 9.0,
        }
        return _ready_route("red_zone_drive", data)

    monkeypatch.setattr(redzone, "route_red_zone_drive", fake_red_zone_route)
    result = redzone.build_matchup_red_zone_drive_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["matchup"]["average_red_zone_td_pct"] == 55.0
    assert result["matchup"]["average_third_down_conv_pct"] == 42.5
    assert result["matchup"]["average_first_downs_per_game"] == 22.0
    assert result["drive_count_available"] is True
    assert result["matchup"]["average_drives_per_game"] == 10.0
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["home"]["provider_used"] == "nflverse"


def test_step6_espn_fallback_remains_ready_without_drive_count(monkeypatch):
    def fallback_route(team_abbr: str, season: int):
        return _ready_route(
            "red_zone_drive",
            {
                "red_zone_td_pct": 52.0,
                "third_down_conv_pct": 41.0,
                "first_downs_per_game": 21.0,
            },
            provider="ESPN NFL team statistics",
            rank=2,
        )

    monkeypatch.setattr(redzone, "route_red_zone_drive", fallback_route)
    result = redzone.build_matchup_red_zone_drive_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert result["ready"] is True
    assert result["drive_count_available"] is False
    assert "average_drives_per_game" not in result["matchup"]
    assert result["provenance"]["away"]["fallback_rank"] == 2


def test_step5_and_step6_provider_failure_stays_fail_closed(monkeypatch):
    monkeypatch.setattr(explosive, "route_explosive", lambda *args: _unavailable_route())
    monkeypatch.setattr(redzone, "route_red_zone_drive", lambda *args: _unavailable_route())
    explosive_result = explosive.build_matchup_explosive_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    redzone_result = redzone.build_matchup_red_zone_drive_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert explosive_result["ready"] is False
    assert redzone_result["ready"] is False


def test_step5_and_step6_acquisition_no_longer_call_requests_directly():
    explosive_source = inspect.getsource(explosive)
    redzone_source = inspect.getsource(redzone)
    assert "requests.get(" not in explosive_source
    assert "requests.get(" not in redzone_source
    assert "route_metric(" in explosive_source
    assert "route_metric(" in redzone_source
    assert "nflverse.fetch_explosive" in explosive_source
    assert "espn.fetch_explosive" in explosive_source
    assert "nflverse.fetch_red_zone_drive" in redzone_source
    assert "espn.fetch_red_zone_drive" in redzone_source


def _step7_slate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "event-1",
                "away_abbr": "MIA",
                "home_abbr": "BUF",
                "game_date": "2026-09-20",
                "tip_et": "1:00 PM ET",
                "venue": "Highmark Stadium",
            }
        ]
    )


def _step7_nws_result(*, indoor: bool = False) -> dict:
    data = {
        "venue_name": "Highmark Stadium",
        "indoor": indoor,
        "weather_applies": not indoor,
        "temperature": None if indoor else 61.0,
        "precipitation": None if indoor else 20.0,
        "gust": None if indoor else 14.0,
        "weather_pressure": "INDOOR" if indoor else "LOW",
    }
    return _ready_route("environment", data, provider="NWS + canonical NFL stadium registry", rank=1)


def test_step7_uses_nws_without_calling_espn_when_nws_is_valid(monkeypatch):
    monkeypatch.setattr(
        environment,
        "load_nfl_slate",
        lambda day: (_step7_slate(), {"request_ok": True, "error": ""}),
        raising=False,
    )
    calls: list[str] = []

    def primary(request: dict):
        calls.append("nws")
        data = _step7_nws_result()["data"]
        return {
            "ready": True,
            "provider": "NWS + canonical NFL stadium registry",
            "data": data,
            "fields_verified": ["venue_name", "indoor", "temperature", "precipitation", "gust"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    def forbidden_fallback(request: dict):
        calls.append("espn")
        raise AssertionError("ESPN fallback must not run when NWS is valid")

    monkeypatch.setattr(environment.nws, "fetch_environment", primary, raising=False)
    monkeypatch.setattr(environment.espn, "fetch_environment", forbidden_fallback, raising=False)
    result = environment.route_environment(
        {
            "event_id": "event-1",
            "day_str": "2026-09-20",
            "home_abbr": "BUF",
            "venue_name": "Highmark Stadium",
            "kickoff_utc": "2026-09-20T17:00:00Z",
        }
    )
    assert result["ready"] is True
    assert result["fallback_rank"] == 1
    assert calls == ["nws"]


def test_step7_indoor_result_neutralizes_weather_without_espn_fallback(monkeypatch):
    monkeypatch.setattr(
        environment,
        "load_nfl_slate",
        lambda day: (_step7_slate(), {"request_ok": True, "error": ""}),
        raising=False,
    )
    monkeypatch.setattr(environment, "route_environment", lambda request: _step7_nws_result(indoor=True), raising=False)
    result = environment.build_slate_environment_context("2026-09-20", ["event-1"])["event-1"]
    assert result["ready"] is True
    assert result["indoor"] is True
    assert result["weather_applies"] is False
    assert result["weather_pressure"] == "INDOOR"


def test_step7_all_providers_fail_closed(monkeypatch):
    monkeypatch.setattr(
        environment,
        "load_nfl_slate",
        lambda day: (_step7_slate(), {"request_ok": True, "error": ""}),
        raising=False,
    )
    monkeypatch.setattr(environment, "route_environment", lambda request: _unavailable_route(), raising=False)
    result = environment.build_slate_environment_context("2026-09-20", ["event-1"])["event-1"]
    assert result["ready"] is False
    assert result["weather_pressure"] == "UNAVAILABLE"
    assert result["sportsbook_projection_weight"] == 0.0


def test_step7_acquisition_no_longer_calls_requests_directly():
    source = inspect.getsource(environment)
    assert "requests.get(" not in source
    assert "route_metric(" in source
    assert "nws.fetch_environment" in source
    assert "espn.fetch_environment" in source


def test_step8_projection_signature_is_unchanged_and_market_free():
    sig = inspect.signature(build_total_projection)
    assert list(sig.parameters) == [
        "scoring_context",
        "pace_context",
        "explosive_context",
        "red_zone_drive_context",
        "environment_context",
    ]
    assert not any(
        token in str(sig).lower()
        for token in ("market", "odds", "fanduel", "sportsbook")
    )
