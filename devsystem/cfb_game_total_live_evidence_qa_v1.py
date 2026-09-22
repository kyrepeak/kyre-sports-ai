"""Live regression proof for the CFB Game Total V151 display-data repair.

This checks the exact user-visible failure case without changing model math:
2026-09-17 Syracuse at Pittsburgh must reconcile current records/team identity,
produce exact-ID logos, and expose scoring evidence on the display copy.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import cfb_game_total_clean_page_v2 as page
import cfb_game_total_hub_v3 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3

TARGET_DAY = "2026-09-17"
TARGET_AWAY = "Syracuse"
TARGET_HOME = "Pittsburgh"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _find_game(games: list[Mapping[str, Any]]) -> dict[str, Any]:
    for row in games:
        away = _clean(row.get("away_team"))
        home = _clean(row.get("home_team"))
        if away == TARGET_AWAY and home == TARGET_HOME:
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
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(
        TARGET_DAY
    )
    game = _find_game(games)
    original = dict(game)

    frozen = frozen_page.slate.analyze_game(game, TARGET_DAY)
    frozen_away = frozen.get("away") or {}
    frozen_home = frozen.get("home") or {}

    display_game, away, home, display_diag = page._display_bundle(
        game,
        TARGET_DAY,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)

    away_record = page._record(
        away,
        display_game,
        "away",
        bool(display_diag.get("runtime_snapshot_used") or display_diag.get("deep_reconciliation_ok")),
    )
    home_record = page._record(
        home,
        display_game,
        "home",
        bool(display_diag.get("runtime_snapshot_used") or display_diag.get("deep_reconciliation_ok")),
    )

    assert _usable_record(away_record), f"Syracuse record still stale: {away_record!r}"
    assert _usable_record(home_record), f"Pittsburgh record still stale: {home_record!r}"

    for side, visual in (("away", visuals.get("away") or {}), ("home", visuals.get("home") or {})):
        team_id = _clean(visual.get("team_id"))
        assert team_id.isdigit(), f"{side} exact ESPN team ID missing: {visual!r}"
        assert _clean(visual.get("logo")), f"{side} exact-ID logo URL missing: {visual!r}"
        assert visual.get("exact_identity") is True, f"{side} logo identity not exact: {visual!r}"

    for label, profile in ((TARGET_AWAY, away), (TARGET_HOME, home)):
        assert profile.get("ppg") is not None, f"{label} PPG missing"
        assert profile.get("points_allowed_pg") is not None, f"{label} allowed/game missing"
        assert profile.get("completed_games"), f"{label} completed-game evidence missing"

    # Display enrichment must not back-write exact-ID/logo fields into the
    # original frozen-model game object.
    for key in ("away_espn_team_id", "home_espn_team_id"):
        if key not in original:
            assert key not in game, f"display reconciliation mutated frozen game: {key}"

    result = {
        "status": "GREEN",
        "day": TARGET_DAY,
        "matchup": f"{TARGET_AWAY} @ {TARGET_HOME}",
        "away_record": away_record,
        "home_record": home_record,
        "away_team_id": _clean((visuals.get("away") or {}).get("team_id")),
        "home_team_id": _clean((visuals.get("home") or {}).get("team_id")),
        "away_ppg": away.get("ppg"),
        "home_ppg": home.get("ppg"),
        "runtime_status": display_diag.get("runtime_status"),
        "runtime_snapshot_used": bool(display_diag.get("runtime_snapshot_used")),
        "deep_reconciliation_ok": bool(display_diag.get("deep_reconciliation_ok")),
        "schedule_identity_status": schedule_diag.get("identity_status"),
    }
    print("CFB_GAME_TOTAL_V151_LIVE_EVIDENCE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return result


if __name__ == "__main__":
    run()
