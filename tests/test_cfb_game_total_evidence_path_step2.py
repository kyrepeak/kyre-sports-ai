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


def test_step2_snapshot_supplies_verified_pace_and_explosive_evidence() -> None:
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

    for profile in (away, home):
        assert _has_official_row(profile, "pace", "tempo", "plays per game", "seconds per play")
        assert _has_official_row(profile, "explosive", "yards per play", "20+", "10+")
        rows = profile.get("official_stats") or {}
        assert all((row or {}).get("source") for row in rows.values() if isinstance(row, dict))

    assert away["official_stats"]["plays_per_game"]["value"] == 82.5
    assert away["official_stats"]["yards_per_play"]["value"] == 5.8
    assert home["official_stats"]["plays_per_game"]["value"] == 73.5
    assert home["official_stats"]["yards_per_play"]["value"] == 6.5
    assert diag["game_total_deterministic_snapshot_used"] is True
