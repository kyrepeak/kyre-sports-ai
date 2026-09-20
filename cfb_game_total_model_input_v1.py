"""Normalized model-input fallback for CFB Game Total page cleanup Step 1.

This module does not modify Game Total math. It repairs only missing/CHECK team
profiles with exact-event, pre-kickoff completed-game evidence from the already
certified Runtime Snapshot V2 source used by Step 3.

Source routing:
1. Existing cfb_team_data_v2 profile when model-ready.
2. Certified Runtime Snapshot V2 exact event/team profile.
3. Fail closed by returning the original profile unchanged.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_game_total_step3_form_v1 as runtime_owner
import cfb_team_data_v1 as quality_owner

MODEL_VERSION = "CFB GAME TOTAL MODEL INPUT V1 • PAGE CLEANUP STEP 1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any) -> float | None:
    return runtime_owner._float(value)


def _profile_model_ready(profile: Mapping[str, Any] | None) -> bool:
    row = profile or {}
    try:
        games = int((row.get("record") or {}).get("games") or 0)
    except Exception:
        games = 0
    grade = _clean((row.get("data_quality") or {}).get("grade")).upper()
    return bool(
        games > 0
        and _f(row.get("ppg")) is not None
        and _f(row.get("points_allowed_pg")) is not None
        and grade != "CHECK"
    )


def _record(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    wins = losses = ties = 0
    for row in rows:
        pf = _f(row.get("points_for"))
        pa = _f(row.get("points_against"))
        if pf is None or pa is None:
            continue
        if pf > pa:
            wins += 1
        elif pf < pa:
            losses += 1
        else:
            ties += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "games": wins + losses + ties,
    }


def _record_text(record: Mapping[str, Any]) -> str:
    return (
        f"{int(record.get('wins') or 0)}-{int(record.get('losses') or 0)}"
        + (
            f"-{int(record.get('ties') or 0)}"
            if int(record.get("ties") or 0)
            else ""
        )
    )


def _mean(rows: list[float]) -> float | None:
    return sum(rows) / len(rows) if rows else None


def _normalized_completed_rows(
    profile: Mapping[str, Any],
    target_day: str,
) -> list[dict[str, Any]]:
    cutoff = _clean(target_day)[:10]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in profile.get("completed_games") or []:
        if not isinstance(raw, Mapping):
            continue
        day = _clean(raw.get("date"))[:10]
        if cutoff and day and day >= cutoff:
            continue
        pf = _f(raw.get("points_for"))
        pa = _f(raw.get("points_against"))
        if pf is None or pa is None:
            continue
        event_id = _clean(raw.get("event_id"))
        key = event_id or f"{day}|{_clean(raw.get('opponent_id'))}|{pf}|{pa}"
        if key in seen:
            continue
        seen.add(key)
        result = "W" if pf > pa else "L" if pf < pa else "T"
        out.append({
            "event_id": event_id,
            "date": day,
            "opponent": _clean(raw.get("opponent")),
            "opponent_id": _clean(raw.get("opponent_id")),
            "location": _clean(raw.get("location")),
            "result": result,
            "points_for": float(pf),
            "points_against": float(pa),
            "score": f"{int(pf)}-{int(pa)}",
            "margin": float(pf - pa),
        })
    out.sort(key=lambda row: (_clean(row.get("date")), _clean(row.get("event_id"))))
    return out


def _split_record(rows: list[Mapping[str, Any]], location: str) -> dict[str, int]:
    return _record([
        row for row in rows
        if _clean(row.get("location")).casefold() == location.casefold()
    ])


def _repair_profile(
    base: Mapping[str, Any],
    runtime_profile: Mapping[str, Any],
    selected_side: Mapping[str, Any],
    target_day: str,
) -> tuple[dict[str, Any], bool]:
    completed = _normalized_completed_rows(runtime_profile, target_day)
    if not completed:
        return dict(base or {}), False

    points_for = [float(row["points_for"]) for row in completed]
    points_against = [float(row["points_against"]) for row in completed]
    ppg = _mean(points_for)
    allowed = _mean(points_against)
    if ppg is None or allowed is None:
        return dict(base or {}), False

    record = _record(completed)
    if int(record.get("games") or 0) <= 0:
        return dict(base or {}), False

    recent = completed[-5:]
    recent_record = _record(recent)
    recent_for = [float(row["points_for"]) for row in recent]
    recent_against = [float(row["points_against"]) for row in recent]
    recent_ppg = _mean(recent_for)
    recent_allowed = _mean(recent_against)

    repaired = dict(base or {})
    repaired.update({
        "team": (
            _clean(repaired.get("team"))
            or _clean(runtime_profile.get("team"))
            or _clean(selected_side.get("team"))
        ),
        "team_id": (
            _clean(runtime_profile.get("team_id"))
            or _clean(selected_side.get("team_id"))
        ),
        "record": record,
        "record_text": _record_text(record),
        "ppg": float(ppg),
        "points_allowed_pg": float(allowed),
        "point_diff_pg": float(ppg - allowed),
        "home_record": _split_record(completed, "home"),
        "away_record": _split_record(completed, "away"),
        "neutral_record": _split_record(completed, "neutral"),
        "recent_form": "".join(str(row.get("result") or "") for row in recent),
        "recent_record": recent_record,
        "recent_ppg": float(recent_ppg) if recent_ppg is not None else None,
        "recent_points_allowed_pg": (
            float(recent_allowed) if recent_allowed is not None else None
        ),
        "recent_point_diff_pg": (
            float(recent_ppg - recent_allowed)
            if recent_ppg is not None and recent_allowed is not None
            else None
        ),
        "completed_games": completed,
        "data_source": (
            "Certified Runtime Snapshot V2 • exact-event pre-kickoff completed games"
        ),
    })
    repaired["data_quality"] = quality_owner._quality(repaired)
    return repaired, _profile_model_ready(repaired)


def enrich_matchup_model_profiles(
    game: Mapping[str, Any],
    as_of_day: str,
    profiles: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Repair only model-incomplete sides from exact Runtime Snapshot V2 evidence."""
    base = profiles or {}
    outputs = {
        "away": dict(base.get("away") or {}),
        "home": dict(base.get("home") or {}),
    }
    needed = {
        side: not _profile_model_ready(outputs[side])
        for side in ("away", "home")
    }
    if not any(needed.values()):
        return outputs, {
            "version": MODEL_VERSION,
            "fallback_used": False,
            "source": "existing_team_profile",
            "repaired_sides": [],
        }

    try:
        payload = runtime_owner.runtime_snapshot_v2._load_v2_snapshot()
        selected = runtime_owner._runtime_v2_selected_row(payload, game, str(as_of_day))
        profile_index = runtime_owner._runtime_v2_profile_index(payload, str(as_of_day))
    except Exception as exc:
        return outputs, {
            "version": MODEL_VERSION,
            "fallback_used": False,
            "source": "runtime_v2_error",
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "repaired_sides": [],
        }

    if not selected:
        return outputs, {
            "version": MODEL_VERSION,
            "fallback_used": False,
            "source": _clean(payload.get("_runtime_snapshot_source")) or "runtime_v2",
            "selected_event_found": False,
            "generated_at": payload.get("generated_at"),
            "window": payload.get("window"),
            "repaired_sides": [],
        }

    repaired_sides: list[str] = []
    side_diag: dict[str, Any] = {}
    for side in ("away", "home"):
        if not needed[side]:
            side_diag[side] = {"source": "existing_team_profile", "repaired": False}
            continue
        selected_side = (
            selected.get(side)
            if isinstance(selected.get(side), Mapping)
            else {}
        )
        team_id = _clean(selected_side.get("team_id"))
        runtime_profile = (
            profile_index.get(team_id)
            if team_id and isinstance(profile_index.get(team_id), Mapping)
            else selected_side
        )
        repaired, ok = _repair_profile(
            outputs[side],
            runtime_profile or {},
            selected_side,
            str(as_of_day),
        )
        if ok:
            outputs[side] = repaired
            repaired_sides.append(side)
        side_diag[side] = {
            "source": (
                "certified_runtime_snapshot_v2"
                if ok else "existing_team_profile_unrepaired"
            ),
            "repaired": bool(ok),
            "team_id": team_id,
            "sample_games": int((repaired.get("record") or {}).get("games") or 0),
            "quality_grade": _clean(
                (repaired.get("data_quality") or {}).get("grade")
            ),
        }

    return outputs, {
        "version": MODEL_VERSION,
        "fallback_used": bool(repaired_sides),
        "source": _clean(payload.get("_runtime_snapshot_source")) or "runtime_v2",
        "selected_event_found": True,
        "event_id": selected.get("event_id"),
        "generated_at": payload.get("generated_at"),
        "window": payload.get("window"),
        "repaired_sides": repaired_sides,
        "sides": side_diag,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_profile_model_ready",
    "enrich_matchup_model_profiles",
]
