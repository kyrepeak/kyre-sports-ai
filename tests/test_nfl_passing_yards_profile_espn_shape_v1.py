import math

import nfl_passing_yards_profile_v1 as profile


def _espn_season_payload(*, games=17, use_team_games=False, passing_yards=3693, attempts=543, completions=343):
    game_name = "teamGamesPlayed" if use_team_games else "gamesPlayed"
    general_stats = [] if use_team_games else [{"name": game_name, "value": games}]
    passing_stats = [
        {"name": "completions", "abbreviation": "CMP", "value": completions},
        {"name": "passingAttempts", "abbreviation": "ATT", "value": attempts},
        {"name": "passingYards", "abbreviation": "YDS", "value": passing_yards},
        {"name": "passingTouchdowns", "abbreviation": "TD", "value": 26},
        {"name": "interceptions", "abbreviation": "INT", "value": 11},
        {"name": "completionPct", "abbreviation": "CMP%", "value": 63.2},
        {"name": "yardsPerPassAttempt", "abbreviation": "AVG", "value": 6.8},
    ]
    if use_team_games:
        passing_stats.insert(0, {"name": game_name, "abbreviation": "TGP", "value": games})
    return {
        "splits": {
            "categories": [
                {"name": "general", "stats": general_stats},
                {
                    "name": "rushing",
                    "stats": [
                        {"name": "rushingYards", "abbreviation": "YDS", "value": 9999},
                        {"name": "rushingTouchdowns", "abbreviation": "TD", "value": 99},
                        {"name": "yardsPerRushAttempt", "abbreviation": "AVG", "value": 99.0},
                    ],
                },
                {"name": "passing", "stats": passing_stats},
            ]
        }
    }


def test_parse_season_passing_recovers_games_from_general_without_stat_collisions():
    row = profile.parse_season_passing(_espn_season_payload())

    assert row["ready"] is True
    assert row["games"] == 17
    assert row["attempts"] == 543
    assert row["completions"] == 343
    assert row["passing_yards"] == 3693
    assert row["yards_per_attempt"] == 6.8
    assert math.isclose(row["attempts_per_game"], 543 / 17)
    assert math.isclose(row["yards_per_game"], 3693 / 17)


def test_parse_season_passing_accepts_team_games_played_from_passing_category():
    row = profile.parse_season_passing(_espn_season_payload(games=16, use_team_games=True))

    assert row["ready"] is True
    assert row["games"] == 16
    assert row["attempts"] == 543
    assert row["passing_yards"] == 3693


def test_build_qb_profile_uses_verified_prior_regular_season_when_current_sample_empty(monkeypatch):
    empty_current = {
        "splits": {
            "categories": [
                {"name": "general", "stats": [{"name": "gamesPlayed", "value": 0}]},
                {"name": "passing", "stats": []},
            ]
        }
    }
    prior = _espn_season_payload()

    def fake_season_loader(year, season_type, athlete_id):
        payload = prior if int(year) == 2025 else empty_current
        return payload, {"ok": True, "http": 200}

    def fake_gamelog_loader(year, athlete_id):
        return {}, {"ok": True, "http": 200}

    monkeypatch.setattr(profile, "_season_stats_payload", fake_season_loader)
    monkeypatch.setattr(profile, "_gamelog_payload", fake_gamelog_loader)

    row = profile.build_qb_profile("3052587", "Baker Mayfield", 2026, 2)

    assert row["ready"] is True
    assert row["season_year"] == 2025
    assert row["early_season_fallback"] is True
    assert row["season"]["games"] == 17
    assert row["season"]["attempts"] == 543
