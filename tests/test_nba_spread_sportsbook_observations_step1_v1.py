from __future__ import annotations

import importlib


def _module():
    return importlib.import_module("nba_spread_sportsbook_observations_v1")


def _schedule():
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "status": "UPCOMING",
        }
    ]


def _events():
    return [
        {
            "teams": {
                "away": {"names": {"long": "Los Angeles Lakers"}},
                "home": {"names": {"long": "Phoenix Suns"}},
            },
            "odds": {
                "away": {
                    "periodID": "game",
                    "betTypeID": "sp",
                    "sideID": "away",
                    "byBookmaker": {
                        "draftkings": {"available": True, "spread": 2.5},
                        "fanduel": {"available": True, "spread": 3.0},
                    },
                },
                "home": {
                    "periodID": "game",
                    "betTypeID": "sp",
                    "sideID": "home",
                    "byBookmaker": {
                        "draftkings": {"available": True, "spread": -2.5},
                        "fanduel": {"available": True, "spread": -3.0},
                    },
                },
            },
        }
    ]


def test_normalizes_two_independent_exact_spread_pairs():
    module = _module()
    rows = module.normalize_sportsgameodds_spread_observations(_events(), _schedule())
    assert rows == [
        {"away_tricode": "LAL", "home_tricode": "PHX", "sportsbook": "DraftKings", "away_spread": 2.5, "home_spread": -2.5},
        {"away_tricode": "LAL", "home_tricode": "PHX", "sportsbook": "FanDuel", "away_spread": 3.0, "home_spread": -3.0},
    ]


def test_rejects_partial_or_non_opposite_spread_pairs():
    module = _module()
    events = _events()
    events[0]["odds"]["home"]["byBookmaker"]["draftkings"]["spread"] = -3.5
    del events[0]["odds"]["home"]["byBookmaker"]["fanduel"]
    assert module.normalize_sportsgameodds_spread_observations(events, _schedule()) == []


def test_fetch_fails_closed_without_credential(monkeypatch):
    module = _module()
    monkeypatch.delenv("SPORTSGAMEODDS_API_KEY", raising=False)
    result = module.load_verified_sportsbook_observations(_schedule(), secret_getter=lambda name: None)
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"
    assert result["observations"] == []
    assert result["fabrication"] is False


def test_fetch_uses_nba_full_game_spreads_and_returns_exact_observations(monkeypatch):
    module = _module()
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": _events()}

    def fake_get(url, *, params, headers, timeout):
        seen.update(url=url, params=params, headers=headers, timeout=timeout)
        return Response()

    result = module.load_verified_sportsbook_observations(
        _schedule(),
        secret_getter=lambda name: "secret" if name == "SPORTSGAMEODDS_API_KEY" else None,
        request_get=fake_get,
    )
    assert result["verification"] == "VERIFIED"
    assert len(result["observations"]) == 2
    assert seen["params"]["leagueID"] == "NBA"
    assert seen["params"]["oddID"] == "points-away-game-sp-away,points-home-game-sp-home"
    assert seen["headers"] == {"x-api-key": "secret"}
    assert result["fabrication"] is False
    assert result["page_wide_source_authority"] is False
