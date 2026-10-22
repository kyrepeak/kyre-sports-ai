from __future__ import annotations

import importlib

import requests


def _valid_payload() -> dict:
    return {
        "ready": True,
        "schema_version": "nfl_passing_yards_simple_qb_grid_v1",
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "quarterback_count": 1,
        "quarterbacks": [
            {
                "player_id": "kyre:nfl:player:test-qb",
                "game_id": "kyre:nfl:game:test-game",
                "qb_name": "Test Quarterback",
                "team_abbr": "AAA",
                "opponent_abbr": "BBB",
                "game_time": "13:00",
                "market": {"status": "NOT_AVAILABLE", "line": None},
                "over_probability": None,
                "under_probability": None,
            }
        ],
        "routing": {
            "canonical_ids": True,
            "sportsbook_line_averaging": False,
            "missing_to_zero": False,
        },
    }


class _Response:
    status_code = 200

    def json(self):
        return _valid_payload()


def test_gateway_retries_one_readtimeout_with_bounded_read_budget(monkeypatch):
    gateway = importlib.import_module("nfl_passing_yards_slate_gateway_v1")
    calls: list[tuple[float, float]] = []

    def fake_get(url, *, params, timeout, headers):
        calls.append(timeout)
        if len(calls) == 1:
            raise requests.ReadTimeout("cold start")
        return _Response()

    monkeypatch.setattr(gateway.requests, "get", fake_get)
    result = gateway.load_passing_yards_slate("2026-10-22")

    assert result["ready"] is True
    assert calls == [
        (gateway.CONNECT_TIMEOUT, gateway.COLD_READ_TIMEOUT),
        (gateway.CONNECT_TIMEOUT, gateway.RETRY_READ_TIMEOUT),
    ]
    assert gateway.COLD_READ_TIMEOUT + gateway.RETRY_READ_TIMEOUT <= 25.0


def test_gateway_does_not_retry_non_readtimeout_request_errors(monkeypatch):
    gateway = importlib.import_module("nfl_passing_yards_slate_gateway_v1")
    calls = 0

    def fake_get(url, *, params, timeout, headers):
        nonlocal calls
        calls += 1
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(gateway.requests, "get", fake_get)
    result = gateway.load_passing_yards_slate("2026-10-22")

    assert result["ready"] is False
    assert calls == 1
    assert result["reason"].endswith("ConnectionError")


def test_gateway_stops_after_second_readtimeout(monkeypatch):
    gateway = importlib.import_module("nfl_passing_yards_slate_gateway_v1")
    calls = 0

    def fake_get(url, *, params, timeout, headers):
        nonlocal calls
        calls += 1
        raise requests.ReadTimeout("still cold")

    monkeypatch.setattr(gateway.requests, "get", fake_get)
    result = gateway.load_passing_yards_slate("2026-10-22")

    assert result["ready"] is False
    assert calls == 2
    assert result["reason"].endswith("ReadTimeout")
