from __future__ import annotations

import inspect

import sports_api.nfl_game_totals_pace_context_v1 as pace
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
