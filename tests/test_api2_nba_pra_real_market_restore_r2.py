from datetime import date
import importlib
from pathlib import Path
import sys
import types

import sports_api as sports_api_pkg

_api_pkg = types.ModuleType("sports_api.api")
_api_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "sports_api" / "api")]
_api_pkg.__package__ = "sports_api.api"
sys.modules["sports_api.api"] = _api_pkg
setattr(sports_api_pkg, "api", _api_pkg)

import nba_pra_market_api_v1 as client


def _odds_event():
    return {
        "id": "evt-1",
        "sport_key": "basketball_nba",
        "commence_time": "2026-10-25T02:10:00Z",
        "away_team": "Washington Wizards",
        "home_team": "Phoenix Suns",
        "bookmakers": [
            {
                "key": "betmgm",
                "title": "BetMGM",
                "last_update": "2026-10-24T05:00:00Z",
                "markets": [
                    {
                        "key": "player_points_rebounds_assists",
                        "last_update": "2026-10-24T05:00:00Z",
                        "outcomes": [
                            {"name": "Over", "description": "Anthony Davis", "price": -115, "point": 41.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -105, "point": 41.5},
                        ],
                    }
                ],
            },
            {
                "key": "espnbet",
                "title": "ESPN BET",
                "last_update": "2026-10-24T05:00:00Z",
                "markets": [
                    {
                        "key": "player_points_rebounds_assists",
                        "outcomes": [
                            {"name": "Over", "description": "Anthony Davis", "price": -110, "point": 41.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -110, "point": 41.5},
                        ],
                    }
                ],
            },
        ],
    }


def test_successor_normalizes_exact_the_odds_api_pra_and_excludes_banned_books():
    api = importlib.import_module("sports_api.api.nba_pra_market_real_restore_v1")
    rows = api.normalize_the_odds_api_pra_event(_odds_event(), slate_date=date(2026, 10, 24))
    assert len(rows) == 2
    assert {row["side"] for row in rows} == {"over", "under"}
    assert {row["sportsbook"] for row in rows} == {"BetMGM"}
    assert {row["provider"] for row in rows} == {"The Odds API"}
    assert {row["line"] for row in rows} == {41.5}
    assert {row["price"] for row in rows} == {-115, -105}
    assert all(row["away_team"] == "Washington Wizards" for row in rows)
    assert all(row["home_team"] == "Phoenix Suns" for row in rows)


def test_successor_fetches_nonfeatured_pra_per_event_only_after_event_discovery():
    api = importlib.import_module("sports_api.api.nba_pra_market_real_restore_v1")
    calls = []

    class Response:
        def __init__(self, payload): self._payload = payload
        def raise_for_status(self): return None
        def json(self): return self._payload

    def fake_get(url, *, params, timeout):
        calls.append((url, dict(params)))
        if url.endswith("/sports/basketball_nba/events"):
            return Response([{
                "id": "evt-1",
                "commence_time": "2026-10-25T02:10:00Z",
                "away_team": "Washington Wizards",
                "home_team": "Phoenix Suns",
            }])
        assert url.endswith("/sports/basketball_nba/events/evt-1/odds")
        return Response(_odds_event())

    rows, state = api.fetch_the_odds_api_pra_observations(
        date(2026, 10, 24), api_key="secret", request_get=fake_get
    )
    assert state == "THE_ODDS_API_OK"
    assert len(rows) == 2
    assert len(calls) == 2
    assert calls[1][1]["markets"] == "player_points_rebounds_assists"
    assert calls[1][1]["regions"] == "us"
    assert "espnbet" not in calls[1][1]["bookmakers"]


def test_successor_uses_aggregator_only_when_frozen_direct_route_has_no_market():
    api = importlib.import_module("sports_api.api.nba_pra_market_real_restore_v1")
    base = {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v2_provider_independence",
        "sport": "nba", "market": "points+rebounds+assists", "date": "2026-10-24",
        "ready": False, "verification": "UNAVAILABLE",
        "diagnostic_state": "MARKET_NOT_POSTED_YET",
        "global_market_state_reason": "UPCOMING_MARKET_NOT_POSTED_YET",
        "player_count": 0, "observation_count": 0, "observations": [],
        "provider_health": [
            {"provider": "FanDuel", "state": "FANDUEL_NO_PRA", "observation_count": 0},
            {"provider": "DraftKings", "state": "DRAFTKINGS_ACCESS_FAILURE:HTTPStatusError", "observation_count": 0},
        ],
        "provider_route_audit": [],
        "recent_participant_profiles": {"anthonydavis": {"player_name": "Anthony Davis", "team": "WAS"}},
        "recent_participant_state": "RECENT_PARTICIPANTS_1",
        "projection_weight": 0.0, "sportsbook_projection_influence": 0.0,
        "consensus_averaging": False, "fabrication": False,
    }
    calls = []
    def direct_loader(_day): return dict(base)
    def odds_loader(_day, *, api_key, request_get=None):
        calls.append(api_key)
        return [
            {"provider":"The Odds API","player_name":"Anthony Davis","sportsbook":"BetMGM","side":"over","line":41.5,"price":-115,"observed_at_utc":"2026-10-24T05:00:00Z","away_team":"Washington Wizards","home_team":"Phoenix Suns"},
            {"provider":"The Odds API","player_name":"Anthony Davis","sportsbook":"BetMGM","side":"under","line":41.5,"price":-105,"observed_at_utc":"2026-10-24T05:00:00Z","away_team":"Washington Wizards","home_team":"Phoenix Suns"},
        ], "THE_ODDS_API_OK"
    out = api.collect_nba_pra_market(
        date(2026, 10, 24), the_odds_api_key="secret",
        direct_loader=direct_loader, odds_loader=odds_loader,
    )
    assert calls == ["secret"]
    assert out["ready"] is True
    assert out["diagnostic_state"] == "OK"
    assert out["observation_count"] == 2
    assert out["recent_participant_profiles"] == base["recent_participant_profiles"]
    assert out["fabrication"] is False
    assert out["consensus_averaging"] is False


def test_streamlit_client_forwards_provider_credential_only_in_header_not_body():
    captured = {}
    class Response:
        def raise_for_status(self): return None
        def json(self):
            return {"projection_weight":0.0,"consensus_averaging":False,"observations":[],"diagnostic_state":"THE_ODDS_API_NO_PRA"}
    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Response()
    client.load_kyre_sports_api_pra_observations(
        date(2026, 10, 24), api_key="super-secret", request_post=fake_post,
    )
    assert captured["headers"]["X-Kyre-The-Odds-Api-Key"] == "super-secret"
    assert captured["json"] == {"date": "2026-10-24"}
    assert "super-secret" not in repr(captured["json"])
