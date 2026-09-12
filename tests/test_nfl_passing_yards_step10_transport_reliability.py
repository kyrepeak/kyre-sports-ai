from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import requests

import nfl_passing_yards_market_api_v1 as api

EVENT_ID = "401872925"
NOW = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)


def _payload(*, captured_at: datetime = NOW, schema_version: str = api.SCHEMA_VERSION) -> dict:
    return {
        "schema_version": schema_version,
        "ready": True,
        "market_available": True,
        "official_event_id": EVENT_ID,
        "sportsbook": "FanDuel",
        "captured_at_utc": captured_at.isoformat(),
        "props": [
            {
                "official_event_id": EVENT_ID,
                "official_athlete_id": "3052587",
                "official_team_id": "27",
                "player_name": "Verified QB",
                "position": "QB",
                "market_type": "passing_yards",
                "line": 232.5,
                "over_odds": -113,
                "under_odds": -113,
                "sportsbook": "FanDuel",
                "line_status": "active",
            }
        ],
        "identity": {
            "fuzzy_matching": False,
            "player_name_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
    }


class _Response:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_read_timeout_retries_once_same_exact_event_then_accepts_fresh_market(monkeypatch):
    calls = []
    sleeps = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            raise requests.exceptions.ReadTimeout("cold read")
        return _Response(_payload())

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)

    assert result["ready"] is True
    assert result["request_attempts"] == 2
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert calls[0][1]["params"] == calls[1][1]["params"] == {"event_id": EVENT_ID}
    assert calls[0][1]["timeout"] == calls[1][1]["timeout"] == (
        api.REQUEST_CONNECT_TIMEOUT_SECONDS,
        api.REQUEST_READ_TIMEOUT_SECONDS,
    )
    assert sleeps == [api.RETRY_BACKOFF_SECONDS]
    assert result["projection_weight"] == 0.0
    assert result["stake_sizing_enabled"] is False


@pytest.mark.parametrize(
    "exc_type",
    [requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError],
)
def test_other_transient_connection_failures_get_only_one_bounded_retry(monkeypatch, exc_type):
    calls = []
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise exc_type("transient")
        return _Response(_payload())

    monkeypatch.setattr(api.requests, "get", fake_get)
    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
    assert result["ready"] is True
    assert result["request_attempts"] == 2
    assert len(calls) == api.MAX_REQUEST_ATTEMPTS == 2


def test_second_transient_failure_stops_after_two_attempts_and_fails_closed(monkeypatch):
    calls = []
    sleeps = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.exceptions.ReadTimeout("still slow")

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert result["reason"].endswith("ReadTimeout")
    assert result["request_attempts"] == 2
    assert len(calls) == 2
    assert sleeps == [api.RETRY_BACKOFF_SECONDS]
    assert result["projection_weight"] == 0.0
    assert result["market_context_only"] is True
    assert result["stake_sizing_enabled"] is False


def test_http_failure_is_not_retried(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response({}, status_code=503)

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: pytest.fail("HTTP response must not retry"))

    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert result["http"] == 503
    assert result["request_attempts"] == 1
    assert len(calls) == 1


def test_invalid_json_is_not_retried(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response(ValueError("bad json"))

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: pytest.fail("invalid JSON must not retry"))

    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "invalid json" in result["reason"].lower()
    assert result["request_attempts"] == 1
    assert len(calls) == 1


def test_schema_mismatch_and_stale_payload_are_not_retried(monkeypatch):
    responses = [
        _Response(_payload(schema_version="wrong_schema")),
        _Response(_payload(captured_at=NOW - timedelta(seconds=api.MAX_MARKET_AGE_SECONDS + 1))),
    ]

    for response in responses:
        calls = []
        monkeypatch.setattr(api.requests, "get", lambda *args, **kwargs: calls.append((args, kwargs)) or response)
        monkeypatch.setattr(api.time, "sleep", lambda _seconds: pytest.fail("validation failure must not retry"))
        result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
        assert result["ready"] is False
        assert result["request_attempts"] == 1
        assert len(calls) == 1


def test_non_transient_request_exception_is_one_shot(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.exceptions.TooManyRedirects("not transient")

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: pytest.fail("non-transient failure must not retry"))

    result = api.fetch_event_market(EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert result["reason"].endswith("TooManyRedirects")
    assert result["request_attempts"] == 1
    assert len(calls) == 1


def test_invalid_event_id_never_touches_network(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *args, **kwargs: pytest.fail("network must not be called"))
    result = api.fetch_event_market("Baker Mayfield", now_utc=NOW)
    assert result["ready"] is False
    assert "official ESPN event ID" in result["reason"]


def test_permanent_step10_market_safety_limits_remain_frozen():
    assert api.MAX_MARKET_AGE_SECONDS == 300
    assert api.MAX_REQUEST_ATTEMPTS == 2
    assert api.REQUEST_CONNECT_TIMEOUT_SECONDS == 3.0
    assert api.REQUEST_READ_TIMEOUT_SECONDS == 8.0
    assert api.RETRY_BACKOFF_SECONDS == 0.35

    result = api.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert result["ready"] is True
    assert result["sportsbook"] == "FanDuel"
    assert result["projection_weight"] == 0.0
    assert result["market_context_only"] is True
    assert result["stake_sizing_enabled"] is False
