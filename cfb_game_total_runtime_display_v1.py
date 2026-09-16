"""CFB Game Total runtime display adapter V1.

Game-Total-only overlay above the frozen/shared CFB runtime adapter. The shared
Over/Under adapter remains untouched. This module preserves verified snapshot
fields that are useful for the Game Total display (completed games, recent
scoring, splits and SOS) while keeping all enrichment on a copied game object.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_over_under_runtime_team_data_v1 as frozen_runtime

MODEL_VERSION = "CFB GAME TOTAL RUNTIME DISPLAY V1 • COMPLETED GAME EVIDENCE"
FROZEN_RUNTIME_ADAPTER = "cfb_over_under_runtime_team_data_v1"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _overlay_snapshot_evidence(
    profile: Mapping[str, Any],
    side_snap: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay display-only verified evidence omitted by the shared adapter."""
    out = dict(profile)

    for key in (
        "home_record",
        "away_record",
        "neutral_record",
        "recent_record",
    ):
        value = side_snap.get(key)
        if isinstance(value, Mapping):
            out[key] = dict(value)

    for key in (
        "record_text",
        "recent_form",
        "data_source",
    ):
        value = side_snap.get(key)
        if value not in (None, ""):
            out[key] = value

    for key in (
        "ppg",
        "points_allowed_pg",
        "point_diff_pg",
        "recent_ppg",
        "recent_points_allowed_pg",
        "recent_point_diff_pg",
        "sos_opponent_win_pct",
        "sos_coverage",
    ):
        if key in side_snap:
            out[key] = side_snap.get(key)

    completed = side_snap.get("completed_games")
    if isinstance(completed, list):
        out["completed_games"] = [
            dict(row) for row in completed if isinstance(row, Mapping)
        ]

    return out


def reconcile_display_bundle(
    game: Mapping[str, Any],
    selected_day: str,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reconcile a display copy without allowing evidence into frozen math."""
    safe_game = dict(game)
    try:
        display_game, away, home, diag = frozen_runtime.reconcile_runtime(
            safe_game,
            selected_day,
        )
        display_game = dict(display_game or safe_game)
        away = dict(away or frozen_away)
        home = dict(home or frozen_home)
        diag = dict(diag or {})

        snap = frozen_runtime._find_snapshot(safe_game)
        if snap:
            away_snap = snap.get("away") if isinstance(snap.get("away"), Mapping) else {}
            home_snap = snap.get("home") if isinstance(snap.get("home"), Mapping) else {}
            away = _overlay_snapshot_evidence(away, away_snap)
            home = _overlay_snapshot_evidence(home, home_snap)
            diag["game_total_snapshot_overlay"] = True
        else:
            diag["game_total_snapshot_overlay"] = False

        for side, profile in (("away", away), ("home", home)):
            team_id = _clean(profile.get("espn_team_id"))
            if team_id.isdigit():
                display_game[f"{side}_espn_team_id"] = team_id

        diag["game_total_runtime_display_version"] = MODEL_VERSION
        return display_game, away, home, diag
    except Exception as exc:
        return (
            safe_game,
            dict(frozen_away),
            dict(frozen_home),
            {
                "runtime_status": "PARTIAL",
                "runtime_snapshot_used": False,
                "deep_reconciliation_ok": False,
                "game_total_snapshot_overlay": False,
                "game_total_runtime_display_version": MODEL_VERSION,
                "runtime_issues": [
                    f"Game Total display reconciliation failed: {type(exc).__name__}"
                ],
            },
        )


__all__ = [
    "FROZEN_RUNTIME_ADAPTER",
    "MODEL_VERSION",
    "_overlay_snapshot_evidence",
    "reconcile_display_bundle",
]
