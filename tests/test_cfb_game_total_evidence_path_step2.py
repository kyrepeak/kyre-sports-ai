from __future__ import annotations

import cfb_game_total_runtime_display_v1 as runtime


def _has_official_row(profile: dict, *needles: str) -> bool:
    rows = profile.get("official_stats") or {}
    haystack = " ".join(
        " ".join((str(key), str((row or {}).get("label") or ""))).lower()
        for key, row in rows.items()
        if isinstance(row, dict)
    )
    return any(needle.lower() in haystack for needle in needles)


def test_step2_snapshot_supplies_verified_steps_4_to_10_evidence_to_display_path() -> None:
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

    for profile in (away, home):
        assert _has_official_row(profile, "pace", "tempo", "plays per game", "seconds per play")
        assert _has_official_row(profile, "explosive", "yards per play", "20+", "10+")
        assert _has_official_row(profile, "red zone")
        assert _has_official_row(profile, "third down", "3rd down")
        assert _has_official_row(profile, "turnover", "giveaway", "takeaway")

    assert any(
        display_game.get(key) not in (None, "")
        for key in ("weather", "temperature", "wind", "wind_mph", "forecast")
    )
    assert any(
        display_game.get(key) not in (None, "", [], {})
        for key in ("history", "series_history", "head_to_head")
    )
    assert diag["game_total_deterministic_snapshot_used"] is True
