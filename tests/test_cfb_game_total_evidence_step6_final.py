from __future__ import annotations

import cfb_game_total_clean_page_v6 as page
import cfb_game_total_runtime_display_v1 as runtime


def test_final_evidence_integration_marks_all_repaired_steps_ready() -> None:
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

    statuses = page._existing_step_status(
        {
            "away": {"exact_identity": True},
            "home": {"exact_identity": True},
        },
        away,
        home,
        display_game,
    )

    assert statuses[4] == "READY"  # Pace
    assert statuses[5] == "READY"  # Explosive Plays
    assert statuses[6] == "READY"  # Red Zone
    assert statuses[7] == "READY"  # Third Down
    assert statuses[9] == "READY"  # Environment
    assert statuses[10] == "READY"  # History

    assert display_game.get("weather_source")
    assert display_game.get("series_history_source")
    assert diag["game_total_deterministic_snapshot_used"] is True
