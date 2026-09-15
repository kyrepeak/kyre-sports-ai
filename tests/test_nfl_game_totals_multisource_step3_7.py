from __future__ import annotations

import inspect

import sports_api.nfl_game_totals_explosive_context_v1 as explosive
import sports_api.nfl_game_totals_pace_context_v1 as pace
import sports_api.nfl_game_totals_red_zone_drive_context_v1 as redzone
import sports_api.nfl_game_totals_scoring_context_v1 as scoring


def _scoring_games(season: int, team: str, count: int) -> list[dict]:
    games = []
    for index in range(count):
        games.append(
            {
                "date": f"{season}-10-{(index % 20) + 1:02d}",
                "pf": 24.0 + (1.0 if team == "BUF" else 0.0),
                "pa": 20.0 + (1.0 if team == "MIA" else 0.0),
                "opponent_abbr": "OPP",
            }
        )
    return games


def test_step3_router_result_preserves_projection_fields_and_blending(monkeypatch):
    calls: list[tuple[str, int, str]] = []

    def fake_scoring_route(team_abbr: str, season: int, cutoff_day: str):
        calls.append((team_abbr, season, cutoff_day))
        count = 16 if season == 2025 else 1
        return {
            "ready": True,
            "metric": "scoring_games",
            "data": {"games": _scoring_games(season, team_abbr, count)},
            "provider_used": "nflverse",
            "fallback_rank": 1,
            "data_freshness": cutoff_day,
            "fields_verified": ["date", "pf", "pa", "opponent_abbr"],
            "quality": "HIGH",
            "diagnostics": [],
            "provider_attempts": [
                {"provider": "nflverse", "rank": 1, "accepted": True, "diagnostics": []}
            ],
        }

    monkeypatch.setattr(scoring, "route_scoring_games", fake_scoring_route)

    result = scoring.build_matchup_scoring_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
    )

    assert result["ready"] is True
    assert set(result["away"]) >= {
        "offense_ppg",
        "opponent_defense_papg",
        "signal",
        "quality",
    }
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["current"]["provider_used"] == "nflverse"
    assert result["provenance"]["home"]["prior"]["fallback_rank"] == 1
    assert len(calls) == 4


def test_step3_provider_failure_stays_fail_closed(monkeypatch):
    def unavailable_route(team_abbr: str, season: int, cutoff_day: str):
        return {
            "ready": False,
            "metric": "scoring_games",
            "data": {},
            "provider_used": "",
            "fallback_rank": 0,
            "data_freshness": "",
            "fields_verified": [],
            "quality": "UNAVAILABLE",
            "diagnostics": ["all certified providers failed"],
            "provider_attempts": [],
        }

    monkeypatch.setattr(scoring, "route_scoring_games", unavailable_route)
    result = scoring.build_matchup_scoring_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
    )

    assert result["ready"] is False
    assert result["sportsbook_projection_weight"] == 0.0


def test_step4_router_result_preserves_projection_fields_and_provenance(monkeypatch):
    def fake_pace_route(team_abbr: str, season: int):
        return {
            "ready": True,
            "metric": "pace",
            "data": {
                "games_played": 2,
                "plays_per_game": 66.0 if team_abbr == "BUF" else 64.0,
                "possession_seconds_per_game": 1820.0,
            },
            "provider_used": "nflverse",
            "fallback_rank": 1,
            "data_freshness": "2026-09-15T22:00:00Z",
            "fields_verified": [
                "plays_per_game",
                "possession_seconds_per_game",
            ],
            "quality": "HIGH",
            "diagnostics": [],
            "provider_attempts": [
                {"provider": "nflverse", "rank": 1, "accepted": True, "diagnostics": []}
            ],
        }

    monkeypatch.setattr(pace, "route_pace", fake_pace_route)
    result = pace.build_matchup_pace_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
    )

    assert result["ready"] is True
    assert result["matchup"]["average_plays_per_game"] == 65.0
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["provider_used"] == "nflverse"
    assert result["provenance"]["home"]["fallback_rank"] == 1


def test_step4_router_can_preserve_valid_espn_fallback_without_direct_http(monkeypatch):
    def fallback_route(team_abbr: str, season: int):
        return {
            "ready": True,
            "metric": "pace",
            "data": {
                "plays_per_game": 64.0,
                "possession_seconds_per_game": 1800.0,
            },
            "provider_used": "ESPN NFL team statistics",
            "fallback_rank": 2,
            "data_freshness": "2026-09-15T22:00:00Z",
            "fields_verified": ["plays_per_game", "possession_seconds_per_game"],
            "quality": "HIGH",
            "diagnostics": ["nflverse unavailable"],
            "provider_attempts": [],
        }

    monkeypatch.setattr(pace, "route_pace", fallback_route)
    result = pace.build_matchup_pace_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
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
        return {
            "ready": True,
            "metric": "explosive",
            "data": {
                "games_played": 2,
                "rushing_big_plays": 3.0,
                "receiving_big_plays": 5.0,
                "total_big_plays": 8.0,
                "rushing_big_plays_per_game": 1.5,
                "receiving_big_plays_per_game": 2.5,
                "explosive_plays_per_game": rate,
            },
            "provider_used": "nflverse",
            "fallback_rank": 1,
            "data_freshness": "2026-09-15T22:00:00Z",
            "fields_verified": ["explosive_plays_per_game"],
            "quality": "HIGH",
            "diagnostics": [],
            "provider_attempts": [],
        }

    monkeypatch.setattr(explosive, "route_explosive", fake_explosive_route)
    result = explosive.build_matchup_explosive_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
    )

    assert result["ready"] is True
    assert result["matchup"]["average_explosive_plays_per_game"] == 3.5
    assert result["matchup"]["signal"] == "BALANCED"
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["provenance"]["away"]["provider_used"] == "nflverse"


def test_step6_router_preserves_existing_projection_fields_and_adds_real_drive_context(monkeypatch):
    def fake_red_zone_route(team_abbr: str, season: int):
        if team_abbr == "BUF":
            data = {
                "red_zone_td_pct": 60.0,
                "third_down_conv_pct": 45.0,
                "first_downs_per_game": 23.0,
                "drives_per_game": 11.0,
            }
        else:
            data = {
                "red_zone_td_pct": 50.0,
                "third_down_conv_pct": 40.0,
                "first_downs_per_game": 21.0,
                "drives_per_game": 9.0,
            }
        return {
            "ready": True,
            "metric": "red_zone_drive",
            "data": data,
            "provider_used": "nflverse",
            "fallback_rank": 1,
            "data_freshness": "2026-09-15T22:00:00Z",
            "fields_verified": list(data),
            "quality": "HIGH",
            "diagnostics": [],
            "provider_attempts": [],
        }

    monkeypatch.setattr(redzone, "route_red_zone_drive", fake_red_zone_route)
    result = redzone.build_matchup_red_zone_drive_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
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
        return {
            "ready": True,
            "metric": "red_zone_drive",
            "data": {
                "red_zone_td_pct": 52.0,
                "third_down_conv_pct": 41.0,
                "first_downs_per_game": 21.0,
            },
            "provider_used": "ESPN NFL team statistics",
            "fallback_rank": 2,
            "data_freshness": "2026-09-15T22:00:00Z",
            "fields_verified": [
                "red_zone_td_pct",
                "third_down_conv_pct",
                "first_downs_per_game",
            ],
            "quality": "HIGH",
            "diagnostics": ["nflverse unavailable"],
            "provider_attempts": [],
        }

    monkeypatch.setattr(redzone, "route_red_zone_drive", fallback_route)
    result = redzone.build_matchup_red_zone_drive_context(
        "BUF",
        "Buffalo Bills",
        "MIA",
        "Miami Dolphins",
        "2026-09-20",
    )

    assert result["ready"] is True
    assert result["drive_count_available"] is False
    assert "average_drives_per_game" not in result["matchup"]
    assert result["provenance"]["away"]["fallback_rank"] == 2


def test_step5_and_step6_provider_failure_stays_fail_closed(monkeypatch):
    def unavailable(*args):
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

    monkeypatch.setattr(explosive, "route_explosive", unavailable)
    monkeypatch.setattr(redzone, "route_red_zone_drive", unavailable)

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
