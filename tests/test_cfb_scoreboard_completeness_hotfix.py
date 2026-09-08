"""Regression checks for CFB NCAA scoreboard completeness hotfix."""
from __future__ import annotations

import json

import cfb_schedule_v3 as schedule


def _game(game_id, away, home, kickoff="2026-09-12T12:00:00-04:00"):
    return {
        "game_id": game_id,
        "identity_key": f"ncaa:{game_id}",
        "identity_fingerprint": f"ncaa:{game_id}",
        "game_date": "2026-09-12",
        "kickoff_iso": kickoff,
        "away_team": away,
        "away_team_slug": away.lower().replace(" ", "-"),
        "home_team": home,
        "home_team_slug": home.lower().replace(" ", "-"),
        "identity_verified": True,
        "date_matches_query": True,
    }


def test_scoreboard_query_uses_current_hash_and_exact_date():
    params = schedule._scoreboard_params("2026-09-12")
    variables = json.loads(params["variables"])
    extensions = json.loads(params["extensions"])

    assert variables == {
        "sportCode": "MFB",
        "division": 11,
        "seasonYear": 2026,
        "contestDate": "2026-09-12",
    }
    assert (
        extensions["persistedQuery"]["sha256Hash"]
        == schedule.NCAA_SCOREBOARD_HASH
    )
    assert schedule.NCAA_SCOREBOARD_HASH.startswith("7287cda6")


def test_official_scoreboard_games_receive_authoritative_markers():
    payload = {
        "data": {
            "contests": [
                {
                    "contestId": "990001",
                    "startDate": "09/12/2026",
                    "startTime": "12:00 PM ET",
                    "gameState": "P",
                    "teams": [
                        {
                            "isHome": False,
                            "nameShort": "Oklahoma",
                            "seoname": "oklahoma",
                            "conferenceSeo": "sec",
                            "teamRank": 10,
                        },
                        {
                            "isHome": True,
                            "nameShort": "Michigan",
                            "seoname": "michigan",
                            "conferenceSeo": "big-ten",
                            "teamRank": 16,
                        },
                    ],
                }
            ]
        }
    }

    games, diag = schedule._official_scoreboard_games(
        payload,
        "2026-09-12",
    )

    assert len(games) == 1
    assert games[0]["identity_key"] == "ncaa:990001"
    assert games[0]["schedule_source"] == "NCAA current FBS scoreboard GraphQL"
    assert games[0]["identity_provider"] == "NCAA"
    assert games[0]["scoreboard_completeness_hotfix"] is True
    assert diag["raw_contests"] == 1


def test_authoritative_ncaa_identity_wins_over_duplicate_fallback():
    official = [_game("100", "Ohio St.", "Texas")]
    fallback = [
        {
            **_game("espn-1", "Ohio St.", "Texas"),
            "identity_key": "espn:401000001",
        },
        _game("101", "Arizona St.", "Texas A&M", "2026-09-12T12:05:00-04:00"),
    ]

    out, diag = schedule._merge_authoritative_scoreboard(
        official,
        fallback,
    )

    assert len(out) == 2
    assert out[0]["identity_key"] == "ncaa:100"
    assert {g["home_team"] for g in out} == {"Texas", "Texas A&M"}
    assert diag["fallback_games_added"] == 1
    assert diag["fallback_duplicates_suppressed"] == 1


def test_hotfix_is_schedule_only():
    assert schedule.FROZEN_SCHEDULE == "cfb_schedule_v2"
    assert schedule.NCAA_SCOREBOARD_DIVISION == 11
