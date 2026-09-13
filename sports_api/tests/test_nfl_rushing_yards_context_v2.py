from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api import nfl_rushing_yards_context_v2 as route
from sports_api.collectors import nfl_rushing_yards_context_v1 as frozen
from sports_api.collectors import nfl_rushing_yards_context_v2 as fast


def _pregame():
    return {
        "header": {
            "id": "401900001",
            "season": {"year": 2026, "type": 2},
            "competitions": [{
                "competitors": [
                    {"homeAway": "away", "team": {"id": "27", "displayName": "Tampa Bay Buccaneers", "abbreviation": "TB"}},
                    {"homeAway": "home", "team": {"id": "4", "displayName": "Cincinnati Bengals", "abbreviation": "CIN"}},
                ]
            }],
        }
    }


def _old_game(team_id: str, opponent_id: str, athlete_id: str, name: str, attempts: str, yards: str):
    return {
        "header": {"competitions": [{"competitors": [{"team": {"id": team_id}}, {"team": {"id": opponent_id}}]}]},
        "boxscore": {
            "players": [{
                "team": {"id": team_id},
                "statistics": [{
                    "name": "rushing",
                    "labels": ["CAR", "YDS", "AVG", "TD", "LONG"],
                    "athletes": [{"athlete": {"id": athlete_id, "displayName": name}, "stats": [attempts, yards, "4.5", "1", "18"]}],
                }],
            }],
            "teams": [
                {"team": {"id": team_id}, "statistics": [
                    {"name": "rushingAttempts", "displayValue": attempts},
                    {"name": "rushingYards", "displayValue": yards},
                    {"name": "rushingTouchdowns", "displayValue": "1"},
                ]},
                {"team": {"id": opponent_id}, "statistics": [
                    {"name": "rushingAttempts", "displayValue": "24"},
                    {"name": "rushingYards", "displayValue": "108"},
                    {"name": "rushingTouchdowns", "displayValue": "1"},
                ]},
            ],
        },
    }


def _schedule_event(event_id: str, year: int):
    return {
        "id": event_id,
        "date": f"{year}-12-01T18:00Z",
        "season": {"year": year, "displayName": str(year)},
        "seasonType": {"id": "2", "type": 2, "name": "Regular Season"},
        "competitions": [{"status": {"type": {"state": "post", "completed": True}}}],
    }


def _fake_espn(calls: list[tuple[str, dict]]):
    old27 = _old_game("27", "1", "100", "Runner One", "20", "100")
    old4 = _old_game("4", "2", "200", "Runner Two", "18", "81")

    def fake_get(url, params=None):
        params = dict(params or {})
        calls.append((url, params))
        if url.endswith("/summary"):
            event = str(params.get("event") or "")
            if event == "401900001":
                return _pregame()
            if event == "90027":
                return old27
            if event == "90004":
                return old4
        if url.endswith("/teams/27/roster"):
            return {"athletes": [{"items": [{"id": "100", "displayName": "Runner One", "position": {"abbreviation": "RB"}}]}]}
        if url.endswith("/teams/4/roster"):
            return {"athletes": [{"items": [{"id": "200", "displayName": "Runner Two", "position": {"abbreviation": "RB"}}]}]}
        if "/schedule" in url:
            assert int(params.get("seasontype") or 0) == 2
            team = url.split("/teams/", 1)[1].split("/", 1)[0]
            season = int(params.get("season") or 0)
            if season == 2026:
                return {"season": {"year": 2026}, "events": []}
            event_id = "90027" if team == "27" else "90004"
            return {
                "season": {"year": 2026, "type": 2},
                "requestedSeason": {"year": 2025},
                "events": [_schedule_event(event_id, 2025)],
            }
        raise AssertionError(f"unexpected ESPN call: {url} {params}")

    return fake_get


def _without_capture(payload: dict) -> dict:
    out = deepcopy(payload)
    out.pop("captured_at_utc", None)
    return out


def test_fast_collector_is_payload_equivalent_to_frozen_v1(monkeypatch):
    v1_calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(frozen, "_get_json", _fake_espn(v1_calls))
    expected = frozen.collect_nfl_rushing_yards_context("401900001")

    v2_calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(frozen, "_get_json", _fake_espn(v2_calls))
    actual = fast.collect_nfl_rushing_yards_context_fast("401900001")

    assert _without_capture(actual) == _without_capture(expected)
    assert actual["schema_version"] == "nfl_rushing_yards_context_v1"
    assert actual["semantics"]["sportsbook_influence"] == 0.0
    assert actual["identity"]["fuzzy_matching"] is False


def test_fast_collector_deduplicates_team_schedule_reads(monkeypatch):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(frozen, "_get_json", _fake_espn(calls))
    payload = fast.collect_nfl_rushing_yards_context_fast("401900001")
    assert payload["ready"] is True

    schedule_calls = [(url, params) for url, params in calls if "/schedule" in url]
    summary_calls = [(url, params) for url, params in calls if url.endswith("/summary")]
    roster_calls = [(url, params) for url, params in calls if url.endswith("/roster")]
    assert len(schedule_calls) == 4
    assert len(summary_calls) == 3
    assert len(roster_calls) == 2
    assert len(calls) == 9


def test_fast_collector_keeps_bounded_concurrency_contract():
    source = __import__("inspect").getsource(fast)
    assert "ThreadPoolExecutor" in source
    assert "MAX_IO_WORKERS = 6" in source
    assert "max_workers=4" in source
    assert "frozen._roster" in source
    assert "frozen._baseline_game_ids" in source
    assert "frozen._rushing_rows" in source
    assert "frozen._team_stat_map" in source


def test_fast_route_preserves_v1_schema_and_safety(monkeypatch):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(frozen, "_get_json", _fake_espn(calls))
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get(
        "/api/v1/nfl/rushing-yards/fast",
        params={"event_id": "401900001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "nfl_rushing_yards_context_v1"
    assert body["official_event_id"] == "401900001"
    assert body["semantics"] == {
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }
    assert response.headers["x-kyre-rushing-context"] == "v2-fast"
    assert response.headers["server-timing"].startswith("rushing-context-v2;dur=")


def test_fast_status_is_additive_and_v1_contract_remains_frozen():
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/v1/nfl/rushing-yards/fast/status")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "nfl_rushing_yards_context_v1"
    assert body["frozen_payload_contract"] == "nfl_rushing_yards_context_v1"
    assert body["performance_only"] is True
    assert body["sportsbook_influence"] == 0.0
    assert body["model_enabled"] is False
    assert body["projection_enabled"] is False
    assert body["market_enabled"] is False
