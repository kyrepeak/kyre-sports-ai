from __future__ import annotations

import math


def _completed_games() -> list[dict]:
    return [
        {
            "event_id": "1",
            "date": "2026-08-29",
            "opponent": "Opponent A",
            "location": "home",
            "result": "W",
            "score": "31-14",
            "opponent_record_pct": 0.600,
        },
        {
            "event_id": "2",
            "date": "2026-09-05",
            "opponent": "Opponent B",
            "location": "away",
            "result": "L",
            "score": "20-24",
            "opponent_record_pct": 0.500,
        },
    ]


def test_game_total_snapshot_overlay_preserves_completed_games_and_recent_context() -> None:
    import cfb_game_total_runtime_display_v1 as runtime

    side_snap = {
        "record_text": "1-1",
        "ppg": 25.5,
        "points_allowed_pg": 19.0,
        "point_diff_pg": 6.5,
        "recent_form": "WL",
        "recent_ppg": 25.5,
        "recent_points_allowed_pg": 19.0,
        "recent_point_diff_pg": 6.5,
        "sos_opponent_win_pct": 0.55,
        "sos_coverage": 1.0,
        "home_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
        "away_record": {"wins": 0, "losses": 1, "ties": 0, "games": 1},
        "neutral_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
        "recent_record": {"wins": 1, "losses": 1, "ties": 0, "games": 2},
        "completed_games": _completed_games(),
    }

    profile = runtime._overlay_snapshot_evidence({"team": "Syracuse"}, side_snap)

    assert profile["completed_games"] == _completed_games()
    assert profile["recent_record"]["games"] == 2
    assert profile["recent_ppg"] == 25.5
    assert profile["recent_points_allowed_pg"] == 19.0
    assert profile["sos_opponent_win_pct"] == 0.55
    assert profile["sos_coverage"] == 1.0


def test_display_stats_rebuild_record_and_averages_from_completed_games() -> None:
    from cfb_game_total_clean_page_v4 import _team_stats_state

    profile = {
        "team": "Syracuse",
        "record_text": "0-0",
        "completed_games": _completed_games(),
    }
    state = _team_stats_state(profile, {"away_record_summary": "0-0"}, "away")

    assert state["record"] == "1-1"
    assert math.isclose(state["ppg"], 25.5)
    assert math.isclose(state["allowed_pg"], 19.0)
    assert math.isclose(state["point_diff_pg"], 6.5)
    assert state["recent_form"] == "WL"
    assert state["home_split"] == "1-0"
    assert state["away_split"] == "0-1"
    assert math.isclose(state["sos_opponent_win_pct"], 0.55)
    assert math.isclose(state["sos_coverage"], 1.0)
    assert state["quality"] == "GREEN"


def test_display_stats_fail_closed_when_completed_evidence_is_absent() -> None:
    from cfb_game_total_clean_page_v4 import _team_stats_state

    state = _team_stats_state(
        {"team": "Syracuse", "record_text": "0-0"},
        {"away_record_summary": "0-0"},
        "away",
    )

    assert state["record"] == "—"
    assert state["ppg"] is None
    assert state["allowed_pg"] is None
    assert state["recent_form"] == "—"
    assert state["quality"] == "CHECK"


def test_display_stats_prefers_more_complete_completed_sample_over_stale_record() -> None:
    from cfb_game_total_clean_page_v4 import _team_stats_state

    rows = _completed_games() + [
        {
            "event_id": "3",
            "date": "2026-09-12",
            "opponent": "Opponent C",
            "location": "home",
            "result": "W",
            "score": "28-17",
            "opponent_record_pct": 0.750,
        }
    ]
    state = _team_stats_state(
        {"team": "Syracuse", "record_text": "1-1", "completed_games": rows},
        {"away_record_summary": "1-1"},
        "away",
    )

    assert state["record"] == "2-1"
    assert state["sample_games"] == 3
    assert state["quality"] == "GREEN"
