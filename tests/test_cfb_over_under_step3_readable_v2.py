"""Regression tests for readable CFB O/U Step 3 V2."""
from __future__ import annotations

from datetime import datetime, timezone

import cfb_over_under_clean_page_v17 as page
import cfb_over_under_step3_readable_v2 as step3


def _core_payload():
    return {
        "splits": {
            "categories": [
                {
                    "name": "general",
                    "stats": [
                        {"name": "gamesPlayed", "value": 2},
                    ],
                },
                {
                    "name": "passing",
                    "stats": [
                        {"name": "netPassingYards", "value": 400},
                        {"name": "netPassingYardsPerGame", "value": 200},
                        {"name": "netTotalYards", "value": 600},
                        {"name": "netYardsPerGame", "value": 300},
                        {"name": "passingTouchdowns", "value": 4},
                        {"name": "totalPoints", "value": 56},
                        {"name": "totalPointsPerGame", "value": 28},
                        {"name": "totalOffensivePlays", "value": 120},
                    ],
                },
                {
                    "name": "rushing",
                    "stats": [
                        {"name": "rushingYards", "value": 200},
                        {"name": "rushingYardsPerGame", "value": 100},
                        {"name": "rushingTouchdowns", "value": 2},
                    ],
                },
                {
                    "name": "miscellaneous",
                    "stats": [
                        {"name": "firstDowns", "value": 44},
                        # Provider quirk: this field can be scaled oddly.
                        {"name": "firstDownsPerGame", "value": 2200},
                    ],
                },
            ],
        },
    }


def _summary(opponent_id: str, *, total: int, passing: int, rushing: int,
             first_downs: int, rush_attempts: int, pass_attempts: int,
             pass_td: int, rush_td: int):
    return {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "1", "displayName": "Defense Team"},
                    "statistics": [],
                },
                {
                    "team": {"id": opponent_id, "displayName": "Opponent"},
                    "statistics": [
                        {"name": "firstDowns", "displayValue": str(first_downs)},
                        {"name": "totalYards", "displayValue": str(total)},
                        {"name": "netPassingYards", "displayValue": str(passing)},
                        {"name": "completionAttempts", "displayValue": f"20/{pass_attempts}"},
                        {"name": "rushingYards", "displayValue": str(rushing)},
                        {"name": "rushingAttempts", "displayValue": str(rush_attempts)},
                    ],
                },
            ],
            "players": [
                {
                    "team": {"id": opponent_id, "displayName": "Opponent"},
                    "statistics": [
                        {
                            "name": "passing",
                            "labels": ["C/ATT", "YDS", "AVG", "TD", "INT"],
                            "athletes": [
                                {"athlete": {"displayName": "QB"}, "stats": ["20/30", str(passing), "7.0", str(pass_td), "0"]},
                            ],
                        },
                        {
                            "name": "rushing",
                            "labels": ["CAR", "YDS", "AVG", "TD", "LONG"],
                            "athletes": [
                                {"athlete": {"displayName": "RB"}, "stats": [str(rush_attempts), str(rushing), "4.0", str(rush_td), "20"]},
                            ],
                        },
                    ],
                },
            ],
        },
    }


def test_live_offense_uses_readable_current_season_stats(monkeypatch):
    step3._live_offense.clear()
    monkeypatch.setattr(
        step3.deep,
        "_core_json",
        lambda url, provider: (_core_payload(), [{"provider": provider}]),
    )

    offense, diag = step3._live_offense("2390", 2026)

    assert diag["ready"] is True
    assert offense["points_pg"] == 28
    assert offense["total_yards_pg"] == 300
    assert offense["pass_yards_pg"] == 200
    assert offense["rush_yards_pg"] == 100
    assert offense["pass_td_pg"] == 2
    assert offense["rush_td_pg"] == 1
    assert offense["first_downs_pg"] == 22
    assert offense["yards_per_play"] == 5


def test_live_defense_aggregates_yards_tds_and_first_downs_allowed(monkeypatch):
    step3._live_defense.clear()
    cutoff = datetime(2026, 9, 10, tzinfo=timezone.utc)

    rows = [
        {
            "event_id": "g1",
            "date_dt": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "points_against": 10,
            "opponent_name": "Opponent One",
        },
        {
            "event_id": "g2",
            "date_dt": datetime(2026, 9, 5, tzinfo=timezone.utc),
            "points_against": 20,
            "opponent_name": "Opponent Two",
        },
    ]
    monkeypatch.setattr(
        step3,
        "_completed_rows",
        lambda team_id, season, cutoff, excluded_event_id: (rows, []),
    )

    summaries = {
        "g1": _summary(
            "2", total=300, passing=200, rushing=100,
            first_downs=18, rush_attempts=25, pass_attempts=30,
            pass_td=1, rush_td=1,
        ),
        "g2": _summary(
            "3", total=400, passing=250, rushing=150,
            first_downs=22, rush_attempts=30, pass_attempts=35,
            pass_td=2, rush_td=2,
        ),
    }
    monkeypatch.setattr(
        step3.deep.environment_engine,
        "_fetch_summary",
        lambda event_id: (summaries[event_id], []),
    )

    defense, diag = step3._live_defense(
        "1",
        2026,
        cutoff.isoformat(),
        "",
    )

    assert diag["ready"] is True
    assert diag["summary_games"] == 2
    assert defense["points_allowed_pg"] == 15
    assert defense["total_yards_allowed_pg"] == 350
    assert defense["pass_yards_allowed_pg"] == 225
    assert defense["rush_yards_allowed_pg"] == 125
    assert defense["pass_td_allowed_pg"] == 1.5
    assert defense["rush_td_allowed_pg"] == 1.5
    assert defense["first_downs_allowed_pg"] == 20
    assert round(defense["yards_per_play_allowed"], 6) == round(700 / 120, 6)


def test_checked_in_famu_miami_snapshot_has_requested_step3_fields():
    payload = step3._snapshot_payload()
    famu = payload["teams"]["50"]
    miami = payload["teams"]["2390"]

    for team in (famu, miami):
        assert team["games"] >= 1
        for key in (
            "points_pg",
            "total_yards_pg",
            "pass_yards_pg",
            "rush_yards_pg",
            "pass_td_pg",
            "rush_td_pg",
            "first_downs_pg",
            "yards_per_play",
        ):
            assert team["offense"][key] is not None
        for key in (
            "points_allowed_pg",
            "total_yards_allowed_pg",
            "pass_yards_allowed_pg",
            "rush_yards_allowed_pg",
            "pass_td_allowed_pg",
            "rush_td_allowed_pg",
            "first_downs_allowed_pg",
            "yards_per_play_allowed",
        ):
            assert team["defense"][key] is not None

    assert famu["offense"]["pass_yards_pg"] == 176.0
    assert famu["defense"]["rush_yards_allowed_pg"] == 147.5
    assert miami["offense"]["pass_yards_pg"] == 428.0
    assert miami["defense"]["total_yards_allowed_pg"] == 299.0


def test_battle_is_descriptive_not_fake_edge_grade():
    away = {
        "team": "Miami (FL)",
        "games": 1,
        "offense": {
            "points_pg": 45,
            "total_yards_pg": 549,
            "pass_yards_pg": 428,
            "rush_yards_pg": 121,
            "pass_td_pg": 5,
            "rush_td_pg": 1,
            "first_downs_pg": 27,
            "yards_per_play": 8.19,
        },
    }
    defense = {
        "team": "Florida A&M",
        "games": 2,
        "defense": {
            "points_allowed_pg": 19,
            "total_yards_allowed_pg": 321,
            "pass_yards_allowed_pg": 173.5,
            "rush_yards_allowed_pg": 147.5,
            "pass_td_allowed_pg": 0.5,
            "rush_td_allowed_pg": 2,
            "first_downs_allowed_pg": 17,
            "yards_per_play_allowed": 5.49,
        },
    }

    battle = step3._battle(away, defense)

    passing = next(row for row in battle["rows"] if row["key"] == "pass_yards")
    assert passing["difference"] == 254.5
    assert "ALLOWANCE" in passing["comparison_label"]
    assert "EDGE" not in passing["comparison_label"]
    assert battle["offense_sample"] == "VERY EARLY • 1 GAME"
    assert battle["defense_sample"] == "EARLY • 2 GAMES"


def test_clean_page_step3_renders_both_readable_battles_not_dev_numbers():
    readable = {
        "display_ready": True,
        "sample_state": "VERY EARLY • 1 GAME",
        "sources": ["ESPN Core", "ESPN exact-event summaries"],
        "away_offense_vs_home_defense": {
            "offense_team": "Florida A&M",
            "defense_team": "Miami (FL)",
            "offense_sample": "EARLY • 2 GAMES",
            "defense_sample": "VERY EARLY • 1 GAME",
            "summary": "Production vs allowance is mixed",
            "rows": [
                {
                    "key": "pass_yards",
                    "label": "Passing yards",
                    "offense_value": 176.0,
                    "defense_value": 221.0,
                    "difference": -45.0,
                    "offense_suffix": "YPG",
                    "defense_suffix": "allowed",
                },
                {
                    "key": "rush_yards",
                    "label": "Rushing yards",
                    "offense_value": 34.5,
                    "defense_value": 78.0,
                    "difference": -43.5,
                    "offense_suffix": "YPG",
                    "defense_suffix": "allowed",
                },
            ],
        },
        "home_offense_vs_away_defense": {
            "offense_team": "Miami (FL)",
            "defense_team": "Florida A&M",
            "offense_sample": "VERY EARLY • 1 GAME",
            "defense_sample": "EARLY • 2 GAMES",
            "summary": "Miami is above current allowance",
            "rows": [
                {
                    "key": "pass_yards",
                    "label": "Passing yards",
                    "offense_value": 428.0,
                    "defense_value": 173.5,
                    "difference": 254.5,
                    "offense_suffix": "YPG",
                    "defense_suffix": "allowed",
                },
                {
                    "key": "first_downs",
                    "label": "First downs",
                    "offense_value": 27.0,
                    "defense_value": 17.0,
                    "difference": 10.0,
                    "offense_suffix": "/ game",
                    "defense_suffix": "allowed / game",
                },
            ],
        },
    }

    html = page._step3_readable(
        readable,
        {"ready": True, "model_ready": False, "coverage": 0.0, "reason": "gated"},
    )

    for token in (
        "Florida A&amp;M OFFENSE",
        "Miami (FL) DEFENSE",
        "Miami (FL) OFFENSE",
        "Florida A&amp;M DEFENSE",
        "Passing yards",
        "Rushing yards",
        "First downs",
        "176.0",
        "221.0",
        "428.0",
        "173.5",
        "+254.5",
        "0% NEW PROJECTION WEIGHT",
        "certified matchup model gated",
    ):
        assert token in html

    for token in (
        "coverage",
        "analysis line matchup weight",
        "max team adjustment",
        "weighted signal",
    ):
        assert token not in html.lower()
