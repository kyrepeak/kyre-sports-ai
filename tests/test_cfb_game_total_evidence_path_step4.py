from __future__ import annotations

import cfb_game_total_runtime_display_v1 as runtime


def test_step4_snapshot_supplies_verified_environment_to_display_game_only() -> None:
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

    assert display_game["temperature"] == 77
    assert display_game["wind"] == "NW 6 mph"
    assert "20%" in display_game["forecast"]
    assert "National Weather Service" in display_game["weather_source"]
    assert diag["game_total_deterministic_snapshot_used"] is True

    # Environment evidence is display-only; it must not be injected into team profiles.
    for profile in (away, home):
        assert "temperature" not in profile
        assert "wind" not in profile
        assert "forecast" not in profile
