from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_market_api():
    """Load only the new API module, not sports_api.api package side effects.

    The collector has its own executable tests. This API contract test deliberately
    injects only the collector symbol required by the route module so unrelated WNBA
    imports in sports_api.api.__init__ cannot affect this narrow certification lane.
    """
    collector_name = "sports_api.collectors.nfl_fanduel_game_totals_v1"
    package_names = ("sports_api", "sports_api.collectors", collector_name)
    previous = {name: sys.modules.get(name) for name in package_names}

    sports_api_package = ModuleType("sports_api")
    sports_api_package.__path__ = []  # type: ignore[attr-defined]
    collectors_package = ModuleType("sports_api.collectors")
    collectors_package.__path__ = []  # type: ignore[attr-defined]
    collector_module = ModuleType(collector_name)

    def _placeholder_collect(event_id: str):
        raise AssertionError(f"collector should be monkeypatched in API contract test: {event_id}")

    collector_module.collect_nfl_game_totals = _placeholder_collect  # type: ignore[attr-defined]

    sys.modules["sports_api"] = sports_api_package
    sys.modules["sports_api.collectors"] = collectors_package
    sys.modules[collector_name] = collector_module

    try:
        module_path = (
            Path(__file__).resolve().parents[1]
            / "sports_api"
            / "api"
            / "nfl_game_totals_market_v1.py"
        )
        spec = spec_from_file_location("nfl_game_totals_market_v1_under_test", module_path)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, prior in previous.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


market_api = _load_market_api()


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
