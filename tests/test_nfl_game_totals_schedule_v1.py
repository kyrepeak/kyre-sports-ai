from copy import deepcopy
from datetime import date

import pytest

from sports_api.collectors.nfl_game_totals_schedule_v1 import (
    NFLGameTotalsScheduleError,
    collect_official_nfl_slate,
    parse_espn_scoreboard,
)


def _scoreboard():
    return {
        "events": [
            {
                "id": "401772714",
                "date": "2026-09-20T17:00:00Z",
                "competitions": [
                    {
                        "id": "401772714",
                        "date": "2026-09-20T17:00:00Z",
                        "neutralSite": False,
                        "venue": {
                            "fullName": "Highmark Stadium",
                            "indoor": False,
                            "address": {"city": "Orchard Park", "state": "NY"},
                        },
                        "status": {
                            "type": {
                                "state": "pre",
                                "completed": False,
                                "detail": "Sun, September 20",
                            }
                        },
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "id": "8",
                                    "abbreviation": "DET",
                                    "displayName": "Detroit Lions",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {
                                    "id": "2",
                                    "abbreviation": "BUF",
                                    "displayName": "Buffalo Bills",
                                },
                            },
                        ],
                    }
                ],
            }
        ]
    }


def test_schedule_parser_preserves_exact_official_identity_and_venue():
    payload = parse_espn_scoreboard(_scoreboard(), "2026-09-20")
    assert payload["schema_version"] == "nfl_game_totals_schedule_v1"
    assert payload["requested_date"] == "2026-09-20"
    assert payload["game_count"] == 1
    assert payload["venue_available_count"] == 1
    assert payload["venue_missing_count"] == 0
    game = payload["games"][0]
    assert game["official_event_id"] == "401772714"
    assert game["away"] == {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"}
    assert game["home"] == {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"}
    assert game["status"]["pregame"] is True
    assert game["venue"] == {
        "available": True,
        "name": "Highmark Stadium",
        "city": "Orchard Park",
        "state": "NY",
        "indoor": False,
    }
    assert game["neutral_site"] is False
    assert game["identity_policy"]["fuzzy_matching"] is False
    assert game["identity_policy"]["synthetic_event_ids"] is False


def test_missing_venue_keeps_official_game_in_slate():
    source = deepcopy(_scoreboard())
    source["events"][0]["competitions"][0].pop("venue")
    payload = parse_espn_scoreboard(source, "2026-09-20")
    assert payload["game_count"] == 1
    assert payload["venue_available_count"] == 0
    assert payload["venue_missing_count"] == 1
    assert payload["games"][0]["venue"] == {
        "available": False,
        "name": None,
        "city": None,
        "state": None,
        "indoor": None,
    }


def test_schedule_collector_accepts_injected_network_free_fetcher():
    payload = collect_official_nfl_slate(
        date(2026, 9, 20),
        fetcher=lambda requested: (_scoreboard(), "fixture://espn"),
    )
    assert payload["source"] == "fixture://espn"
    assert payload["game_count"] == 1


def test_schedule_fails_closed_on_non_numeric_event_id():
    payload = _scoreboard()
    payload["events"][0]["id"] = "fake-event"
    with pytest.raises(NFLGameTotalsScheduleError):
        parse_espn_scoreboard(payload, "2026-09-20")


def test_schedule_fails_closed_on_duplicate_event_id():
    payload = _scoreboard()
    payload["events"].append(deepcopy(payload["events"][0]))
    with pytest.raises(NFLGameTotalsScheduleError):
        parse_espn_scoreboard(payload, "2026-09-20")


def test_schedule_fails_closed_on_missing_exact_home_away_identity():
    payload = _scoreboard()
    payload["events"][0]["competitions"][0]["competitors"] = payload["events"][0]["competitions"][0]["competitors"][:1]
    with pytest.raises(NFLGameTotalsScheduleError):
        parse_espn_scoreboard(payload, "2026-09-20")
