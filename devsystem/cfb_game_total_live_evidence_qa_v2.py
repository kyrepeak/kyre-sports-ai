"""Live regression proof for CFB Game Total V152 completed-game evidence.

Checks the known user-visible matchup without changing frozen model math:
2026-09-17 Syracuse at Pittsburgh must reconcile exact team identity, usable
records, completed-game scoring evidence, and GREEN derived team stats through
the Game-Total-only V4 display path.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import cfb_game_total_clean_page_v4 as page
import cfb_game_total_hub_v3 as frozen_page
import cfb_game_total_runtime_display_v1 as runtime_display
import cfb_over_under_logo_resolver_v3 as logo_v3

TARGET_DAY = "2026-09-17"
TARGET_AWAY = "Syracuse"
TARGET_HOME = "Pittsburgh"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _find_game(games: list[Mapping[str, Any]]) -> dict[str, Any]:
    for row in games:
        if _clean(row.get("away_team")) == TARGET_AWAY and _clean(row.get("home_team")) == TARGET_HOME:
            return dict(row)
    raise AssertionError(
        f"target matchup missing on {TARGET_DAY}: "
        + ", ".join(
            f"{_clean(g.get('away_team'))} @ {_clean(g.get('home_team'))}"
            for g in games
        )
    )


def _usable_record(value: Any) -> bool:
    text = _clean(value)
    return bool(text and text not in {"0-0", "—"})


def run() -> dict[str, Any]:
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(TARGET_DAY)
    game = _find_game(games)
    original = dict(game)

    frozen = frozen_page.slate.analyze_game(game, TARGET_DAY)
    frozen_away = frozen.get("away") or {}
    frozen_home = frozen.get("home") or {}

    display_game, away, home, display_diag = runtime_display.reconcile_display_bundle(
        game,
        TARGET_DAY,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    away_stats = page._team_stats_state(away, display_game, "away")
    home_stats = page._team_stats_state(home, display_game, "home")

    for side, visual in (("away", visuals.get("away") or {}), ("home", visuals.get("home") or {})):
        team_id = _clean(visual.get("team_id"))
        assert team_id.isdigit(), f"{side} exact ESPN team ID missing: {visual!r}"
        assert _clean(visual.get("logo")), f"{side} exact-ID logo URL missing: {visual!r}"
        assert visual.get("exact_identity") is True, f"{side} logo identity not exact: {visual!r}"

    for label, profile, stats in (
        (TARGET_AWAY, away, away_stats),
        (TARGET_HOME, home, home_stats),
    ):
        assert profile.get("completed_games"), f"{label} completed-game evidence missing"
        assert _usable_record(stats.get("record")), f"{label} record still stale: {stats.get('record')!r}"
        assert stats.get("ppg") is not None, f"{label} PPG missing"
        assert stats.get("allowed_pg") is not None, f"{label} allowed/game missing"
        assert stats.get("quality") == "GREEN", f"{label} stats quality not GREEN: {stats!r}"
        assert int(stats.get("sample_games") or 0) > 0, f"{label} completed-game sample empty"

    # Display enrichment must not back-write exact-ID/logo fields into the
    # original frozen-model game object.
    for key in ("away_espn_team_id", "home_espn_team_id"):
        if key not in original:
            assert key not in game, f"display reconciliation mutated frozen game: {key}"

    result = {
        "status": "GREEN",
        "day": TARGET_DAY,
        "matchup": f"{TARGET_AWAY} @ {TARGET_HOME}",
        "away_record": away_stats.get("record"),
        "home_record": home_stats.get("record"),
        "away_ppg": away_stats.get("ppg"),
        "home_ppg": home_stats.get("ppg"),
        "away_allowed_pg": away_stats.get("allowed_pg"),
        "home_allowed_pg": home_stats.get("allowed_pg"),
        "away_sample_games": away_stats.get("sample_games"),
        "home_sample_games": home_stats.get("sample_games"),
        "away_team_id": _clean((visuals.get("away") or {}).get("team_id")),
        "home_team_id": _clean((visuals.get("home") or {}).get("team_id")),
        "runtime_status": display_diag.get("runtime_status"),
        "runtime_snapshot_used": bool(display_diag.get("runtime_snapshot_used")),
        "game_total_snapshot_overlay": bool(display_diag.get("game_total_snapshot_overlay")),
        "schedule_identity_status": schedule_diag.get("identity_status"),
    }
    print("CFB_GAME_TOTAL_V152_LIVE_EVIDENCE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return result


if __name__ == "__main__":
    run()
