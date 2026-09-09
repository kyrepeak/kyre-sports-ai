from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api.cfb_markets import router, validate_feed


def _sample_feed():
    return {
        "schema_version": "cfb_market_feed_v1",
        "captured_at_utc": "2026-09-09T18:00:00Z",
        "source": "Kyre Sports API test feed",
        "games": [
            {
                "game_id": "cfb-2026-miami-florida",
                "home_team": "Florida",
                "away_team": "Miami",
                "start_time_utc": "2026-09-12T23:30:00Z",
                "total": 51.5,
                "sportsbook": "DraftKings",
                "updated_at_utc": "2026-09-09T17:59:00Z",
                "line_status": "active",
            }
        ],
    }


def test_contract_keeps_market_data_out_of_projection():
    validated = validate_feed(_sample_feed())
    assert validated["market_semantics"] == {
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
    }
    assert validated["games"][0]["total"] == 51.5


def test_status_route_declares_step1_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(tmp_path / "cfb_market_feed.json"))
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/v1/cfb/markets/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Kyre Sports API"
    assert body["sport"] == "college_football"
    assert body["route_ready"] is True
    assert body["market_semantics"]["projection_weight"] == 0.0
    assert body["market_semantics"]["market_context_only"] is True


def test_shared_host_lifespan_starts_with_cfb_route(monkeypatch, tmp_path):
    """Regression test for the Render startup recursion from nested router lifespans."""
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(tmp_path / "cfb_market_feed.json"))
    from sports_api.main import app as shared_host_app

    with TestClient(shared_host_app) as client:
        health = client.get("/health")
        status = client.get("/api/v1/cfb/markets/status")

    assert health.status_code == 200
    assert status.status_code == 200
    assert status.json()["market_semantics"]["projection_weight"] == 0.0


def test_ingest_and_read_current_market(monkeypatch, tmp_path):
    feed_path = tmp_path / "cfb_market_feed.json"
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(feed_path))
    monkeypatch.setenv("CFB_KYRE_MARKET_INGEST_TOKEN", "step1-test-token")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/cfb/markets/feed",
        json=_sample_feed(),
        headers={"Authorization": "Bearer step1-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["stored"] is True
    assert response.json()["authorization_token_returned"] is False

    response = client.get("/api/v1/cfb/markets/current?game_id=cfb-2026-miami-florida")
    assert response.status_code == 200
    body = response.json()
    assert body["game"]["home_team"] == "Florida"
    assert body["game"]["away_team"] == "Miami"
    assert body["game"]["sportsbook"] == "DraftKings"
    assert body["game"]["line_status"] == "active"
    assert body["market_semantics"]["projection_weight"] == 0.0


def test_ingest_rejects_bad_token_without_echoing_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(tmp_path / "cfb_market_feed.json"))
    monkeypatch.setenv("CFB_KYRE_MARKET_INGEST_TOKEN", "real-secret")
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/v1/cfb/markets/feed",
        json=_sample_feed(),
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert response.status_code == 401
    assert "real-secret" not in response.text
    assert "wrong-secret" not in response.text
