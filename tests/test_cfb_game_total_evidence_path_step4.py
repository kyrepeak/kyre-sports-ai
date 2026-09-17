from __future__ import annotations

import cfb_game_total_runtime_display_v1 as runtime


def test_step4_snapshot_supplies_verified_environment_evidence() -> None:
    payload = runtime._load_game_total_snapshot()
    game = (payload.get("games") or [])[0]

    display_game, _, _, diag = runtime._apply_deterministic_snapshot(
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
    assert display_game["wind_mph"] == 6
    assert display_game["wind"] == "NW 6 mph"
    assert "shower" in display_game["weather"].lower() or "thunderstorm" in display_game["weather"].lower()
    assert "National Weather Service" in display_game["environment_source"]
    assert display_game["forecast_updated_at"]
    assert diag["game_total_deterministic_snapshot_used"] is True
