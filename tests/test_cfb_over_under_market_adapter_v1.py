"""Regression tests for CFB O/U Market Adapter V1."""
from __future__ import annotations

import cfb_over_under_market_adapter_v1 as market


def _payload():
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": "2026-09-09T22:54:00+00:00",
        "source": "FanDuel anonymous public NCAAF content-managed-page",
        "game_count": 1,
        "games": [
            {
                "game_id": "401858213",
                "provider_game_id": "35993112",
                "game_date": "2026-09-10",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "away_team_id": "50",
                "home_team_id": "2390",
                "start_time_utc": "2026-09-11T00:00:00+00:00",
                "sportsbook": "FanDuel",
                "market_type": "game_total",
                "total": 62.5,
                "line_status": "active",
                "line_updated_at_utc": "2026-09-09T22:54:00+00:00",
                "venue": "Hard Rock Stadium",
                "broadcast": "ACC Network",
                "identity_verified": True,
            }
        ],
        "diagnostics": {
            "identity_verified_rows": 1,
            "unmatched_market_rows": 0,
            "complete_identity_coverage": True,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def test_step3_contract_validates_and_preserves_zero_projection_weight():
    out = market._validate_payload(_payload(), requested_day="2026-09-10")
    assert out["game_count"] == 1
    assert out["games"][0]["game_id"] == "401858213"
    assert out["games"][0]["total"] == 62.5
    assert out["market_semantics"]["projection_weight"] == 0.0
    assert out["market_semantics"]["may_modify_projection"] is False


def test_adapter_attaches_line_only_by_official_espn_event_id():
    games = [
        {
            "game_date": "2026-09-10",
            "away_team": "Florida A&M",
            "home_team": "Miami (FL)",
            "espn_event_id": "401858213",
            "identity_key": "schedule-1",
        },
        {
            "game_date": "2026-09-10",
            "away_team": "Other",
            "home_team": "Game",
            "espn_event_id": "not-in-market",
            "identity_key": "schedule-2",
        },
    ]
    out, diag = market.attach_market_lines(games, _payload())
    assert out[0]["market_line_available"] is True
    assert out[0]["market_total"] == 62.5
    assert out[0]["market_sportsbook"] == "FanDuel"
    assert out[0]["market_official_game_id"] == "401858213"
    assert out[0]["market_projection_weight"] == 0.0
    assert out[1]["market_line_available"] is False
    assert diag["market_lines_attached"] == 1
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False
    assert diag["matching_method"] == "official ESPN event_id only"


def test_adapter_never_name_guesses_when_official_id_missing():
    games = [
        {
            "game_date": "2026-09-10",
            "away_team": "Florida A&M",
            "home_team": "Miami",
            "identity_key": "same-names-but-no-id",
        }
    ]
    out, diag = market.attach_market_lines(games, _payload())
    assert out[0]["market_line_available"] is False
    assert out[0]["market_reason"] == "missing_official_espn_event_id"
    assert diag["schedule_games_missing_official_id"] == 1


def test_adapter_rejects_unsafe_market_semantics():
    payload = _payload()
    payload["market_semantics"]["projection_weight"] = 0.1
    try:
        market._validate_payload(payload, requested_day="2026-09-10")
    except ValueError as exc:
        assert "projection weight" in str(exc)
    else:
        raise AssertionError("unsafe market projection weight was accepted")


def test_adapter_rejects_incomplete_identity_coverage():
    payload = _payload()
    payload["diagnostics"]["complete_identity_coverage"] = False
    try:
        market._validate_payload(payload, requested_day="2026-09-10")
    except ValueError as exc:
        assert "identity coverage" in str(exc)
    else:
        raise AssertionError("incomplete identity coverage was accepted")


def test_market_line_is_bounded_and_visible():
    game = {
        "market_line_available": True,
        "market_total": 62.5,
    }
    assert market.market_line(game) == 62.5
    assert market.market_line({"market_line_available": False}) is None


def test_live_loader_uses_step3_date_and_sportsbook_filters(monkeypatch):
    seen = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return _payload()

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return Response()

    market.clear_market_cache()
    monkeypatch.setattr(market.requests, "get", fake_get)
    payload, diag = market.load_odds_for_date("2026-09-10", "FanDuel")
    market.clear_market_cache()

    assert seen["url"].endswith("/api/v1/cfb/odds")
    assert seen["params"] == {
        "game_date": "2026-09-10",
        "sportsbook": "FanDuel",
    }
    assert seen["timeout"] == market.REQUEST_TIMEOUT_SECONDS
    assert diag["status"] == "GREEN"
    assert payload["game_count"] == 1


def test_adapter_rejects_missing_projection_weight_contract():
    payload = _payload()
    payload["market_semantics"].pop("projection_weight")
    try:
        market._validate_payload(payload, requested_day="2026-09-10")
    except ValueError as exc:
        assert "projection weight is missing" in str(exc)
    else:
        raise AssertionError("missing projection-weight contract was accepted")
