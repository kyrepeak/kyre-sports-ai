from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api import mlb


def _snapshot():
    return {
        "provider": "FanDuel",
        "transport": "anonymous_public_get_only",
        "http_methods": ["GET"],
        "sportsbook_region": "NJ",
        "collected_at_utc": "2026-08-31T04:15:59+00:00",
        "landing_event_count": 2,
        "candidate_pregame_event_count": 2,
        "matched_game_count": 2,
        "fully_priced_game_count": 1,
        "rejected_events": [{"sportsbook_event_id": "x", "reason": "test"}],
        "games": [
            {
                "official_game_id": 1001,
                "sportsbook_event_id": "2001",
                "sportsbook": "FanDuel",
                "away_team": {"id": 1, "name": "Away"},
                "home_team": {"id": 2, "name": "Home"},
                "fully_priced": True,
                "markets": {
                    "moneyline": {"away_odds": -110, "home_odds": 100},
                    "run_line": {
                        "away_line": -1.5,
                        "away_odds": 130,
                        "home_line": 1.5,
                        "home_odds": -150,
                    },
                    "total": {"line": 8.5, "over_odds": -105, "under_odds": -115},
                },
            },
            {
                "official_game_id": 1002,
                "sportsbook_event_id": "2002",
                "sportsbook": "FanDuel",
                "away_team": {"id": 3, "name": "Away Two"},
                "home_team": {"id": 4, "name": "Home Two"},
                "fully_priced": False,
                "markets": {
                    "moneyline": {"away_odds": 105, "home_odds": -115},
                },
            },
        ],
    }


def _client(monkeypatch, collector):
    monkeypatch.setattr(mlb, "collect_live_mlb_game_odds", collector)
    app = FastAPI()
    app.include_router(mlb.router)
    return TestClient(app)


def test_odds_endpoint_defaults_to_fully_priced_games(monkeypatch):
    seen = {}

    def collector(**kwargs):
        seen.update(kwargs)
        return _snapshot()

    response = _client(monkeypatch, collector).get("/api/v1/mlb/odds")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "mlb_live_odds_api_response_v1"
    assert payload["schema_version"] == 1
    assert payload["source"] == "FanDuel"
    assert payload["transport"] == "anonymous_public_get_only"
    assert payload["http_methods"] == ["GET"]
    assert payload["fully_priced_only"] is True
    assert payload["matched_game_count"] == 2
    assert payload["fully_priced_game_count"] == 1
    assert payload["game_count"] == 1
    assert payload["rejected_event_count"] == 1
    assert payload["games"][0]["official_game_id"] == 1001
    assert seen["max_events"] == 30
    assert seen["now_utc"].tzinfo is not None


def test_odds_endpoint_can_return_partially_priced_games(monkeypatch):
    response = _client(monkeypatch, lambda **_: _snapshot()).get(
        "/api/v1/mlb/odds?fully_priced_only=false&max_events=12"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fully_priced_only"] is False
    assert payload["game_count"] == 2


def test_odds_endpoint_validates_max_events(monkeypatch):
    client = _client(monkeypatch, lambda **_: _snapshot())
    assert client.get("/api/v1/mlb/odds?max_events=0").status_code == 422
    assert client.get("/api/v1/mlb/odds?max_events=51").status_code == 422


def test_odds_endpoint_maps_collector_failures_to_502(monkeypatch):
    def collector(**_):
        raise RuntimeError("upstream broke")

    response = _client(monkeypatch, collector).get("/api/v1/mlb/odds")

    assert response.status_code == 502
    assert response.json() == {"detail": "MLB live odds collection failed."}


def test_odds_route_is_registered_on_mlb_router():
    paths = {getattr(route, "path", None) for route in mlb.router.routes}
    assert "/api/v1/mlb/odds" in paths
