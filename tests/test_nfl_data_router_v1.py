from __future__ import annotations

from sports_api.nfl_data_router_v1 import (
    clear_router_caches,
    register_cache_clearer,
    route_metric,
)


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
