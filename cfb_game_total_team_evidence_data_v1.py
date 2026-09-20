"""Team Evidence data handoff for page cleanup Step 3.

Preserves the already-verified Step-1 completed-game sample when the shared
runtime display profile is non-empty but lacks usable scored games. This module
does not fetch data, modify model math, or alter Team Evidence presentation.
"""
from __future__ import annotations

from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL TEAM EVIDENCE DATA V1 • PAGE CLEANUP STEP 3"
REQUIRED_FIELDS = ("ppg", "allowed_pg", "point_diff_pg", "recent_form")


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scored_rows(profile: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in (profile or {}).get("completed_games") or []:
        if not isinstance(raw, Mapping):
            continue
        pf = _float(raw.get("points_for"))
        pa = _float(raw.get("points_against"))
        if pf is None or pa is None:
            continue
        rows.append(dict(raw))
    return rows


def has_team_evidence_sample(profile: Mapping[str, Any] | None) -> bool:
    return bool(_scored_rows(profile))


_EVIDENCE_KEYS = (
    "completed_games",
    "record",
    "record_text",
    "ppg",
    "points_allowed_pg",
    "point_diff_pg",
    "recent_form",
    "recent_record",
    "recent_ppg",
    "recent_points_allowed_pg",
    "recent_point_diff_pg",
    "home_record",
    "away_record",
    "neutral_record",
    "sos_opponent_win_pct",
    "sos_coverage",
    "data_quality",
    "data_source",
)


def repair_team_evidence_profile(
    display_profile: Mapping[str, Any] | None,
    step1_profile: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """Repair an incomplete display profile from the verified Step-1 profile.

    A display profile with its own usable scored completed-game sample remains
    untouched. Only an incomplete sample may inherit Step-1 evidence.
    """
    display = dict(display_profile or {})
    if has_team_evidence_sample(display):
        return display, False

    step1 = dict(step1_profile or {})
    if not has_team_evidence_sample(step1):
        return display, False

    out = dict(display)
    for key in _EVIDENCE_KEYS:
        value = step1.get(key)
        if value in (None, "", "—", [], {}):
            continue
        if isinstance(value, list):
            out[key] = [
                dict(row) if isinstance(row, Mapping) else row
                for row in value
            ]
        elif isinstance(value, Mapping):
            out[key] = dict(value)
        else:
            out[key] = value

    # Keep runtime/display identity extras but make the evidence provenance clear.
    source = str(step1.get("data_source") or "").strip()
    if source:
        out["team_evidence_source"] = source
    out["team_evidence_step3_repaired"] = True
    return out, True


def repair_team_evidence_bundle(
    display_away: Mapping[str, Any] | None,
    display_home: Mapping[str, Any] | None,
    step1_away: Mapping[str, Any] | None,
    step1_home: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    away, away_repaired = repair_team_evidence_profile(display_away, step1_away)
    home, home_repaired = repair_team_evidence_profile(display_home, step1_home)
    repaired = [
        side
        for side, active in (("away", away_repaired), ("home", home_repaired))
        if active
    ]
    return away, home, {
        "version": MODEL_VERSION,
        "repaired_sides": repaired,
        "fallback_used": bool(repaired),
        "required_fields": list(REQUIRED_FIELDS),
        "data_green": (
            has_team_evidence_sample(away)
            and has_team_evidence_sample(home)
        ),
    }


__all__ = [
    "MODEL_VERSION",
    "REQUIRED_FIELDS",
    "has_team_evidence_sample",
    "repair_team_evidence_bundle",
    "repair_team_evidence_profile",
]
