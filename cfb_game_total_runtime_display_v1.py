"""CFB Game Total runtime display adapter V1.

Game-Total-only overlay above the frozen/shared CFB runtime adapter. The shared
Over/Under adapter remains untouched. This module preserves verified snapshot
fields that are useful for the Game Total display (completed games, recent
scoring, splits and SOS) while keeping all enrichment on a copied game object.

For matchups covered by the Game-Total-only deterministic production snapshot,
the display path uses that checked-in evidence before any shared live provider
call. This prevents deployed Streamlit network variance from producing fallback
logos and blank records/stats. Frozen Step 11/12 model math remains untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cfb_over_under_runtime_team_data_v1 as frozen_runtime

MODEL_VERSION = "CFB GAME TOTAL RUNTIME DISPLAY V1 • DETERMINISTIC PRODUCTION EVIDENCE"
FROZEN_RUNTIME_ADAPTER = "cfb_over_under_runtime_team_data_v1"
GAME_TOTAL_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_game_total_runtime_snapshot_v1.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_game_total_snapshot() -> dict[str, Any]:
    try:
        payload = json.loads(GAME_TOTAL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _find_game_total_snapshot(
    game: Mapping[str, Any],
    selected_day: Any,
) -> dict[str, Any]:
    payload = _load_game_total_snapshot()
    event_id = _clean(game.get("espn_event_id"))
    day = _clean(selected_day) or _clean(game.get("game_date"))
    away_key = frozen_runtime._key(game.get("away_team"))
    home_key = frozen_runtime._key(game.get("home_team"))

    for row in payload.get("games") or []:
        if not isinstance(row, Mapping):
            continue
        if event_id and _clean(row.get("event_id")) == event_id:
            return dict(row)
        if (
            day
            and _clean(row.get("game_date")) == day
            and frozen_runtime._key(row.get("away_team")) == away_key
            and frozen_runtime._key(row.get("home_team")) == home_key
        ):
            return dict(row)
    return {}


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
        "conference",
        "head_coach",
        "division_context",
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

    for key in ("official_stats", "polls"):
        value = side_snap.get(key)
        if isinstance(value, Mapping):
            out[key] = {
                str(name): dict(row) if isinstance(row, Mapping) else row
                for name, row in value.items()
            }

    completed = side_snap.get("completed_games")
    if isinstance(completed, list):
        out["completed_games"] = [
            dict(row) for row in completed if isinstance(row, Mapping)
        ]

    return out


def _overlay_game_snapshot_evidence(
    display_game: Mapping[str, Any],
    snap: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy verified Game-Total-only environment/history evidence onto the display game."""
    out = dict(display_game)
    for key in (
        "weather",
        "temperature",
        "wind",
        "wind_mph",
        "forecast",
        "weather_source",
        "weather_updated_at",
        "history",
        "series_history",
        "head_to_head",
        "history_source",
    ):
        value = snap.get(key)
        if value not in (None, "", [], {}):
            out[key] = dict(value) if isinstance(value, Mapping) else value
    return out


def _apply_deterministic_snapshot(
    safe_game: dict[str, Any],
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
    snap: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    display_game = dict(safe_game)
    frozen_runtime._merge_game_snapshot(display_game, snap)
    display_game = _overlay_game_snapshot_evidence(display_game, snap)

    away_snap = snap.get("away") if isinstance(snap.get("away"), Mapping) else {}
    home_snap = snap.get("home") if isinstance(snap.get("home"), Mapping) else {}

    away = frozen_runtime._profile_from_snapshot(dict(frozen_away), away_snap)
    home = frozen_runtime._profile_from_snapshot(dict(frozen_home), home_snap)
    away = _overlay_snapshot_evidence(away, away_snap)
    home = _overlay_snapshot_evidence(home, home_snap)

    away.setdefault("team", _clean(display_game.get("away_team")) or "Away")
    home.setdefault("team", _clean(display_game.get("home_team")) or "Home")

    for side, profile in (("away", away), ("home", home)):
        team_id = _clean(profile.get("espn_team_id"))
        if team_id.isdigit():
            display_game[f"{side}_espn_team_id"] = team_id

    diag = {
        "runtime_reconciled": True,
        "runtime_status": "GREEN",
        "runtime_issues": [],
        "runtime_snapshot_used": True,
        "deep_reconciliation_ok": False,
        "game_total_snapshot_overlay": True,
        "game_total_deterministic_snapshot_used": True,
        "game_total_deterministic_snapshot_path": GAME_TOTAL_SNAPSHOT_PATH.name,
        "game_total_runtime_display_version": MODEL_VERSION,
    }
    return display_game, away, home, diag


def reconcile_display_bundle(
    game: Mapping[str, Any],
    selected_day: str,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reconcile a display copy without allowing evidence into frozen math."""
    safe_game = dict(game)

    deterministic = _find_game_total_snapshot(safe_game, selected_day)
    if deterministic:
        try:
            return _apply_deterministic_snapshot(
                safe_game,
                frozen_away,
                frozen_home,
                deterministic,
            )
        except Exception as exc:
            deterministic_error = f"{type(exc).__name__}: {exc}"[:500]
    else:
        deterministic_error = ""

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
            display_game = _overlay_game_snapshot_evidence(display_game, snap)
            diag["game_total_snapshot_overlay"] = True
        else:
            diag["game_total_snapshot_overlay"] = False

        for side, profile in (("away", away), ("home", home)):
            team_id = _clean(profile.get("espn_team_id"))
            if team_id.isdigit():
                display_game[f"{side}_espn_team_id"] = team_id

        diag["game_total_deterministic_snapshot_used"] = False
        if deterministic_error:
            diag["game_total_deterministic_snapshot_error"] = deterministic_error
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
                "game_total_deterministic_snapshot_used": False,
                "game_total_runtime_display_version": MODEL_VERSION,
                "runtime_issues": [
                    f"Game Total display reconciliation failed: {type(exc).__name__}"
                ],
            },
        )


__all__ = [
    "FROZEN_RUNTIME_ADAPTER",
    "GAME_TOTAL_SNAPSHOT_PATH",
    "MODEL_VERSION",
    "_find_game_total_snapshot",
    "_load_game_total_snapshot",
    "_overlay_game_snapshot_evidence",
    "_overlay_snapshot_evidence",
    "reconcile_display_bundle",
]
