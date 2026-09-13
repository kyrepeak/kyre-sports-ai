from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import time

from fastapi import HTTPException

from sports_api.api import nfl_rushing_yards_market_v1 as route


def _payload(
    event_id: str = "401872925",
    *,
    ready: bool = True,
    market_available: bool = True,
    marker: int = 1,
) -> dict:
    return {
        "schema_version": "nfl_rushing_yards_market_v1",
        "ready": ready,
        "market_available": market_available,
        "official_event_id": event_id,
        "sportsbook": "FanDuel",
        "captured_at_utc": f"2026-09-13T05:30:{marker:02d}+00:00",
        "props": [
            {
                "official_event_id": event_id,
                "official_athlete_id": "4430807",
                "official_team_id": "4",
                "player_name": "Exact Runner",
                "position": "RB",
                "market_type": "rushing_yards",
                "line": 64.5,
                "over_odds": -110,
                "under_odds": -110,
                "sportsbook": "FanDuel",
                "line_status": "active",
            }
        ] if market_available else [],
        "identity": {
            "official_authority": "ESPN",
            "event_identity": "exact",
            "player_identity": "exact",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "probability_enabled": False,
            "fair_odds_enabled": False,
            "ev_enabled": False,
            "grading_enabled": False,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def test_active_exact_event_market_reuses_snapshot(monkeypatch):
    route._clear_market_snapshot_cache()
    calls = 0

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", fake_collect)
    first = route._collect_or_reuse_market("401872925")
    second = route._collect_or_reuse_market("401872925")
    third = route._collect_or_reuse_market("401872925")

    assert calls == 1
    assert first == second == third
    assert first is not second and second is not third
    assert first["captured_at_utc"] == "2026-09-13T05:30:01+00:00"


def test_market_snapshot_expires_after_ten_seconds(monkeypatch):
    route._clear_market_snapshot_cache()
    clock = [100.0]
    calls = 0
    monkeypatch.setattr(route, "monotonic", lambda: clock[0])

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", fake_collect)
    first = route._collect_or_reuse_market("401872925")
    clock[0] = 109.99
    second = route._collect_or_reuse_market("401872925")
    assert calls == 1
    assert second["captured_at_utc"] == first["captured_at_utc"]

    clock[0] = 110.01
    third = route._collect_or_reuse_market("401872925")
    assert calls == 2
    assert third["captured_at_utc"] != first["captured_at_utc"]


def test_unavailable_market_is_never_cached(monkeypatch):
    route._clear_market_snapshot_cache()
    calls = 0

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, market_available=False, marker=calls)

    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", fake_collect)
    route._collect_or_reuse_market("401872925")
    route._collect_or_reuse_market("401872925")
    assert calls == 2


def test_market_snapshot_returns_deep_copies(monkeypatch):
    route._clear_market_snapshot_cache()
    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: _payload(event_id))

    first = route._collect_or_reuse_market("401872925")
    first["props"][0]["line"] = 999.5
    first["market_semantics"]["projection_weight"] = 1.0

    second = route._collect_or_reuse_market("401872925")
    assert second["props"][0]["line"] == 64.5
    assert second["market_semantics"]["projection_weight"] == 0.0


def test_cached_market_is_revalidated_and_fails_closed(monkeypatch):
    route._clear_market_snapshot_cache()
    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: _payload(event_id))
    route._collect_or_reuse_market("401872925")

    with route._CACHE_LOCK:
        expires_at, collector_id, cached = route._MARKET_SNAPSHOT_CACHE["401872925"]
        weakened = deepcopy(cached)
        weakened["market_semantics"]["grading_enabled"] = True
        route._MARKET_SNAPSHOT_CACHE["401872925"] = (expires_at, collector_id, weakened)

    try:
        route._collect_or_reuse_market("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "safety contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("weakened cached market did not fail closed")


def test_cached_duplicate_athlete_market_fails_closed(monkeypatch):
    route._clear_market_snapshot_cache()
    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: _payload(event_id))
    route._collect_or_reuse_market("401872925")

    with route._CACHE_LOCK:
        expires_at, collector_id, cached = route._MARKET_SNAPSHOT_CACHE["401872925"]
        duplicated = deepcopy(cached)
        duplicated["props"].append(deepcopy(duplicated["props"][0]))
        route._MARKET_SNAPSHOT_CACHE["401872925"] = (expires_at, collector_id, duplicated)

    try:
        route._collect_or_reuse_market("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "row identity contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("duplicate cached athlete market did not fail closed")


def test_same_event_concurrent_market_requests_single_flight(monkeypatch):
    route._clear_market_snapshot_cache()
    calls = 0
    calls_lock = threading.Lock()

    def fake_collect(event_id: str):
        nonlocal calls
        with calls_lock:
            calls += 1
            marker = calls
        time.sleep(0.08)
        return _payload(event_id, marker=marker)

    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", fake_collect)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: route._collect_or_reuse_market("401872925"), range(6)))

    assert calls == 1
    assert all(row["captured_at_utc"] == "2026-09-13T05:30:01+00:00" for row in results)


def test_collector_swap_invalidates_existing_market_snapshot(monkeypatch):
    route._clear_market_snapshot_cache()
    calls = {"a": 0, "b": 0}

    def collector_a(event_id: str):
        calls["a"] += 1
        return _payload(event_id, marker=1)

    def collector_b(event_id: str):
        calls["b"] += 1
        return _payload(event_id, marker=2)

    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", collector_a)
    first = route._collect_or_reuse_market("401872925")
    monkeypatch.setattr(route, "collect_fanduel_nfl_rushing_yards_hosted", collector_b)
    second = route._collect_or_reuse_market("401872925")

    assert calls == {"a": 1, "b": 1}
    assert first["captured_at_utc"] != second["captured_at_utc"]


def test_market_cache_contract_is_short_exact_and_projection_blind():
    assert route.MARKET_SNAPSHOT_TTL_SECONDS == 10.0
    assert route.CONTRACT["official_event_id_required"] is True
    assert route.CONTRACT["player_name_matching"] is False
    assert route.CONTRACT["fuzzy_matching"] is False
    assert route.CONTRACT["synthetic_event_ids"] is False
    assert route.CONTRACT["synthetic_player_ids"] is False
    assert route.CONTRACT["projection_weight"] == 0.0
    assert route.CONTRACT["market_context_only"] is True
    assert route.CONTRACT["may_modify_projection"] is False
    assert route.CONTRACT["probability_enabled"] is False
    assert route.CONTRACT["grading_enabled"] is False
    assert route.CONTRACT["wager_actions"] is False
