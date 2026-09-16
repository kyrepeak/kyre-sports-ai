from __future__ import annotations

import math

import pandas as pd

from sports_api.nfl_data_nflverse_v1 import (
    canonical_team_abbr,
    derive_explosive_metrics,
    derive_pace_metrics,
    derive_red_zone_drive_metrics,
    extract_scoring_games,
)


def test_extract_scoring_games_returns_only_completed_regular_games_before_cutoff():
    frame = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_type": "REG",
                "gameday": "2026-09-10",
                "away_team": "BUF",
                "home_team": "NYJ",
                "away_score": 27,
                "home_score": 17,
            },
            {
                "season": 2026,
                "game_type": "REG",
                "gameday": "2026-09-20",
                "away_team": "BUF",
                "home_team": "MIA",
                "away_score": 0,
                "home_score": 0,
            },
            {
                "season": 2026,
                "game_type": "POST",
                "gameday": "2026-09-01",
                "away_team": "BUF",
                "home_team": "KC",
                "away_score": 24,
                "home_score": 21,
            },
        ]
    )

    rows = extract_scoring_games(frame, "BUF", 2026, "2026-09-15")

    assert rows == [
        {
            "date": "2026-09-10",
            "pf": 27.0,
            "pa": 17.0,
            "opponent_abbr": "NYJ",
        }
    ]


def test_canonical_team_abbr_normalizes_known_historical_aliases():
    assert canonical_team_abbr("JAC") == "JAX"
    assert canonical_team_abbr("STL") == "LAR"
    assert canonical_team_abbr("OAK") == "LV"
    assert canonical_team_abbr("WSH") == "WAS"
    assert canonical_team_abbr("BUF") == "BUF"


def _sample_pbp() -> pd.DataFrame:
    rows = [
        # BUF drive 1: six valid offensive plays, 900 seconds possession, RZ TD.
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 3600, "play_type": "run", "rush_attempt": 1, "pass_attempt": 0, "sack": 0, "yards_gained": 25, "complete_pass": 0, "no_play": 0, "yardline_100": 75, "touchdown": 0, "down": 1, "third_down_converted": 0, "third_down_failed": 0, "first_down": 1},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 3450, "play_type": "pass", "rush_attempt": 0, "pass_attempt": 1, "sack": 0, "yards_gained": 21, "complete_pass": 1, "no_play": 0, "yardline_100": 50, "touchdown": 0, "down": 3, "third_down_converted": 1, "third_down_failed": 0, "first_down": 1},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 3300, "play_type": "pass", "rush_attempt": 0, "pass_attempt": 1, "sack": 0, "yards_gained": 8, "complete_pass": 1, "no_play": 0, "yardline_100": 18, "touchdown": 0, "down": 2, "third_down_converted": 0, "third_down_failed": 0, "first_down": 0},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 3150, "play_type": "pass", "rush_attempt": 0, "pass_attempt": 1, "sack": 0, "yards_gained": 30, "complete_pass": 1, "no_play": 0, "yardline_100": 10, "touchdown": 1, "down": 1, "third_down_converted": 0, "third_down_failed": 0, "first_down": 1},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 3000, "play_type": "run", "rush_attempt": 1, "pass_attempt": 0, "sack": 0, "yards_gained": 4, "complete_pass": 0, "no_play": 0, "yardline_100": 40, "touchdown": 0, "down": 3, "third_down_converted": 0, "third_down_failed": 1, "first_down": 0},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 1, "qtr": 1, "game_seconds_remaining": 2700, "play_type": "sack", "rush_attempt": 0, "pass_attempt": 0, "sack": 1, "yards_gained": -6, "complete_pass": 0, "no_play": 0, "yardline_100": 45, "touchdown": 0, "down": 3, "third_down_converted": 0, "third_down_failed": 1, "first_down": 0},
        # BUF drive 2: second 900-second possession, reaches red zone but no TD.
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 2, "qtr": 3, "game_seconds_remaining": 1800, "play_type": "no_play", "rush_attempt": 0, "pass_attempt": 0, "sack": 0, "yards_gained": 50, "complete_pass": 0, "no_play": 1, "yardline_100": 19, "touchdown": 0, "down": 1, "third_down_converted": 0, "third_down_failed": 0, "first_down": 0},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 2, "qtr": 3, "game_seconds_remaining": 1650, "play_type": "run", "rush_attempt": 1, "pass_attempt": 0, "sack": 0, "yards_gained": 3, "complete_pass": 0, "no_play": 0, "yardline_100": 20, "touchdown": 0, "down": 3, "third_down_converted": 0, "third_down_failed": 1, "first_down": 0},
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "BUF", "defteam": "NYJ", "drive": 2, "qtr": 3, "game_seconds_remaining": 900, "play_type": "pass", "rush_attempt": 0, "pass_attempt": 1, "sack": 0, "yards_gained": 5, "complete_pass": 1, "no_play": 0, "yardline_100": 17, "touchdown": 0, "down": 3, "third_down_converted": 1, "third_down_failed": 0, "first_down": 1},
        # NYJ row must not contaminate BUF metrics.
        {"game_id": "g1", "season": 2026, "season_type": "REG", "posteam": "NYJ", "defteam": "BUF", "drive": 3, "qtr": 2, "game_seconds_remaining": 2400, "play_type": "run", "rush_attempt": 1, "pass_attempt": 0, "sack": 0, "yards_gained": 50, "complete_pass": 0, "no_play": 0, "yardline_100": 50, "touchdown": 0, "down": 1, "third_down_converted": 0, "third_down_failed": 0, "first_down": 1},
    ]
    return pd.DataFrame(rows)


def test_derive_pace_counts_valid_offensive_plays_and_unique_drive_possession():
    metrics = derive_pace_metrics(_sample_pbp(), team_abbr="BUF")

    assert metrics["ready"] is True
    assert metrics["games_played"] == 1
    # 8 valid BUF offensive plays; no-play row excluded.
    assert metrics["plays_per_game"] == 8.0
    # Drive 1 spans 900 sec (3600 -> 2700), drive 2 spans 900 sec (1800 -> 900).
    assert metrics["possession_seconds_per_game"] == 1800.0


def test_derive_explosive_metrics_uses_20_plus_yard_canonical_definition():
    metrics = derive_explosive_metrics(_sample_pbp(), "BUF")

    assert metrics["ready"] is True
    assert metrics["games_played"] == 1
    assert metrics["rushing_big_plays"] == 1.0
    assert metrics["receiving_big_plays"] == 2.0
    assert metrics["total_big_plays"] == 3.0
    assert metrics["explosive_plays_per_game"] == 3.0


def test_derive_red_zone_drive_metrics_uses_unique_drives_and_valid_third_downs():
    metrics = derive_red_zone_drive_metrics(_sample_pbp(), "BUF")

    assert metrics["ready"] is True
    # Two BUF drives reach the red zone; only drive 1 scores a TD.
    assert metrics["red_zone_td_pct"] == 50.0
    # Five valid third-down plays: 2 conversions, 3 failures.
    assert metrics["third_down_conv_pct"] == 40.0
    # Four first-down plays across one completed game.
    assert metrics["first_downs_per_game"] == 4.0
    assert metrics["drives_per_game"] == 2.0


def test_derivations_fail_closed_when_team_has_no_completed_offensive_data():
    frame = _sample_pbp()
    for function in (derive_pace_metrics, derive_explosive_metrics, derive_red_zone_drive_metrics):
        result = function(frame, "MIA")
        assert result["ready"] is False
        assert result["games_played"] == 0
        for value in result.values():
            if isinstance(value, float):
                assert math.isnan(value) or math.isfinite(value)
