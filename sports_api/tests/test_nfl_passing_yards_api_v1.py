from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api import nfl_passing_yards_market_v1 as api
from sports_api.collectors import nfl_fanduel_passing_yards as collector


def _official_summary():
    return {
        "header": {
            "id": "401999001",
            "competitions": [
                {
                    "id": "401999001",
                    "date": "2026-09-13T17:00:00Z",
                    "status": {"type": {"state": "pre", "completed": False}},
                    "competitors": [
                        {"homeAway": "home", "team": {"id": "4", "abbreviation": "CIN", "displayName": "Cincinnati Bengals"}},
                        {"homeAway": "away", "team": {"id": "27", "abbreviation": "TB", "displayName": "Tampa Bay Buccaneers"}},
                    ],
                }
            ],
        }
    }


def _landing():
    return {
        "attachments": {
            "events": {
                "fd-1": {
                    "eventId": "fd-1",
                    "name": "Tampa Bay Buccaneers @ Cincinnati Bengals",
                    "openDate": "2026-09-13T17:00:00Z",
                }
            }
        }
    }


def _market():
    return {
        "marketId": "m-1",
        "marketType": "PLAYER_PASSING_YARDS",
        "marketName": "Passing Yards",
        "marketStatus": "OPEN",
        "inPlay": False,
        "runners": [
            {
                "selectionId": "over-1",
                "runnerStatus": "ACTIVE",
                "handicap": 249.5,
                "result": {"type": "OVER"},
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
            },
            {
                "selectionId": "under-1",
                "runnerStatus": "ACTIVE",
                "handicap": 249.5,
                "result": {"type": "UNDER"},
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
            },
        ],
    }


def _players():
    return {
        "qb-provider-key": {
            "team": "TB",
            "number": "6",
            "position": "QB",
            "selectionIds": ["over-1", "under-1"],
        }
    }


def _rosters():
    return {
        "27": [
            {
                "team_id": "27",
                "athlete_id": "4431452",
                "jersey": "6",
                "position": "QB",
                "display_name": "Verified Tampa QB",
            }
        ],
        "4": [],
    }


def test_official_event_and_provider_event_reconcile_by_exact_ids_and_kickoff():
    official = collector.parse_official_event(_official_summary())
    provider = collector.reconcile_fanduel_event(_landing(), official)
    assert official["event_id"] == "401999001"
    assert official["away"]["team_id"] == "27"
    assert official["home"]["team_id"] == "4"
    assert provider["provider_event_id"] == "fd-1"
    assert provider["kickoff_delta_seconds"] == 0


def test_unknown_provider_team_name_fails_closed_instead_of_fuzzy_matching():
    official = collector.parse_official_event(_official_summary())
    bad = _landing()
    bad["attachments"]["events"]["fd-1"]["name"] = "Tampa @ Cincinnati"
    with pytest.raises(collector.NFLPassingYardsCollectorError):
        collector.reconcile_fanduel_event(bad, official)


def test_passing_yards_market_maps_selection_to_exact_qb_roster_identity():
    players = _players()
    by_selection = {"over-1": ["qb-provider-key"], "under-1": ["qb-provider-key"]}
    row = collector.normalize_passing_yards_market(
        _market(),
        official_event_id="401999001",
        provider_event_id="fd-1",
        players=players,
        by_selection=by_selection,
        rosters_by_team=_rosters(),
        captured_at_utc=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc),
    )
    assert row is not None
    assert row["official_event_id"] == "401999001"
    assert row["official_athlete_id"] == "4431452"
    assert row["official_team_id"] == "27"
    assert row["line"] == 249.5
    assert row["over_odds"] == -110
    assert row["under_odds"] == -110
    assert row["sportsbook"] == "FanDuel"


def test_player_name_is_never_enough_to_resolve_identity():
    player = {"name": "Verified Tampa QB", "team": "TB", "position": "QB"}
    with pytest.raises(collector.NFLPassingYardsCollectorError):
        collector.reconcile_provider_qb(player, _rosters())


def test_ambiguous_team_jersey_qb_identity_fails_closed():
    rosters = _rosters()
    rosters["27"] = rosters["27"] + [
        {
            "team_id": "27",
            "athlete_id": "9999999",
            "jersey": "6",
            "position": "QB",
            "display_name": "Second QB",
        }
    ]
    with pytest.raises(collector.NFLPassingYardsCollectorError):
        collector.reconcile_provider_qb(_players()["qb-provider-key"], rosters)


def test_market_requires_real_two_way_matching_line_and_prices():
    market = _market()
    market["runners"][1]["handicap"] = 250.5
    players = _players()
    by_selection = {"over-1": ["qb-provider-key"], "under-1": ["qb-provider-key"]}
    with pytest.raises(collector.NFLPassingYardsCollectorError):
        collector.normalize_passing_yards_market(
            market,
            official_event_id="401999001",
            provider_event_id="fd-1",
            players=players,
            by_selection=by_selection,
            rosters_by_team=_rosters(),
            captured_at_utc=datetime.now(timezone.utc),
        )


def test_status_contract_locks_market_out_of_projection():
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    response = client.get("/api/v1/nfl/passing-yards/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["projection_weight"] == 0.0
    assert payload["market_context_only"] is True
    assert payload["may_modify_projection"] is False
    assert payload["stake_sizing_enabled"] is False
    assert payload["fuzzy_matching"] is False
    assert payload["player_name_matching"] is False
    assert payload["synthetic_event_ids"] is False
    assert payload["synthetic_player_ids"] is False
    assert payload["wager_actions"] is False


def test_market_endpoint_returns_only_same_official_event(monkeypatch):
    safe_payload = {
        "schema_version": "nfl_passing_yards_market_v1",
        "ready": True,
        "market_available": True,
        "official_event_id": "401999001",
        "sportsbook": "FanDuel",
        "captured_at_utc": "2026-09-12T12:00:00+00:00",
        "props": [],
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
    monkeypatch.setattr(api, "collect_fanduel_nfl_passing_yards", lambda event_id: dict(safe_payload))
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    response = client.get("/api/v1/nfl/passing-yards", params={"event_id": "401999001"})
    assert response.status_code == 200
    assert response.json()["official_event_id"] == "401999001"


def test_market_endpoint_rejects_identity_mismatch(monkeypatch):
    payload = {
        "official_event_id": "401999002",
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
    monkeypatch.setattr(api, "collect_fanduel_nfl_passing_yards", lambda event_id: payload)
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    response = client.get("/api/v1/nfl/passing-yards", params={"event_id": "401999001"})
    assert response.status_code == 503


def test_shared_host_route_table_contains_nfl_passing_yards_without_new_lifespan_router():
    from sports_api.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/nfl/passing-yards" in paths
    assert "/api/v1/nfl/passing-yards/status" in paths
