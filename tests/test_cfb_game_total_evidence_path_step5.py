from __future__ import annotations

import cfb_game_total_clean_page_v6 as page
import cfb_game_total_runtime_display_v1 as runtime


def test_step5_snapshot_supplies_verified_series_history_to_display_path() -> None:
    payload = runtime._load_game_total_snapshot()
    game = (payload.get("games") or [])[0]

    display_game, away, home, diag = runtime._apply_deterministic_snapshot(
        {
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "game_date": game["game_date"],
        },
        {},
        {},
        game,
    )

    history = display_game.get("series_history") or {}
    assert history.get("meetings") == 82
    assert history.get("leader") == "Pittsburgh"
    assert history.get("record") == "45-33-3"
    assert history.get("series_start") == 1916
    assert history.get("recent_streak") == "Pittsburgh won the last two meetings"
    assert "Syracuse University Athletics" in str(display_game.get("history_source") or "")

    statuses = page._existing_step_status({}, away, home, display_game)
    assert statuses[10] == "READY"
    assert diag["game_total_deterministic_snapshot_used"] is True
