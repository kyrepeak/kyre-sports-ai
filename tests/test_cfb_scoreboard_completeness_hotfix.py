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


def test_authoritative_ncaa_slate_is_atomic_when_available():
    official = [
        _game("100", "Ohio St.", "Texas"),
        _game("101", "Arizona St.", "Texas A&M", "2026-09-12T12:05:00-04:00"),
    ]
    fallback = [
        {
            **_game("espn-1", "Ohio State", "Texas"),
            "identity_key": "espn:401000001",
        },
        _game("espn-2", "Arizona State", "Texas A&M", "2026-09-12T12:05:00-04:00"),
        _game("espn-3", "Western Kentucky", "Georgia", "2026-09-12T12:10:00-04:00"),
    ]

    out, diag = schedule._merge_authoritative_scoreboard(
        official,
        fallback,
    )

    assert len(out) == 2
    assert [g["identity_key"] for g in out] == ["ncaa:100", "ncaa:101"]
    assert diag["fallback_games_added"] == 0
    assert diag["fallback_duplicates_suppressed"] == 3
    assert diag["fallback_mode"] == 0


def test_fallback_is_used_only_when_official_scoreboard_is_empty():
    fallback = [
        _game("200", "Oklahoma", "Michigan"),
        _game("201", "Oregon", "Oklahoma St.", "2026-09-12T12:05:00-04:00"),
    ]

    out, diag = schedule._merge_authoritative_scoreboard([], fallback)

    assert len(out) == 2
    assert diag["official_scoreboard_games"] == 0
    assert diag["fallback_games_added"] == 2
    assert diag["fallback_mode"] == 1


def test_hotfix_is_schedule_only():
    assert schedule.FROZEN_SCHEDULE == "cfb_schedule_v2"
    assert schedule.NCAA_SCOREBOARD_DIVISION == 11
