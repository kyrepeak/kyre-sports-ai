from __future__ import annotations

import io
import json
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from sports_api.api import nfl_rushing_yards_context_v1 as route
from sports_api.collectors import nfl_rushing_yards_context_v1 as collector


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


def _install_fake_espn(monkeypatch):
    old27 = _old_game("27", "1", "100", "Runner One", "20", "100")
    old4 = _old_game("4", "2", "200", "Runner Two", "18", "81")

    def fake_get(url, params=None):
        params = params or {}
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
            team = url.split("/teams/", 1)[1].split("/", 1)[0]
            season = int(params.get("season") or 0)
            if season == 2026:
                return {"events": []}
            event_id = "90027" if team == "27" else "90004"
            return {"events": [{
                "id": event_id,
                "date": "2025-12-01T18:00Z",
                "season": {"type": 2},
                "competitions": [{"status": {"type": {"state": "post"}}}],
            }]}
        raise AssertionError(f"unexpected ESPN call: {url} {params}")

    monkeypatch.setattr(collector, "_get_json", fake_get)


class _BytesResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit=None):
        return self._raw


def _http_error(url: str, code: int) -> HTTPError:
    return HTTPError(url, code, "transport failure", {}, io.BytesIO(b"{}"))


def test_get_json_primary_http_error_uses_same_path_and_query_on_alternate(monkeypatch):
    seen: list[str] = []
    event_id = "401872925"

    def fake_urlopen(request, timeout):
        assert timeout == collector.DEFAULT_TIMEOUT_SECONDS
        target = request.full_url
        seen.append(target)
        if len(seen) == 1:
            raise _http_error(target, 403)
        return _BytesResponse({"header": {"id": event_id}})

    monkeypatch.setattr(collector, "urlopen", fake_urlopen)
    payload = collector._get_json(
        f"{collector.ESPN_SITE_BASE}/summary",
        {"event": event_id},
    )

    assert payload["header"]["id"] == event_id
    assert len(seen) == 2
    assert seen[0] == f"{collector.ESPN_SITE_BASE}/summary?event={event_id}"
    assert seen[1] == f"{collector.ESPN_SITE_ALTERNATE_BASE}/summary?event={event_id}"
    assert seen[0].split("/summary", 1)[1] == seen[1].split("/summary", 1)[1]


def test_get_json_both_espn_transports_fail_closed_with_codes(monkeypatch):
    seen: list[str] = []

    def fake_urlopen(request, timeout):
        target = request.full_url
        seen.append(target)
        code = 403 if len(seen) == 1 else 429
        raise _http_error(target, code)

    monkeypatch.setattr(collector, "urlopen", fake_urlopen)
    try:
        collector._get_json(
            f"{collector.ESPN_SITE_BASE}/summary",
            {"event": "401872925"},
        )
    except collector.NFLRushingYardsContextError as exc:
        message = str(exc)
        assert "both certified transports" in message
        assert "primary HTTP 403" in message
        assert "alternate HTTP 429" in message
    else:
        raise AssertionError("dual ESPN transport failure did not fail closed")

    assert len(seen) == 2
    assert seen[0].startswith(collector.ESPN_SITE_BASE)
    assert seen[1].startswith(collector.ESPN_SITE_ALTERNATE_BASE)


def test_collector_exact_id_prior_season_fallback(monkeypatch):
    _install_fake_espn(monkeypatch)
    payload = collector.collect_nfl_rushing_yards_context("401900001")
    assert payload["schema_version"] == "nfl_rushing_yards_context_v1"
    assert payload["official_event_id"] == "401900001"
    assert payload["ready"] is True
    assert payload["identity"]["player_name_matching"] is False
    assert payload["identity"]["fuzzy_matching"] is False
    assert payload["identity"]["synthetic_event_ids"] is False
    assert payload["identity"]["synthetic_player_ids"] is False
    assert payload["semantics"] == {
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }
    by_team = {team["official_team_id"]: team for team in payload["teams"]}
    assert by_team["27"]["players"][0]["official_athlete_id"] == "100"
    assert by_team["27"]["players"][0]["carries"] == 20
    assert by_team["27"]["players"][0]["rushing_yards"] == 100
    assert by_team["27"]["player_baseline_season"] == 2025
    assert by_team["27"]["opponent_run_front"]["official_team_id"] == "4"
    assert by_team["27"]["opponent_run_front"]["rush_yards_allowed_per_game"] == 108.0


def test_collector_rejects_non_numeric_event_id():
    try:
        collector.collect_nfl_rushing_yards_context("not-an-id")
    except collector.NFLRushingYardsContextError as exc:
        assert "numeric ESPN" in str(exc)
    else:
        raise AssertionError("non-numeric event ID was accepted")


def test_route_status_contract():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/v1/nfl/rushing-yards/status")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "nfl_rushing_yards_context_v1"
    assert body["official_event_id_required"] is True
    assert body["official_athlete_id_required"] is True
    assert body["player_name_matching"] is False
    assert body["fuzzy_matching"] is False
    assert body["model_enabled"] is False
    assert body["projection_enabled"] is False
    assert body["market_enabled"] is False
    assert body["sportsbook_influence"] == 0.0
    assert body["stake_sizing_enabled"] is False


def test_route_returns_exact_id_context(monkeypatch):
    _install_fake_espn(monkeypatch)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/v1/nfl/rushing-yards", params={"event_id": "401900001"})
    assert response.status_code == 200
    body = response.json()
    assert body["official_event_id"] == "401900001"
    athlete_ids = [p["official_athlete_id"] for team in body["teams"] for p in team["players"]]
    assert athlete_ids == ["100", "200"]
    assert len(set(athlete_ids)) == len(athlete_ids)


def test_route_fails_closed_on_weakened_semantics(monkeypatch):
    _install_fake_espn(monkeypatch)
    original = route.collect_nfl_rushing_yards_context

    def weakened(event_id):
        payload = original(event_id)
        payload["semantics"]["market_enabled"] = True
        return payload

    monkeypatch.setattr(route, "collect_nfl_rushing_yards_context", weakened)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/v1/nfl/rushing-yards", params={"event_id": "401900001"})
    assert response.status_code == 503
    assert "safety contract failed closed" in response.json()["detail"]
