from __future__ import annotations

import importlib


def _event_page_payload():
    return {
        "attachments": {
            "markets": {
                "m1": {
                    "marketId": "m1",
                    "marketName": "Player Passing Yards",
                    "marketType": "PLAYER_PASSING_YARDS",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        {
                            "selectionId": "s-over",
                            "runnerStatus": "ACTIVE",
                            "handicap": 244.5,
                            "result": {"type": "OVER"},
                            "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
                        },
                        {
                            "selectionId": "s-under",
                            "runnerStatus": "ACTIVE",
                            "handicap": 244.5,
                            "result": {"type": "UNDER"},
                            "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
                        },
                    ],
                }
            }
        }
    }


def _fdx_payload():
    return {
        "playerMap": {
            "p1": {
                "name": "Drake Maye",
                "team": "NE",
                "position": "QB",
                "selectionIds": ["s-over", "s-under"],
            }
        }
    }


def test_successor_parses_current_fanduel_result_roles_and_american_odds_int():
    market = importlib.import_module("sports_api.collectors.nfl_fanduel_passing_yards_nflverse_v1")
    rows = market.parse_event_market_observations(_event_page_payload(), _fdx_payload(), source_timestamp="2026-10-22T18:50:00Z")
    assert rows == [{
        "player_name": "Drake Maye",
        "team_abbr": "NE",
        "sportsbook": "FanDuel",
        "market": "Passing Yards",
        "line": 244.5,
        "over_odds": -110,
        "under_odds": -110,
        "source_timestamp": "2026-10-22T18:50:00Z",
        "provider_market_id": "m1",
        "source_provider": "FanDuel direct",
    }]


def test_successor_rejects_closed_inplay_or_one_sided_markets_without_fabrication():
    market = importlib.import_module("sports_api.collectors.nfl_fanduel_passing_yards_nflverse_v1")
    payload = _event_page_payload()
    row = payload["attachments"]["markets"]["m1"]
    row["marketStatus"] = "CLOSED"
    assert market.parse_event_market_observations(payload, _fdx_payload(), source_timestamp="2026-10-22T18:50:00Z") == []
    row["marketStatus"] = "OPEN"
    row["runners"] = row["runners"][:1]
    assert market.parse_event_market_observations(payload, _fdx_payload(), source_timestamp="2026-10-22T18:50:00Z") == []


def test_successor_has_no_banned_provider_dependency():
    market = importlib.import_module("sports_api.collectors.nfl_fanduel_passing_yards_nflverse_v1")
    source = market.__file__
    text = open(source, encoding="utf-8").read()
    assert "ESPN" not in text.upper()
    assert "SGO" not in text.upper()


def test_slate_prefers_successor_fanduel_parser_and_falls_back_only_when_needed(monkeypatch):
    slate = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    direct = [{
        "player_name": "Drake Maye", "team_abbr": "NE", "sportsbook": "FanDuel",
        "market": "Passing Yards", "line": 244.5, "over_odds": -110, "under_odds": -110,
        "source_timestamp": "2026-10-22T18:50:00Z", "provider_market_id": "m1",
        "source_provider": "FanDuel direct",
    }]
    game = {"away":"NE", "home":"CHI", "away_name":"New England Patriots", "home_name":"Chicago Bears"}
    monkeypatch.setattr(slate.market_fill, "collect_fanduel_game_markets", lambda game: direct)
    monkeypatch.setattr(slate.base, "collect_market_observations", lambda game: (_ for _ in ()).throw(AssertionError("fallback should not run")))
    assert slate._collect_market_observations(game) == direct

    monkeypatch.setattr(slate.market_fill, "collect_fanduel_game_markets", lambda game: [])
    monkeypatch.setattr(slate.base, "collect_market_observations", lambda game: [{"sportsbook":"The Odds API", "line":245.5}])
    assert slate._collect_market_observations(game) == [{"sportsbook":"The Odds API", "line":245.5}]


def test_market_listed_qb_reconciliation_uses_unique_team_nflverse_identity():
    slate = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    rows = [
        {"team":"ATL", "qb_name":"C.Rush", "player_source_id":"00-1", "attempts":20},
        {"team":"ATL", "qb_name":"M.Penix", "player_source_id":"00-2", "attempts":35},
        {"team":"PHI", "qb_name":"J.Hurts", "player_source_id":"00-3", "attempts":31},
        {"team":"PHI", "qb_name":"T.McKee", "player_source_id":"00-4", "attempts":48},
        {"team":"NYG", "qb_name":"J.Winston", "player_source_id":"00-5", "attempts":30},
        {"team":"NYG", "qb_name":"J.McCarthy", "player_source_id":"00-6", "attempts":24},
    ]
    observations = [
        {"team_abbr":"ATL", "player_name":"Michael Penix Jr."},
        {"team_abbr":"PHI", "player_name":"Tanner McKee"},
        {"team_abbr":"NYG", "player_name":"J.J McCarthy"},
    ]
    atl = slate._current_rows_for_market_qb("ATL", rows, observations)
    phi = slate._current_rows_for_market_qb("PHI", rows, observations)
    nyg = slate._current_rows_for_market_qb("NYG", rows, observations)
    assert {r["player_source_id"] for r in atl if r["team"] == "ATL"} == {"00-2"}
    assert {r["player_source_id"] for r in phi if r["team"] == "PHI"} == {"00-4"}
    assert {r["player_source_id"] for r in nyg if r["team"] == "NYG"} == {"00-6"}


def test_market_qb_reconciliation_fails_closed_on_ambiguous_identity():
    slate = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    rows = [
        {"team":"ATL", "qb_name":"M.Penix", "player_source_id":"00-2", "attempts":35},
        {"team":"ATL", "qb_name":"M.Penix", "player_source_id":"00-9", "attempts":1},
    ]
    observations = [{"team_abbr":"ATL", "player_name":"Michael Penix Jr."}]
    assert slate._current_rows_for_market_qb("ATL", rows, observations) == rows
