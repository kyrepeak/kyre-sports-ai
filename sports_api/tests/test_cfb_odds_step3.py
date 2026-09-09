from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from sports_api.api import cfb_odds_v1 as step3


def _feed(*rows):
    return {
        "schema_version": "cfb_market_feed_v1",
        "captured_at_utc": "2026-09-09T22:00:00+00:00",
        "source": "FanDuel anonymous public NCAAF content-managed-page",
        "games": list(rows),
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def _market(
    *,
    game_id="fd-1",
    away_team="Florida A&M",
    home_team="Miami Florida",
    start_time_utc="2026-09-11T00:00:00+00:00",
    total=62.5,
    sportsbook="FanDuel",
):
    return {
        "game_id": game_id,
        "away_team": away_team,
        "home_team": home_team,
        "start_time_utc": start_time_utc,
        "total": total,
        "sportsbook": sportsbook,
        "updated_at_utc": "2026-09-09T22:00:00+00:00",
        "line_status": "active",
    }


def _verified(
    *,
    event_id="401858213",
    game_date="2026-09-10",
    away_team="Florida A&M",
    home_team="Miami",
):
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": "50",
        "home_team_id": "2390",
        "venue": "Hard Rock Stadium",
        "broadcast": "ACC Network",
        "status": "Scheduled",
        "sources": ["verified fixture"],
    }


def test_step3_builds_streamlit_friendly_verified_contract():
    body = step3.build_odds_payload(_feed(_market()), [_verified()])
    assert body["step"] == 3
    assert body["schema_version"] == "cfb_odds_v1"
    assert body["game_count"] == 1
    row = body["games"][0]
    assert row["game_id"] == "401858213"
    assert row["provider_game_id"] == "fd-1"
    assert row["away_team"] == "Florida A&M"
    assert row["home_team"] == "Miami"
    assert row["market_type"] == "game_total"
    assert row["total"] == 62.5
    assert row["sportsbook"] == "FanDuel"
    assert row["identity_verified"] is True
    assert body["diagnostics"]["complete_identity_coverage"] is True
    assert body["market_semantics"]["projection_weight"] == 0.0
    assert body["market_semantics"]["may_modify_projection"] is False


def test_step3_refuses_partial_identity_coverage():
    wrong = _market(home_team="Florida State")
    with pytest.raises(ValueError, match="identity coverage is incomplete"):
        step3.build_odds_payload(_feed(wrong), [_verified()])


def test_step3_sorts_rows_stably():
    feed = _feed(
        _market(
            game_id="fd-late",
            away_team="Georgia",
            home_team="Clemson",
            start_time_utc="2026-09-12T23:00:00+00:00",
            total=58.5,
        ),
        _market(game_id="fd-early"),
    )
    verified = [
        _verified(),
        _verified(
            event_id="game-2",
            game_date="2026-09-12",
            away_team="Georgia",
            home_team="Clemson",
        ),
    ]
    body = step3.build_odds_payload(feed, verified)
    assert [row["game_id"] for row in body["games"]] == [
        "401858213",
        "game-2",
    ]


def test_step3_endpoint_supports_date_game_and_sportsbook_filters(monkeypatch):
    feed = _feed(_market())
    monkeypatch.setattr(step3, "_load_feed", lambda: feed)
    monkeypatch.setattr(
        step3,
        "resolve_verified_games",
        lambda _feed: (
            [_verified()],
            {
                "resolver_mode": "test verified snapshot",
                "verified_games": 1,
                "fail_closed": True,
            },
        ),
    )

    app = FastAPI()
    app.include_router(step3.router)
    client = TestClient(app)

    response = client.get(
        "/api/v1/cfb/odds"
        "?game_date=2026-09-10"
        "&game_id=401858213"
        "&sportsbook=fanduel"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["game_count"] == 1
    assert body["games"][0]["game_id"] == "401858213"
    assert body["identity_resolution"]["verified_games"] == 1


def test_step3_endpoint_returns_404_when_filters_match_nothing(monkeypatch):
    monkeypatch.setattr(step3, "_load_feed", lambda: _feed(_market()))
    monkeypatch.setattr(
        step3,
        "resolve_verified_games",
        lambda _feed: ([_verified()], {"verified_games": 1}),
    )

    app = FastAPI()
    app.include_router(step3.router)
    response = TestClient(app).get("/api/v1/cfb/odds?game_id=not-real")
    assert response.status_code == 404


def test_step3_status_contract_is_projection_safe():
    app = FastAPI()
    app.include_router(step3.router)
    response = TestClient(app).get("/api/v1/cfb/odds/status")
    assert response.status_code == 200
    body = response.json()
    assert body["step"] == 3
    assert body["endpoint_ready"] is True
    assert body["endpoint"] == "/api/v1/cfb/odds"
    assert body["identity_required"] is True
    assert body["identity_policy"]["synthetic_ids"] is False
    assert body["identity_policy"]["fuzzy_matching"] is False
    assert body["market_semantics"]["projection_weight"] == 0.0


def test_shared_host_starts_with_step3_status_route():
    from sports_api.main import app as shared_host_app

    with TestClient(shared_host_app) as client:
        health = client.get("/health")
        step3_status = client.get("/api/v1/cfb/odds/status")

    assert health.status_code == 200
    assert step3_status.status_code == 200
    assert step3_status.json()["step"] == 3
