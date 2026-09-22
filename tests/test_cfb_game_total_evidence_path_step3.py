from __future__ import annotations

import cfb_game_total_runtime_display_v1 as runtime


def _row(profile: dict, key: str) -> dict:
    return dict((profile.get("official_stats") or {}).get(key) or {})


def test_step3_snapshot_supplies_verified_red_zone_and_third_down_evidence() -> None:
    payload = runtime._load_game_total_snapshot()
    game = (payload.get("games") or [])[0]

    _, away, home, diag = runtime._apply_deterministic_snapshot(
        {
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "game_date": game["game_date"],
        },
        {},
        {},
        game,
    )

    assert _row(away, "red_zone")["display_value"] == "11-14"
    assert _row(away, "third_down")["display_value"] == "15-29 (51.724%)"
    assert _row(home, "red_zone")["display_value"] == "5-6"
    assert _row(home, "third_down")["display_value"] == "12-29 (41.379%)"

    for profile in (away, home):
        assert "red zone" in _row(profile, "red_zone")["label"].lower()
        assert "third down" in _row(profile, "third_down")["label"].lower()
        assert _row(profile, "red_zone")["source"]
        assert _row(profile, "third_down")["source"]

    assert diag["game_total_deterministic_snapshot_used"] is True
