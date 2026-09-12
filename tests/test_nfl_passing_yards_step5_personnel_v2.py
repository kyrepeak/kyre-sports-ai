from __future__ import annotations

import math

import nfl_passing_yards_hub_v28 as hub_v28
import nfl_passing_yards_personnel_v2 as v2


def _summary(with_targets: bool = True):
    receiving_labels = ["REC", "YDS", "AVG", "TD", "LONG"]
    receiving_stats = ["6", "88", "14.7", "1", "28"]
    if with_targets:
        receiving_labels.append("TGTS")
        receiving_stats.append("10")
    return {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "27"},
                    "statistics": [
                        {"name": "completionAttempts", "value": "-", "displayValue": "20/30"},
                    ],
                },
                {"team": {"id": "4"}, "statistics": []},
            ],
            "players": [
                {
                    "team": {"id": "27"},
                    "statistics": [
                        {
                            "name": "receiving",
                            "labels": receiving_labels,
                            "athletes": [
                                {
                                    "athlete": {"id": "100", "displayName": "Exact Weapon"},
                                    "stats": receiving_stats,
                                }
                            ],
                        },
                        {
                            "name": "passing",
                            "labels": ["C/ATT", "YDS"],
                            "athletes": [
                                {"athlete": {"id": "3052587"}, "stats": ["20/30", "250"]},
                            ],
                        },
                    ],
                }
            ],
        }
    }


def test_parse_team_receiving_game_uses_exact_team_and_explicit_targets():
    row = v2.parse_team_receiving_game(_summary(True), "27")
    assert row["ready"] is True
    assert row["team_pass_attempts"] == 30
    assert row["players"][0]["athlete_id"] == "100"
    assert row["players"][0]["targets"] == 10
    assert row["players"][0]["receptions"] == 6
    assert row["players"][0]["receiving_yards"] == 88


def test_parse_team_receiving_game_fails_closed_without_target_column():
    row = v2.parse_team_receiving_game(_summary(False), "27")
    assert row["ready"] is False
    assert "targets" in row["reason"].lower()


def test_current_weapon_rows_join_usage_by_exact_athlete_id_only():
    depth = [
        {"position": "WR", "rank": 1, "athlete_id": "100", "name": "Exact Weapon"},
        {"position": "WR", "rank": 2, "athlete_id": "200", "name": "Second Weapon"},
        {"position": "QB", "rank": 1, "athlete_id": "999", "name": "QB"},
    ]
    usage = {
        "usage_games": 5,
        "players": {
            "100": {"targets": 40, "receptions": 28, "receiving_yards": 410, "target_share": 25.0, "target_share_verified": True},
            "777": {"targets": 90, "target_share": 50.0, "target_share_verified": True},
        },
    }
    rows = v2._current_weapon_rows(depth, usage)
    assert [r["athlete_id"] for r in rows] == ["100", "200"]
    assert rows[0]["target_share"] == 25.0
    assert not v2._finite(rows[1]["target_share"])
    assert all(r["athlete_id"] != "777" for r in rows)


def test_no_hard_or_watch_skill_injuries_means_zero_share_not_unknown(monkeypatch):
    monkeypatch.setattr(
        v2.base,
        "build_personnel_matchup",
        lambda *args, **kwargs: {
            "ready": True,
            "offense_team_id": "27",
            "offense_team_name": "Tampa Bay Buccaneers",
            "defense_team_id": "4",
            "defense_team_name": "Cincinnati Bengals",
            "qb_name": "Baker Mayfield",
            "qb_status": "No listed injury",
            "skill_injuries": [],
            "ol_injuries": [],
            "secondary_injuries": [],
            "skill_hard_count": 0,
            "skill_watch_count": 0,
            "ol_hard_count": 0,
            "secondary_hard_count": 0,
            "offense_depth_rows": [{"position": "WR", "rank": 1, "athlete_id": "100", "name": "Exact Weapon"}],
            "projection_adjustment": 0.0,
        },
    )
    monkeypatch.setattr(
        v2,
        "recent_weapon_usage",
        lambda *args, **kwargs: {
            "ready": True,
            "usage_games": 5,
            "event_ids": ["1", "2", "3", "4", "5"],
            "early_season_fallback": True,
            "players": {"100": {"targets": 40, "target_share": 25.0, "target_share_verified": True}},
        },
    )
    offense = {"team_id": "27", "injury_feed_ok": True, "injuries": []}
    defense = {"team_id": "4", "injury_feed_ok": True, "injuries": []}
    row = v2.build_personnel_matchup(offense, defense, 2026, 2, 600, cutoff_date="2026-09-13")
    assert row["hard_target_share"] == 0.0
    assert row["watch_target_share"] == 0.0
    assert row["weapon_usage_ready"] is True
    assert row["top_weapons"][0]["target_share"] == 25.0
    assert row["projection_adjustment"] == 0.0
    assert row["sportsbook_influence"] == 0.0


def test_hard_skill_share_uses_exact_recent_usage_and_can_drive_existing_label(monkeypatch):
    monkeypatch.setattr(
        v2.base,
        "build_personnel_matchup",
        lambda *args, **kwargs: {
            "ready": True,
            "offense_team_id": "27",
            "offense_team_name": "TB",
            "defense_team_id": "4",
            "defense_team_name": "CIN",
            "qb_name": "QB",
            "qb_status": "No listed injury",
            "skill_injuries": [{"athlete_id": "100", "name": "WR1", "position": "WR", "tier": "HARD", "status": "Out", "depth_rank": 1}],
            "ol_injuries": [],
            "secondary_injuries": [],
            "skill_hard_count": 1,
            "skill_watch_count": 0,
            "ol_hard_count": 0,
            "secondary_hard_count": 0,
            "offense_depth_rows": [{"position": "WR", "rank": 1, "athlete_id": "100", "name": "WR1"}],
        },
    )
    monkeypatch.setattr(
        v2,
        "recent_weapon_usage",
        lambda *args, **kwargs: {
            "ready": True,
            "usage_games": 5,
            "event_ids": ["1"],
            "early_season_fallback": False,
            "players": {"100": {"targets": 45, "receptions": 30, "receiving_yards": 500, "target_share": 23.0, "target_share_verified": True}},
        },
    )
    offense = {"team_id": "27", "injury_feed_ok": True}
    defense = {"team_id": "4", "injury_feed_ok": True}
    row = v2.build_personnel_matchup(offense, defense, 2026, 2, 600, cutoff_date="2026-10-01")
    assert row["hard_target_share"] == 23.0
    assert row["skill_injuries"][0]["target_share_verified"] is True
    assert row["personnel_label"] == "HURT"


def test_v28_proxy_supplies_selected_cutoff_and_restores_nested_owners(monkeypatch):
    original_personnel = hub_v28.step7_owner.personnel
    original_card = hub_v28.step5_ui._personnel_card
    original_table = hub_v28.step5_ui._personnel_table
    monkeypatch.setattr(hub_v28, "_selected_cutoff", lambda: "2026-09-13")

    captured = {}
    monkeypatch.setattr(
        hub_v28.personnel_v2,
        "build_personnel_matchup",
        lambda *args, **kwargs: captured.update({"cutoff": kwargs.get("cutoff_date")}) or {"ready": True},
    )

    def fake_prior_render():
        result = hub_v28.step7_owner.personnel.build_personnel_matchup({}, {}, 2026, 2, 0)
        assert result["ready"] is True
        assert hub_v28.step5_ui._personnel_card is hub_v28._personnel_card
        assert hub_v28.step5_ui._personnel_table is hub_v28._personnel_table

    monkeypatch.setattr(hub_v28.prior, "render_nfl_passing_yards_hub", fake_prior_render)
    hub_v28.render_nfl_passing_yards_hub()
    assert captured["cutoff"] == "2026-09-13"
    assert hub_v28.step7_owner.personnel is original_personnel
    assert hub_v28.step5_ui._personnel_card is original_card
    assert hub_v28.step5_ui._personnel_table is original_table


def test_v28_source_contract_is_context_only():
    assert "V28" in hub_v28.MODEL_VERSION
    assert hub_v28.FROZEN_PRIOR == "nfl_passing_yards_hub_v27"
    assert v2.FROZEN_PRIOR == "nfl_passing_yards_personnel_v1"
    assert v2.RECENT_USAGE_WINDOW == 5
