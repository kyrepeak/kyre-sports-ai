from __future__ import annotations

from pathlib import Path

from wnba_data_completeness_repair_v1_step2_live_history import summarize_player_history


def _game(day, minutes, points, rebounds, assists):
    return {
        "game_date": day,
        "minutes": minutes,
        "points": points,
        "rebounds": rebounds,
        "assists": assists,
    }


def test_history_summary_uses_only_games_before_selected_day_and_builds_pra():
    history = {
        "games": [
            _game("2026-10-07", 40, 99, 99, 99),
            _game("2026-10-06", 30, 18, 5, 7),
            _game("2026-10-04", 20, 10, 4, 3),
            _game("2026-10-02", 10, 6, 2, 1),
        ]
    }
    result = summarize_player_history(history, "2026-10-07")
    assert result["GP"] == 3
    assert result["MIN"] == 20.0
    assert round(result["PTS"], 4) == round(34 / 3, 4)
    assert round(result["REB"], 4) == round(11 / 3, 4)
    assert round(result["AST"], 4) == round(11 / 3, 4)
    assert round(result["PRA"], 4) == round(56 / 3, 4)
    assert result["L5_GP"] == 3
    assert result["L10_GP"] == 3
    assert result["LAST_GAME_DATE"] == "2026-10-06"


def test_last_five_is_more_recent_than_full_history():
    history = {"games": [
        _game(f"2026-09-{day:02d}", 20 + index, 10 + index, 4 + index, 2 + index)
        for index, day in enumerate((30, 29, 28, 27, 26, 25), start=0)
    ]}
    result = summarize_player_history(history, "2026-10-01")
    assert result["GP"] == 6
    assert result["L5_GP"] == 5
    assert result["L10_GP"] == 6
    assert result["L5_MIN"] != result["MIN"]


def test_player_pool_runtime_uses_latency_safe_athlete_gamelog_fallback():
    source = Path("wnba_players_v25.py").read_text(encoding="utf-8")
    assert "get_step3_espn_player_game_log_dataset" in source
    assert "_aggregate_espn_athlete_gamelogs" in source
    assert "ESPN WNBA Athlete Gamelog" in source
