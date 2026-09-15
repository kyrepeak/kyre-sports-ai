from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.api.nfl_game_totals_market_v1 as market_api


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market_api.router)
    return TestClient(app)


def test_game_totals_market_contract_uses_exact_espn_event_id(monkeypatch) -> None:
    def fake_collect(event_id: str):
        assert event_id == "401671789"
        return {
            "event_id": event_id,
            "provider": "fanduel",
            "provider_event_id": "fd-123",
            "captured_at_utc": "2026-09-15T20:00:00Z",
            "ready": True,
            "market_available": True,
            "markets": [
                {
                    "sportsbook": "fanduel",
                    "total": 47.5,
                    "over_price": -110,
                    "under_price": -110,
                    "market_id": "total-123",
                    "updated_at_utc": "2026-09-15T19:59:00Z",
                    "active": True,
                }
            ],
            "diagnostics": [],
        }

    monkeypatch.setattr(market_api, "collect_nfl_game_totals", fake_collect)

    response = _client().get(
        "/api/v1/nfl/totals/market",
        params={"event_id": "401671789"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "401671789"
    assert body["provider"] == "fanduel"
    assert body["provider_event_id"] == "fd-123"
    assert body["ready"] is True
    assert body["market_available"] is True
    assert body["sportsbook_projection_weight"] == 0.0
    assert body["markets"] == [
        {
            "sportsbook": "fanduel",
            "total": 47.5,
            "over_price": -110,
            "under_price": -110,
            "market_id": "total-123",
            "updated_at_utc": "2026-09-15T19:59:00Z",
            "active": True,
        }
    ]


def test_game_totals_market_fails_closed_when_market_is_unavailable(monkeypatch) -> None:
    def fake_collect(event_id: str):
        return {
            "event_id": event_id,
            "provider": "fanduel",
            "provider_event_id": None,
            "captured_at_utc": "2026-09-15T20:00:00Z",
            "ready": False,
            "market_available": False,
            "markets": [],
            "diagnostics": ["exact ESPN-to-FanDuel reconciliation failed"],
        }

    monkeypatch.setattr(market_api, "collect_nfl_game_totals", fake_collect)

    response = _client().get(
        "/api/v1/nfl/totals/market",
        params={"event_id": "401671789"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["market_available"] is False
    assert body["markets"] == []
    assert body["sportsbook_projection_weight"] == 0.0
    assert body["diagnostics"]


def test_game_totals_market_requires_event_id() -> None:
    response = _client().get("/api/v1/nfl/totals/market")
    assert response.status_code == 422
