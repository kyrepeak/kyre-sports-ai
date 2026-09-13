from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import time

from fastapi import HTTPException

from sports_api.api import nfl_rushing_yards_context_v1 as route


def _payload(event_id: str = "401872925", *, ready: bool = True, marker: int = 1) -> dict:
    return {
        "schema_version": "nfl_rushing_yards_context_v1",
        "ready": ready,
        "official_event_id": event_id,
        "captured_at_utc": f"2026-09-13T05:00:{marker:02d}+00:00",
        "official_authority": "ESPN",
        "season": 2026,
        "teams": [
            {
                "official_team_id": "27",
                "opponent_official_team_id": "4",
                "team_name": "Tampa Bay Buccaneers",
                "team_abbreviation": "TB",
                "players": [
                    {
                        "official_event_id": event_id,
                        "official_team_id": "27",
                        "official_athlete_id": "100",
                        "player_name": "Runner One",
                    }
                ],
            },
            {
                "official_team_id": "4",
                "opponent_official_team_id": "27",
                "team_name": "Cincinnati Bengals",
                "team_abbreviation": "CIN",
                "players": [
                    {
                        "official_event_id": event_id,
                        "official_team_id": "4",
                        "official_athlete_id": "200",
                        "player_name": "Runner Two",
                    }
                ],
            },
        ],
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def test_exact_event_snapshot_reuses_successful_payload(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = 0

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", fake_collect)
    first = route._collect_or_reuse_context("401872925")
    second = route._collect_or_reuse_context("401872925")
    third = route._collect_or_reuse_context("401872925")

    assert calls == 1
    assert first == second == third
    assert first is not second and second is not third
    assert first["captured_at_utc"] == "2026-09-13T05:00:01+00:00"


def test_snapshot_expiry_forces_fresh_collection(monkeypatch):
    route._clear_context_snapshot_cache()
    clock = [100.0]
    calls = 0

    monkeypatch.setattr(route, "monotonic", lambda: clock[0])

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", fake_collect)

    first = route._collect_or_reuse_context("401872925")
    clock[0] = 159.9
    second = route._collect_or_reuse_context("401872925")
    assert calls == 1
    assert second["captured_at_utc"] == first["captured_at_utc"]

    clock[0] = 160.01
    third = route._collect_or_reuse_context("401872925")
    assert calls == 2
    assert third["captured_at_utc"] != first["captured_at_utc"]


def test_non_ready_payload_is_not_cached(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = 0

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _payload(event_id, ready=False, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", fake_collect)
    route._collect_or_reuse_context("401872925")
    route._collect_or_reuse_context("401872925")
    assert calls == 2


def test_snapshot_returns_deep_copies(monkeypatch):
    route._clear_context_snapshot_cache()
    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", lambda event_id: _payload(event_id))

    first = route._collect_or_reuse_context("401872925")
    first["teams"][0]["team_name"] = "MUTATED"
    first["semantics"]["sportsbook_influence"] = 99.0

    second = route._collect_or_reuse_context("401872925")
    assert second["teams"][0]["team_name"] == "Tampa Bay Buccaneers"
    assert second["semantics"]["sportsbook_influence"] == 0.0


def test_cached_payload_is_revalidated_and_fails_closed(monkeypatch):
    route._clear_context_snapshot_cache()
    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", lambda event_id: _payload(event_id))
    route._collect_or_reuse_context("401872925")

    with route._CACHE_LOCK:
        expires_at, collector_id, cached = route._CONTEXT_SNAPSHOT_CACHE["401872925"]
        weakened = deepcopy(cached)
        weakened["semantics"]["market_enabled"] = True
        route._CONTEXT_SNAPSHOT_CACHE["401872925"] = (expires_at, collector_id, weakened)

    try:
        route._collect_or_reuse_context("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "safety contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("weakened cached payload did not fail closed")


def test_same_event_concurrent_requests_single_flight(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = 0
    calls_lock = threading.Lock()

    def fake_collect(event_id: str):
        nonlocal calls
        with calls_lock:
            calls += 1
            marker = calls
        time.sleep(0.08)
        return _payload(event_id, marker=marker)

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", fake_collect)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: route._collect_or_reuse_context("401872925"), range(6)))

    assert calls == 1
    assert all(row["captured_at_utc"] == "2026-09-13T05:00:01+00:00" for row in results)


def test_collector_swap_invalidates_existing_snapshot(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = {"a": 0, "b": 0}

    def collector_a(event_id: str):
        calls["a"] += 1
        return _payload(event_id, marker=1)

    def collector_b(event_id: str):
        calls["b"] += 1
        return _payload(event_id, marker=2)

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", collector_a)
    first = route._collect_or_reuse_context("401872925")

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", collector_b)
    second = route._collect_or_reuse_context("401872925")

    assert calls == {"a": 1, "b": 1}
    assert first["captured_at_utc"] != second["captured_at_utc"]


def test_cache_contract_is_short_exact_event_and_market_blind():
    assert route.CONTEXT_SNAPSHOT_TTL_SECONDS == 60.0
    assert route.CONTRACT["official_event_id_required"] is True
    assert route.CONTRACT["player_name_matching"] is False
    assert route.CONTRACT["fuzzy_matching"] is False
    assert route.CONTRACT["synthetic_event_ids"] is False
    assert route.CONTRACT["synthetic_player_ids"] is False
    assert route.CONTRACT["projection_enabled"] is False
    assert route.CONTRACT["market_enabled"] is False
    assert route.CONTRACT["sportsbook_influence"] == 0.0
