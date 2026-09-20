"""Deterministic Game Total model-input routing for page cleanup Step 6.

Fresh helper name intentionally bypasses stale Streamlit module/cache state.
The checked-in certified Runtime Snapshot V2 is the first path. Frozen model
math is not implemented here and is never modified.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cfb_game_total_model_input_v1 as prior

MODEL_VERSION = "CFB GAME TOTAL MODEL INPUT V2 • STEP 6 RUNTIME FRESH"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "cfb_runtime_snapshot_v2.json"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_local_snapshot() -> dict[str, Any]:
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 2, "games": [], "_runtime_snapshot_source": "unavailable"}
    if int(payload.get("version") or 0) != 2 or not isinstance(payload.get("games"), list):
        return {"version": 2, "games": [], "_runtime_snapshot_source": "unavailable"}
    out = dict(payload)
    out["_runtime_snapshot_source"] = "checked-in-certified-runtime-v2"
    return out


def local_snapshot_revision() -> str:
    payload = _load_local_snapshot()
    return "|".join((
        _clean(payload.get("generated_at")) or "unknown",
        _clean((payload.get("window") or {}).get("start")),
        _clean((payload.get("window") or {}).get("end")),
        str(len(payload.get("games") or [])),
    ))


def _select_exact(
    payload: Mapping[str, Any],
    game: Mapping[str, Any],
    as_of_day: str,
) -> dict[str, Any]:
    rows = [row for row in (payload.get("games") or []) if isinstance(row, Mapping)]
    event_id = _clean(game.get("espn_event_id") or game.get("event_id"))
    if event_id:
        exact = [row for row in rows if _clean(row.get("event_id")) == event_id]
        if len(exact) == 1:
            return dict(exact[0])

    day = _clean(game.get("game_date") or as_of_day)[:10]
    away = _clean(game.get("away_team")).casefold()
    home = _clean(game.get("home_team")).casefold()
    exact = [
        row for row in rows
        if _clean(row.get("game_date"))[:10] == day
        and _clean(row.get("away_team")).casefold() == away
        and _clean(row.get("home_team")).casefold() == home
    ]
    return dict(exact[0]) if len(exact) == 1 else {}


def local_exact_profiles(
    game: Mapping[str, Any],
    as_of_day: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = _load_local_snapshot()
    selected = _select_exact(payload, game, str(as_of_day))
    if not selected:
        return {"away": {}, "home": {}}, {
            "version": MODEL_VERSION,
            "source": payload.get("_runtime_snapshot_source"),
            "selected_event_found": False,
            "snapshot_revision": local_snapshot_revision(),
            "ready": False,
        }

    outputs: dict[str, dict[str, Any]] = {}
    side_diag: dict[str, Any] = {}
    for side in ("away", "home"):
        selected_side = selected.get(side) if isinstance(selected.get(side), Mapping) else {}
        repaired, ok = prior._repair_profile({}, selected_side, selected_side, str(as_of_day))
        outputs[side] = repaired if ok else {}
        side_diag[side] = {
            "ready": bool(ok),
            "team_id": _clean(selected_side.get("team_id")),
            "sample_games": int((repaired.get("record") or {}).get("games") or 0),
            "quality_grade": _clean((repaired.get("data_quality") or {}).get("grade")),
        }

    ready = all(bool(outputs.get(side)) for side in ("away", "home"))
    return outputs, {
        "version": MODEL_VERSION,
        "source": "checked-in-certified-runtime-v2",
        "selected_event_found": True,
        "event_id": _clean(selected.get("event_id")),
        "generated_at": payload.get("generated_at"),
        "window": payload.get("window"),
        "snapshot_revision": local_snapshot_revision(),
        "sides": side_diag,
        "ready": bool(ready),
        "fallback_used": bool(ready),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def enrich_matchup_model_profiles(
    game: Mapping[str, Any],
    as_of_day: str,
    profiles: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    base = {
        "away": dict((profiles or {}).get("away") or {}),
        "home": dict((profiles or {}).get("home") or {}),
    }
    needed = {
        side: not prior._profile_model_ready(base[side])
        for side in ("away", "home")
    }
    if not any(needed.values()):
        return base, {
            "version": MODEL_VERSION,
            "source": "existing_team_profile",
            "fallback_used": False,
            "repaired_sides": [],
        }

    local, local_diag = local_exact_profiles(game, as_of_day)
    repaired_sides: list[str] = []
    for side in ("away", "home"):
        if needed[side] and prior._profile_model_ready(local.get(side) or {}):
            base[side] = dict(local[side])
            repaired_sides.append(side)

    if all(prior._profile_model_ready(base[side]) for side in ("away", "home")):
        diag = dict(local_diag)
        diag["fallback_used"] = bool(repaired_sides)
        diag["repaired_sides"] = repaired_sides
        return base, diag

    # Preserve the proven V1 live fallback only for fields not covered locally.
    return prior.enrich_matchup_model_profiles(game, as_of_day, base)


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SNAPSHOT_PATH",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_matchup_model_profiles",
    "local_exact_profiles",
    "local_snapshot_revision",
]
