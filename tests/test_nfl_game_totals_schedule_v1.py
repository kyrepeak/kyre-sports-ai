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


def test_schedule_parser_preserves_exact_official_identity():
    payload = parse_espn_scoreboard(_scoreboard(), "2026-09-20")
    assert payload["schema_version"] == "nfl_game_totals_schedule_v1"
    assert payload["requested_date"] == "2026-09-20"
    assert payload["game_count"] == 1
    game = payload["games"][0]
    assert game["official_event_id"] == "401772714"
    assert game["away"] == {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"}
    assert game["home"] == {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"}
    assert game["status"]["pregame"] is True
    assert game["identity_policy"]["fuzzy_matching"] is False
    assert game["identity_policy"]["synthetic_event_ids"] is False


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
    payload["events"].append(payload["events"][0].copy())
    with pytest.raises(NFLGameTotalsScheduleError):
        parse_espn_scoreboard(payload, "2026-09-20")


def test_schedule_fails_closed_on_missing_exact_home_away_identity():
    payload = _scoreboard()
    payload["events"][0]["competitions"][0]["competitors"] = payload["events"][0]["competitions"][0]["competitors"][:1]
    with pytest.raises(NFLGameTotalsScheduleError):
        parse_espn_scoreboard(payload, "2026-09-20")
