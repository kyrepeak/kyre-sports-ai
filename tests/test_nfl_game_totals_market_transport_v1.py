from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from sports_api.api import nfl_game_totals_market_v1 as market
from sports_api.collectors.nfl_fanduel_totals_v1 import NFLGameTotalsCollectorError


EVENT_ID = "401772714"
NOW = datetime(2026, 9, 15, 1, 30, tzinfo=timezone.utc)


def _payload(stamp=NOW):
    iso = stamp.isoformat()
    return {
        "schema_version": "nfl_game_totals_market_v1",
        "service": "Kyre Sports API",
        "sport": "nfl",
        "market": "game_total",
        "official_event_id": EVENT_ID,
        "captured_at_utc": iso,
        "ready": True,
        "market_available": True,
        "identity": {
            "official_authority": "ESPN",
            "official_event_id": EVENT_ID,
            "provider_event_id": "fd-9001",
            "away_team_id": "8",
            "home_team_id": "2",
            "away_abbr": "DET",
            "home_abbr": "BUF",
            "kickoff_delta_seconds": 0,
            "team_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
        },
        "books": [
            {
                "official_event_id": EVENT_ID,
                "sportsbook": "FanDuel",
                "provider": "FanDuel via Kyre Sports API",
                "provider_event_id": "fd-9001",
                "market_id": "m-total-1",
                "total": 48.5,
                "over_price": -110,
                "under_price": -110,
                "updated_at_utc": iso,
                "line_status": "active",
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "multi_book_capable": True,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def test_market_payload_validates_fresh_exact_id_snapshot():
    out = market._validate_market_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert out["book_count"] == 1
    assert out["books"][0]["total"] == 48.5
    assert out["freshness"]["snapshot_ttl_seconds"] == 10.0
    assert out["freshness"]["max_snapshot_age_seconds"] == 120.0


def test_market_payload_fails_closed_when_stale():
    stale = NOW - timedelta(seconds=market.MAX_SNAPSHOT_AGE_SECONDS + 1)
    with pytest.raises(HTTPException) as exc:
        market._validate_market_payload(_payload(stale), EVENT_ID, now_utc=NOW)
    assert exc.value.status_code == 503
    assert "stale" in str(exc.value.detail).lower()


def test_market_payload_fails_closed_on_future_timestamp():
    future = NOW + timedelta(seconds=market.MAX_FUTURE_SKEW_SECONDS + 1)
    with pytest.raises(HTTPException) as exc:
        market._validate_market_payload(_payload(future), EVENT_ID, now_utc=NOW)
    assert exc.value.status_code == 503
    assert "future" in str(exc.value.detail).lower()


def test_market_payload_fails_closed_on_wrong_event_identity():
    with pytest.raises(HTTPException) as exc:
        market._validate_market_payload(_payload(), "999999", now_utc=NOW)
    assert exc.value.status_code == 503
    assert "identity mismatch" in str(exc.value.detail).lower()


def test_market_payload_fails_closed_on_invalid_total_or_price():
    payload = _payload()
    payload["books"][0]["total"] = -1
    with pytest.raises(HTTPException):
        market._validate_market_payload(payload, EVENT_ID, now_utc=NOW)
    payload = _payload()
    payload["books"][0]["over_price"] = 50
    with pytest.raises(HTTPException):
        market._validate_market_payload(payload, EVENT_ID, now_utc=NOW)


def test_market_cache_expires_and_returns_deep_copy():
    market._clear_market_snapshot_cache()
    payload = _payload()
    market._cache_put(EVENT_ID, payload, now=100.0)
    cached = market._cache_get(EVENT_ID, now=105.0)
    assert cached is not None
    cached["books"][0]["total"] = 99.5
    second = market._cache_get(EVENT_ID, now=105.0)
    assert second["books"][0]["total"] == 48.5
    assert market._cache_get(EVENT_ID, now=111.0) is None


def test_upstream_collector_error_becomes_fail_closed_503(monkeypatch):
    market._clear_market_snapshot_cache()

    def fail(event_id):
        raise NFLGameTotalsCollectorError("no open pregame Total Points market")

    monkeypatch.setattr(market, "collect_fanduel_nfl_game_total", fail)
    with pytest.raises(HTTPException) as exc:
        market._collect_or_reuse_market(EVENT_ID)
    assert exc.value.status_code == 503
    assert "market unavailable" in str(exc.value.detail).lower()


def test_public_route_rejects_non_numeric_event_id_before_network():
    with pytest.raises(HTTPException) as exc:
        market.game_totals_market("fake-event")
    assert exc.value.status_code == 422
