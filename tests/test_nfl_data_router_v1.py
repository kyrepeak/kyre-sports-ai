from __future__ import annotations

import pandas as pd

import sports_api.nfl_data_espn_fallback_v1 as espn
import sports_api.nfl_game_totals_environment_context_v1 as environment
import sports_api.nfl_game_totals_scoring_context_v1 as scoring
from sports_api.nfl_data_router_v1 import (
    clear_router_caches,
    register_cache_clearer,
    route_metric,
)
from sports_api.nfl_game_totals_total_projection_v1 import build_total_projection


def test_router_falls_back_after_primary_transport_failure():
    def primary(request):
        return {"ready": False, "provider": "primary", "diagnostics": ["403"]}

    def secondary(request):
        return {
            "ready": True,
            "provider": "secondary",
            "data": {
                "plays_per_game": 65.0,
                "possession_seconds_per_game": 1812.0,
            },
            "fields_verified": [
                "plays_per_game",
                "possession_seconds_per_game",
            ],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {"team_abbr": "BUF"}, (primary, secondary))

    assert result["ready"] is True
    assert result["provider_used"] == "secondary"
    assert result["fallback_rank"] == 2
    assert result["provider_attempts"][0]["provider"] == "primary"
    assert result["provider_attempts"][0]["accepted"] is False


def test_router_rejects_invalid_metric_shape_instead_of_guessing():
    def bad(request):
        return {
            "ready": True,
            "provider": "bad",
            "data": {
                "plays_per_game": -4.0,
                "possession_seconds_per_game": 99999.0,
            },
            "fields_verified": [
                "plays_per_game",
                "possession_seconds_per_game",
            ],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {"team_abbr": "BUF"}, (bad,))

    assert result["ready"] is False
    assert result["provider_used"] == ""
    assert any("range" in item.lower() for item in result["diagnostics"])


def test_router_rejects_low_quality_result_for_projection_use():
    def low_quality(request):
        return {
            "ready": True,
            "provider": "weak",
            "data": {
                "plays_per_game": 64.0,
                "possession_seconds_per_game": 1800.0,
            },
            "fields_verified": [
                "plays_per_game",
                "possession_seconds_per_game",
            ],
            "quality": "LOW",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {"team_abbr": "BUF"}, (low_quality,))

    assert result["ready"] is False
    assert result["provider_used"] == ""
    assert any("quality" in item.lower() for item in result["diagnostics"])


def test_router_all_providers_fail_closed_with_attempt_history():
    def timeout(request):
        raise TimeoutError("provider timeout")

    def unavailable(request):
        return {
            "ready": False,
            "provider": "backup",
            "diagnostics": ["schema drift"],
        }

    result = route_metric(
        "explosive",
        {"team_abbr": "BUF"},
        (timeout, unavailable),
    )

    assert result["ready"] is False
    assert result["provider_used"] == ""
    assert result["fallback_rank"] == 0
    assert len(result["provider_attempts"]) == 2
    assert any("timeout" in item.lower() for item in result["diagnostics"])
    assert any("schema drift" in item.lower() for item in result["diagnostics"])


def test_router_cache_registry_clears_only_registered_functions():
    calls: list[str] = []

    register_cache_clearer("nflverse", lambda: calls.append("nflverse"))
    register_cache_clearer("nws", lambda: calls.append("nws"))

    cleared = clear_router_caches()

    assert cleared == ["nflverse", "nws"]
    assert calls == ["nflverse", "nws"]


def test_espn_fallback_adapter_exposes_all_router_provider_functions():
    for name in (
        "fetch_scoring_games",
        "fetch_pace",
        "fetch_explosive",
        "fetch_red_zone_drive",
        "fetch_environment",
    ):
        assert callable(getattr(espn, name))


def test_espn_403_is_recoverable_when_primary_provider_is_valid():
    def nws_provider(request):
        return {
            "ready": True,
            "provider": "NWS",
            "data": {
                "venue_name": "Lincoln Financial Field",
                "indoor": False,
                "temperature": 72.0,
                "precipitation": 20.0,
                "gust": 12.0,
            },
            "fields_verified": [
                "venue_name",
                "indoor",
                "temperature",
                "precipitation",
                "gust",
            ],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    def espn_403(request):
        return {
            "ready": False,
            "provider": "ESPN NFL fallback",
            "diagnostics": ["403 Client Error: Forbidden"],
        }

    result = route_metric("environment", {}, (nws_provider, espn_403))

    assert result["ready"] is True
    assert result["provider_used"] == "NWS"
    assert result["fallback_rank"] == 1
    assert len(result["provider_attempts"]) == 1


def test_espn_can_win_only_after_primary_fails_validation():
    def broken_nflverse(request):
        return {
            "ready": True,
            "provider": "nflverse",
            "data": {
                "plays_per_game": -1.0,
                "possession_seconds_per_game": 1800.0,
            },
            "fields_verified": ["plays_per_game", "possession_seconds_per_game"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    def valid_espn(request):
        return {
            "ready": True,
            "provider": "ESPN NFL team statistics",
            "data": {
                "plays_per_game": 64.0,
                "possession_seconds_per_game": 1810.0,
            },
            "fields_verified": ["plays_per_game", "possession_seconds_per_game"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {}, (broken_nflverse, valid_espn))

    assert result["ready"] is True
    assert result["provider_used"].startswith("ESPN")
    assert result["fallback_rank"] == 2
    assert result["provider_attempts"][0]["accepted"] is False


def test_espn_pace_adapter_normalizes_exact_existing_fields_without_projection_math():
    payload = {
        "results": {
            "stats": {
                "categories": [
                    {
                        "name": "general",
                        "stats": [
                            {"name": "totalOffensivePlays", "perGameValue": 65.5},
                            {"name": "possessionTimeSeconds", "perGameValue": 1812.0},
                        ],
                    }
                ]
            }
        }
    }

    result = espn.fetch_pace(
        {"team_abbr": "BUF", "season": 2026},
        get_json=lambda url, params=None: payload,
    )

    assert result["ready"] is True
    assert result["provider"].startswith("ESPN")
    assert result["data"]["plays_per_game"] == 65.5
    assert result["data"]["possession_seconds_per_game"] == 1812.0
    assert "projection" not in " ".join(result.keys()).lower()


def test_forced_primary_failures_use_certified_fallback_and_all_failures_block_projection(monkeypatch):
    def primary_transport_failure(request):
        raise TimeoutError("forced primary transport failure")

    def espn_scoring_fallback(request):
        season = int(request["season"])
        team = str(request["team_abbr"])
        games = [
            {
                "date": f"{season}-09-{index:02d}",
                "pf": 24.0 + (1.0 if team == "BUF" else 0.0),
                "pa": 21.0,
                "opponent_abbr": "OPP",
            }
            for index in range(1, 17)
        ]
        return {
            "ready": True,
            "provider": "ESPN NFL scoring fallback",
            "data": {"games": games},
            "fields_verified": ["date", "pf", "pa", "opponent_abbr"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    monkeypatch.setattr(scoring.nflverse, "fetch_scoring_games", primary_transport_failure)
    monkeypatch.setattr(scoring.espn, "fetch_scoring_games", espn_scoring_fallback)

    scoring_context = scoring.build_matchup_scoring_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    assert scoring_context["ready"] is True
    assert scoring_context["provenance"]["away"]["prior"]["fallback_rank"] == 2
    assert scoring_context["provenance"]["home"]["current"]["fallback_rank"] == 2

    monkeypatch.setattr(
        environment,
        "load_nfl_slate",
        lambda day: (
            pd.DataFrame(
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
            ),
            {"request_ok": True, "games": 1},
        ),
    )
    monkeypatch.setattr(environment.nws, "fetch_environment", primary_transport_failure)

    def espn_environment_fallback(request):
        return {
            "ready": True,
            "provider": "ESPN NFL environment fallback",
            "data": {
                "venue_name": "Highmark Stadium",
                "indoor": False,
                "temperature": 61.0,
                "precipitation": 20.0,
                "gust": 14.0,
            },
            "fields_verified": [
                "venue_name",
                "indoor",
                "temperature",
                "precipitation",
                "gust",
            ],
            "quality": "HIGH",
            "data_freshness": "2026-09-20T17:00:00Z",
            "diagnostics": [],
        }

    monkeypatch.setattr(environment.espn, "fetch_environment", espn_environment_fallback)
    environment_context = environment.build_slate_environment_context(
        "2026-09-20", ["event-1"]
    )["event-1"]
    assert environment_context["ready"] is True
    assert environment_context["provenance"]["fallback_rank"] == 2
    assert environment_context["provider"].startswith("ESPN")

    def unavailable_fallback(request):
        return {
            "ready": False,
            "provider": "ESPN NFL fallback",
            "diagnostics": ["forced fallback failure"],
        }

    monkeypatch.setattr(scoring.espn, "fetch_scoring_games", unavailable_fallback)
    monkeypatch.setattr(environment.espn, "fetch_environment", unavailable_fallback)

    failed_scoring = scoring.build_matchup_scoring_context(
        "BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20"
    )
    failed_environment = environment.build_slate_environment_context(
        "2026-09-20", ["event-1"]
    )["event-1"]
    assert failed_scoring["ready"] is False
    assert failed_environment["ready"] is False

    projection = build_total_projection(
        failed_scoring,
        {"ready": True, "matchup": {"average_plays_per_game": 65.0}},
        {"ready": True, "matchup": {"average_explosive_plays_per_game": 3.5}},
        {
            "ready": True,
            "matchup": {
                "average_red_zone_td_pct": 55.0,
                "average_third_down_conv_pct": 42.0,
                "average_first_downs_per_game": 22.0,
            },
        },
        failed_environment,
    )
    assert projection["ready"] is False
    assert projection["projected_total"] is None
    assert projection["sportsbook_projection_weight"] == 0.0
