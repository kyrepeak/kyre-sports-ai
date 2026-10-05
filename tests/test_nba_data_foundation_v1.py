from __future__ import annotations

from datetime import datetime

import pytest

import nba_data_foundation_v1 as nba


def _espn_event(*, event_id: str = "401000001", home: str = "PHX", away: str = "LAL", state: str = "pre") -> dict:
    return {
        "id": event_id,
        "date": "2026-10-24T02:00:00Z",
        "status": {"type": {"state": state, "description": "Scheduled" if state == "pre" else state}},
        "competitions": [
            {
                "venue": {"fullName": "Footprint Center", "address": {"city": "Phoenix"}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"id": "21", "abbreviation": home, "displayName": "Phoenix Suns" if home == "PHX" else home},
                        "records": [{"type": "total", "summary": "2-0"}],
                    },
                    {
                        "homeAway": "away",
                        "team": {"id": "13", "abbreviation": away, "displayName": "Los Angeles Lakers" if away == "LAL" else away},
                        "records": [{"type": "total", "summary": "1-1"}],
                    },
                ],
            }
        ],
    }


def _official_game(*, game_id: str = "0022600001", home: str = "PHX", away: str = "LAL", status: int = 1) -> dict:
    return {
        "gameId": game_id,
        "gameStatus": status,
        "gameStatusText": "7:00 pm ET" if status == 1 else "Final",
        "gameDateTimeUTC": "2026-10-24T02:00:00Z",
        "arenaName": "Footprint Center",
        "arenaCity": "Phoenix",
        "homeTeam": {"teamId": 1610612756, "teamTricode": home, "teamName": "Suns", "wins": 2, "losses": 0},
        "awayTeam": {"teamId": 1610612747, "teamTricode": away, "teamName": "Lakers", "wins": 1, "losses": 1},
    }


def _official_payload(games: list[dict]) -> dict:
    return {"leagueSchedule": {"gameDates": [{"gameDate": "10/23/2026 12:00:00 AM", "games": games}]}}


def _odds_payload() -> list[dict]:
    return [
        {
            "id": "odds-1",
            "sport_key": "basketball_nba",
            "commence_time": "2026-10-24T02:00:00Z",
            "home_team": "Phoenix Suns",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "last_update": "2026-10-24T00:15:00Z",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": -110, "point": 228.5},
                                {"name": "Under", "price": -110, "point": 228.5},
                            ],
                        }
                    ],
                }
            ],
        }
    ]


def test_source_contract_is_nba_only_and_projection_neutral():
    contract = nba.source_contract()
    assert contract["sport"] == "NBA"
    assert contract["schedule_primary"] == "NBA_OFFICIAL_CDN"
    assert contract["schedule_fallback"] == "ESPN_NBA_SCOREBOARD"
    assert contract["odds_provider"] == "THE_ODDS_API"
    assert contract["odds_sport_key"] == "basketball_nba"
    assert contract["odds_market"] == "totals"
    assert contract["timezone"] == "America/Phoenix"
    assert contract["projection_influence"] == 0.0
    assert contract["sportsbook_projection_influence"] == 0.0
    assert contract["other_sports_allowed"] is False


def test_phoenix_time_is_fixed_to_arizona_offset_year_round():
    winter = nba.to_phoenix_time("2026-01-15T03:00:00Z")
    summer = nba.to_phoenix_time("2026-07-15T03:00:00Z")
    assert winter.endswith("-07:00")
    assert summer.endswith("-07:00")


def test_official_schedule_normalizes_records_venue_and_phoenix_tip():
    rows = nba.normalize_official_schedule(_official_payload([_official_game()]), "2026-10-23")
    assert len(rows) == 1
    row = rows[0]
    assert row["game_id"] == "0022600001"
    assert row["status"] == "UPCOMING"
    assert row["home_abbr"] == "PHX"
    assert row["away_abbr"] == "LAL"
    assert row["home_record"] == "2-0"
    assert row["away_record"] == "1-1"
    assert row["arena"] == "Footprint Center"
    assert row["city"] == "Phoenix"
    assert row["tip_phoenix"].endswith("-07:00")
    assert row["source"] == "NBA_OFFICIAL_CDN"


def test_espn_normalizer_rejects_non_nba_team_pairs():
    payload = {"events": [_espn_event(), _espn_event(event_id="wnba-like", home="SEA", away="LV")]}
    rows = nba.normalize_espn_schedule(payload, "2026-10-23")
    assert [row["game_id"] for row in rows] == ["401000001"]
    assert rows[0]["source"] == "ESPN_NBA_SCOREBOARD"


def test_valid_primary_off_day_does_not_fall_through_to_espn():
    class FakeHTTP:
        def __init__(self):
            self.calls = []

        def get_json(self, url, *, params=None, headers=None, timeout=8):
            self.calls.append((url, params))
            if url == nba.NBA_OFFICIAL_SCHEDULE_URL:
                return _official_payload([])
            raise AssertionError("fallback should not be called for a valid official off-day")

    client = nba.NBADataClient(FakeHTTP())
    assert client.schedule_for_date("2026-10-23") == []


def test_primary_transport_failure_uses_espn_fallback_only():
    class FakeHTTP:
        def __init__(self):
            self.calls = []

        def get_json(self, url, *, params=None, headers=None, timeout=8):
            self.calls.append((url, params))
            if url == nba.NBA_OFFICIAL_SCHEDULE_URL:
                raise RuntimeError("official unavailable")
            if url == nba.ESPN_SCOREBOARD_URL:
                return {"events": [_espn_event()]}
            raise AssertionError(url)

    http = FakeHTTP()
    rows = nba.NBADataClient(http).schedule_for_date("2026-10-23")
    assert len(rows) == 1
    assert rows[0]["source"] == "ESPN_NBA_SCOREBOARD"
    assert [url for url, _ in http.calls] == [nba.NBA_OFFICIAL_SCHEDULE_URL, nba.ESPN_SCOREBOARD_URL]


def test_totals_normalizer_keeps_complete_nba_over_under_markets_only():
    bad = {
        "id": "bad",
        "sport_key": "basketball_wnba",
        "commence_time": "2026-10-24T02:00:00Z",
        "home_team": "Phoenix Mercury",
        "away_team": "Las Vegas Aces",
        "bookmakers": [],
    }
    rows = nba.normalize_totals_odds(_odds_payload() + [bad])
    assert rows == [
        {
            "event_id": "odds-1",
            "home_team": "Phoenix Suns",
            "away_team": "Los Angeles Lakers",
            "commence_time_utc": "2026-10-24T02:00:00Z",
            "tip_phoenix": "2026-10-23T19:00:00-07:00",
            "bookmaker_key": "draftkings",
            "bookmaker": "DraftKings",
            "market_total": 228.5,
            "over_price": -110,
            "under_price": -110,
            "last_update": "2026-10-24T00:15:00Z",
            "source": "THE_ODDS_API",
        }
    ]


def test_odds_client_requires_key_and_requests_only_nba_totals():
    class FakeHTTP:
        def __init__(self):
            self.calls = []

        def get_json(self, url, *, params=None, headers=None, timeout=8):
            self.calls.append((url, params))
            return _odds_payload()

    http = FakeHTTP()
    client = nba.NBADataClient(http)
    with pytest.raises(nba.NBADataSourceError, match="API key"):
        client.totals_odds("")

    rows = client.totals_odds("secret")
    assert len(rows) == 1
    url, params = http.calls[-1]
    assert url == nba.THE_ODDS_API_URL
    assert params == {
        "apiKey": "secret",
        "regions": "us",
        "markets": "totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
