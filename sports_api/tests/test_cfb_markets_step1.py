import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api import cfb_markets
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


@pytest.mark.parametrize("bad_total", [float("nan"), float("inf"), float("-inf")])
def test_contract_rejects_non_finite_totals(bad_total):
    payload = _sample_feed()
    payload["games"][0]["total"] = bad_total
    with pytest.raises(ValueError, match="outside the supported range"):
        validate_feed(payload)


def test_contract_rejects_duplicate_provider_game_ids():
    payload = _sample_feed()
    payload["games"].append(dict(payload["games"][0]))
    with pytest.raises(ValueError, match="duplicate game_id"):
        validate_feed(payload)


def test_status_route_declares_live_self_healing_contract(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CFB_KYRE_MARKET_FEED_PATH",
        str(tmp_path / "cfb_market_feed.json"),
    )
    monkeypatch.delenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", raising=False)
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/v1/cfb/markets/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Kyre Sports API"
    assert body["sport"] == "college_football"
    assert body["route_ready"] is True
    assert body["auto_refresh_enabled"] is True
    assert body["live_provider"]["provider"] == "FanDuel"
    assert body["live_provider"]["custom_page_id"] == "ncaaf"
    assert body["live_provider"]["secret_required"] is False
    assert body["live_provider"]["requests_per_refresh"] == 1
    assert body["live_provider"]["cache_self_heals_after_redeploy"] is True
    assert body["market_semantics"]["projection_weight"] == 0.0
    assert body["market_semantics"]["market_context_only"] is True


def test_shared_host_lifespan_starts_with_cfb_route(monkeypatch, tmp_path):
    """Regression test for the Render startup recursion from nested router lifespans."""
    monkeypatch.setenv(
        "CFB_KYRE_MARKET_FEED_PATH",
        str(tmp_path / "cfb_market_feed.json"),
    )
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
    monkeypatch.setenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", "false")
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

    response = client.get(
        "/api/v1/cfb/markets/current?game_id=cfb-2026-miami-florida"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["game"]["home_team"] == "Florida"
    assert body["game"]["away_team"] == "Miami"
    assert body["game"]["sportsbook"] == "DraftKings"
    assert body["game"]["line_status"] == "active"
    assert body["market_semantics"]["projection_weight"] == 0.0


def test_missing_cache_self_heals_from_live_provider(monkeypatch, tmp_path):
    feed_path = tmp_path / "cfb_market_feed.json"
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(feed_path))
    monkeypatch.delenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", raising=False)

    live = _sample_feed()
    live["captured_at_utc"] = "2026-09-09T20:00:00Z"
    live["source"] = "FanDuel anonymous public NCAAF content-managed-page"
    called = {"count": 0}

    def refresh():
        called["count"] += 1
        validated = validate_feed(live)
        cfb_markets._store_validated_feed(validated)
        return validated

    monkeypatch.setattr(cfb_markets, "_refresh_from_fanduel", refresh)

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/v1/cfb/markets/current")
    assert response.status_code == 200
    assert called["count"] == 1
    assert feed_path.is_file()
    assert response.json()["source"].startswith("FanDuel anonymous public NCAAF")


def test_internal_force_refresh_replaces_existing_cache(monkeypatch, tmp_path):
    feed_path = tmp_path / "cfb_market_feed.json"
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(feed_path))
    monkeypatch.delenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", raising=False)

    stale = validate_feed(_sample_feed())
    cfb_markets._store_validated_feed(stale)

    fresh = _sample_feed()
    fresh["captured_at_utc"] = "2026-09-09T20:00:00Z"
    fresh["games"][0]["total"] = 52.5
    called = {"count": 0}

    def refresh():
        called["count"] += 1
        validated = validate_feed(fresh)
        cfb_markets._store_validated_feed(validated)
        return validated

    monkeypatch.setattr(cfb_markets, "_refresh_from_fanduel", refresh)
    result = cfb_markets._load_feed(force_refresh=True)
    assert called["count"] == 1
    assert result["games"][0]["total"] == 52.5


def test_public_current_has_no_force_refresh_parameter(monkeypatch, tmp_path):
    feed_path = tmp_path / "cfb_market_feed.json"
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(feed_path))
    monkeypatch.setenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", "false")
    cfb_markets._store_validated_feed(validate_feed(_sample_feed()))

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/v1/cfb/markets/current?refresh=true")
    assert response.status_code == 200
    # Unknown query parameters are ignored by FastAPI, but there is no route
    # argument that can bypass the cache and no provider refresh occurs.
    assert response.json()["games"][0]["total"] == 51.5


def test_ingest_rejects_bad_token_before_echoing_or_parsing(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CFB_KYRE_MARKET_FEED_PATH",
        str(tmp_path / "cfb_market_feed.json"),
    )
    monkeypatch.setenv("CFB_KYRE_MARKET_INGEST_TOKEN", "real-secret")
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/v1/cfb/markets/feed",
        content=b"{definitely-not-json",
        headers={
            "Authorization": "Bearer wrong-secret",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401
    assert "real-secret" not in response.text
    assert "wrong-secret" not in response.text
    assert "valid UTF-8 JSON" not in response.text


def test_ingest_rejects_oversized_declared_body_before_parse(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CFB_KYRE_MARKET_FEED_PATH",
        str(tmp_path / "cfb_market_feed.json"),
    )
    monkeypatch.setenv("CFB_KYRE_MARKET_INGEST_TOKEN", "real-secret")
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/v1/cfb/markets/feed",
        content=b"{}",
        headers={
            "Authorization": "Bearer real-secret",
            "Content-Type": "application/json",
            "Content-Length": str(cfb_markets.MAX_FEED_BYTES + 1),
        },
    )
    assert response.status_code == 413


def test_strict_serializer_refuses_nan_even_if_called_directly():
    validated = validate_feed(_sample_feed())
    validated["games"][0]["total"] = math.nan
    with pytest.raises(ValueError, match="strict JSON"):
        cfb_markets._serialize_feed(validated)


def test_materially_future_capture_timestamp_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CFB_KYRE_MARKET_FEED_PATH",
        str(tmp_path / "cfb_market_feed.json"),
    )
    payload = _sample_feed()
    payload["captured_at_utc"] = "2099-01-01T00:00:00Z"
    validated = validate_feed(payload)
    with pytest.raises(ValueError, match="implausibly in the future"):
        cfb_markets._store_validated_feed(validated)


def test_invalid_cache_self_heals_from_live_provider(monkeypatch, tmp_path):
    feed_path = tmp_path / "cfb_market_feed.json"
    monkeypatch.setenv("CFB_KYRE_MARKET_FEED_PATH", str(feed_path))
    monkeypatch.delenv("CFB_FANDUEL_AUTO_REFRESH_ENABLED", raising=False)
    feed_path.write_text("{truncated-json", encoding="utf-8")

    fresh = _sample_feed()
    fresh["captured_at_utc"] = "2026-09-09T20:00:00Z"
    fresh["source"] = "FanDuel anonymous public NCAAF content-managed-page"
    called = {"count": 0}

    def refresh():
        called["count"] += 1
        validated = validate_feed(fresh)
        cfb_markets._store_validated_feed(validated)
        return validated

    monkeypatch.setattr(cfb_markets, "_refresh_from_fanduel", refresh)
    result = cfb_markets._load_feed()
    assert called["count"] == 1
    assert result["source"].startswith("FanDuel anonymous public NCAAF")
