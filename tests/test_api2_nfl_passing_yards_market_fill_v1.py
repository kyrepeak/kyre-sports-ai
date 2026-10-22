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
