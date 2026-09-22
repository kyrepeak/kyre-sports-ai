"""Pitch-mix matchup helpers for MLB Matchup Intelligence V2 Step 5.

Step 5 compares the opposing starter's actual pitch usage with the selected
hitter's Statcast results against those pitch types. All outputs are descriptive
matchup context only. This module does not calculate game-level hit probability,
fair odds, Monte Carlo outcomes, calibration or ranking changes.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Any

import pandas as pd

import mlb_matchup_rankings_v17 as statcast_feed

PITCH_MIN_SAMPLE = 8
PITCH_FULL_SAMPLE = 45
HAND_FILTER_MIN_PITCHES = 75
MAX_ARSENAL_PITCHES = 6

PITCH_NAMES = {
    "FF": "4-Seam",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curve",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "SV": "Slurve",
    "CS": "Slow Curve",
    "KN": "Knuckleball",
}

WHIFF_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
}
SWING_CONTACT_DESCRIPTIONS = {
    "foul",
    "foul_bunt",
    "foul_tip",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
    "hit_into_play_out",
}


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _series_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def pitch_name(code: Any) -> str:
    text = str(code or "—")
    return PITCH_NAMES.get(text, text)


def sample_reliability(pitches: int) -> float:
    """Pitch-type evidence is ignored below 8 pitches and capped at 45 pitches."""
    count = max(0, int(pitches or 0))
    if count < PITCH_MIN_SAMPLE:
        return 0.0
    return _clamp(count / float(PITCH_FULL_SAMPLE), 0.0, 1.0)


def starter_arsenal_from_frame(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if frame is None or frame.empty or "pitch_type" not in frame.columns:
        return []
    values = frame["pitch_type"].dropna().astype(str)
    counts = Counter(x for x in values if x and x.lower() != "nan")
    total = sum(counts.values())
    if total <= 0:
        return []
    rows = []
    for code, count in counts.most_common(MAX_ARSENAL_PITCHES):
        rows.append(
            {
                "code": code,
                "name": pitch_name(code),
                "starter_pitches": int(count),
                "usage": count / total,
            }
        )
    return rows


def filter_hitter_for_starter_hand(
    frame: pd.DataFrame | None,
    starter_hand: Any,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Use same-hand Statcast history only when its sample is large enough."""
    if frame is None or frame.empty:
        return frame, {"applied": False, "hand": str(starter_hand or "—"), "rows": 0, "reason": "no hitter Statcast rows"}
    hand = str(starter_hand or "").strip().upper()[:1]
    if hand not in {"L", "R"} or "p_throws" not in frame.columns:
        return frame, {"applied": False, "hand": hand or "—", "rows": len(frame), "reason": "starter hand unavailable"}
    same = frame[frame["p_throws"].astype(str).str.upper().str.startswith(hand)].copy()
    if len(same) >= HAND_FILTER_MIN_PITCHES:
        return same, {"applied": True, "hand": hand, "rows": len(same), "reason": "same-hand sample verified"}
    return frame, {
        "applied": False,
        "hand": hand,
        "rows": len(frame),
        "same_hand_rows": len(same),
        "reason": f"same-hand sample below {HAND_FILTER_MIN_PITCHES} pitches; using all-hand pitch-type history",
    }


def pitch_type_performance(frame: pd.DataFrame | None, code: str) -> dict[str, Any]:
    if frame is None or frame.empty or "pitch_type" not in frame.columns:
        return {
            "code": str(code),
            "pitches": 0,
            "reliability": 0.0,
            "swings": 0,
            "whiffs": 0,
            "contact_pct": None,
            "whiff_pct": None,
            "xba": None,
            "xba_bip": 0,
            "avg_ev": None,
            "hard_hit_pct": None,
            "bbe": 0,
        }

    subset = frame[frame["pitch_type"].astype(str) == str(code)].copy()
    pitches = len(subset)
    descriptions = (
        subset["description"].fillna("").astype(str).str.lower()
        if "description" in subset.columns
        else pd.Series([""] * pitches, index=subset.index, dtype=str)
    )
    whiffs = int(descriptions.isin(WHIFF_DESCRIPTIONS).sum())
    contacts = int(descriptions.isin(SWING_CONTACT_DESCRIPTIONS).sum())
    swings = whiffs + contacts
    whiff_pct = whiffs / swings if swings > 0 else None
    contact_pct = contacts / swings if swings > 0 else None

    xba_values = _series_numeric(subset, "estimated_ba_using_speedangle").dropna()
    ev_values = _series_numeric(subset, "launch_speed").dropna()
    xba = float(xba_values.mean()) if len(xba_values) >= 3 else None
    avg_ev = float(ev_values.mean()) if len(ev_values) >= 3 else None
    hard_hit_pct = float((ev_values >= 95.0).mean()) if len(ev_values) >= 3 else None

    return {
        "code": str(code),
        "pitches": pitches,
        "reliability": sample_reliability(pitches),
        "swings": swings,
        "whiffs": whiffs,
        "contact_pct": contact_pct,
        "whiff_pct": whiff_pct,
        "xba": xba,
        "xba_bip": len(xba_values),
        "avg_ev": avg_ev,
        "hard_hit_pct": hard_hit_pct,
        "bbe": len(ev_values),
    }


def _standardized_component(perf: dict[str, Any]) -> tuple[float | None, int]:
    """Return hitter-friendly pitch-type component in [-1, 1] and signal count."""
    signals: list[float] = []
    xba = _finite(perf.get("xba"))
    contact = _finite(perf.get("contact_pct"))
    whiff = _finite(perf.get("whiff_pct"))
    ev = _finite(perf.get("avg_ev"))
    hard = _finite(perf.get("hard_hit_pct"))

    if xba is not None:
        signals.append(_clamp((xba - 0.250) / 0.110, -1.0, 1.0))
    if contact is not None:
        signals.append(_clamp((contact - 0.750) / 0.160, -1.0, 1.0))
    if whiff is not None:
        signals.append(_clamp((0.250 - whiff) / 0.160, -1.0, 1.0))
    if ev is not None:
        signals.append(_clamp((ev - 88.5) / 6.5, -1.0, 1.0))
    if hard is not None:
        signals.append(_clamp((hard - 0.400) / 0.220, -1.0, 1.0))

    if not signals:
        return None, 0
    return sum(signals) / len(signals), len(signals)


def _weighted_metric(rows: list[dict[str, Any]], metric: str) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = _finite(row.get(metric))
        if value is None:
            continue
        weight = float(row.get("usage") or 0.0) * float(row.get("reliability") or 0.0)
        if weight <= 0:
            continue
        numerator += value * weight
        denominator += weight
    return numerator / denominator if denominator > 0 else None


def matchup_label(score: int | None) -> str:
    if score is None:
        return "PENDING"
    if score >= 66:
        return "STRONG PITCH-MIX EDGE"
    if score >= 57:
        return "SLIGHT PITCH-MIX EDGE"
    if score >= 44:
        return "NEUTRAL PITCH-MIX"
    if score >= 35:
        return "TOUGH PITCH-MIX"
    return "VERY TOUGH PITCH-MIX"


def _data_quality(
    arsenal: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    pitcher_verified: bool,
    hitter_verified: bool,
    hand_info: dict[str, Any],
) -> tuple[int, dict[str, tuple[int, int]]]:
    identity = 10 if pitcher_verified and hitter_verified else 5 if pitcher_verified or hitter_verified else 0
    arsenal_points = 25 if arsenal and sum(float(x.get("usage") or 0.0) for x in arsenal) >= 0.70 else 12 if arsenal else 0
    hand_points = 10 if hand_info.get("applied") else 5 if hand_info.get("hand") in {"L", "R"} else 0
    weighted_coverage = sum(float(x.get("usage") or 0.0) * float(x.get("reliability") or 0.0) for x in rows)
    sample_points = int(round(30 * _clamp(weighted_coverage / 0.80, 0.0, 1.0)))
    key_metrics = 0
    if _weighted_metric(rows, "xba") is not None:
        key_metrics += 7
    if _weighted_metric(rows, "contact_pct") is not None:
        key_metrics += 5
    if _weighted_metric(rows, "whiff_pct") is not None:
        key_metrics += 5
    if _weighted_metric(rows, "avg_ev") is not None:
        key_metrics += 4
    if _weighted_metric(rows, "hard_hit_pct") is not None:
        key_metrics += 4
    components = {
        "Verified Statcast feeds": (identity, 10),
        "Starter arsenal coverage": (arsenal_points, 25),
        "Same-hand context": (hand_points, 10),
        "Pitch-type sample depth": (sample_points, 30),
        "Pitch-type metrics": (key_metrics, 25),
    }
    return sum(v[0] for v in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE PITCH DATA"
    if score >= 75:
        return "STRONG PITCH DATA"
    if score >= 60:
        return "USABLE PITCH DATA"
    if score >= 40:
        return "PARTIAL PITCH DATA"
    return "LOW PITCH DATA"


def build_pitch_mix_profile(
    foundation: dict[str, Any],
    pitcher_payload: dict[str, Any] | None,
    hitter_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    pitcher_payload = pitcher_payload or {}
    hitter_payload = hitter_payload or {}
    pitcher_verified = pitcher_payload.get("status") == "VERIFIED"
    hitter_verified = hitter_payload.get("status") == "VERIFIED"
    pitcher_frame = pitcher_payload.get("frame") if pitcher_verified else None
    hitter_frame = hitter_payload.get("frame") if hitter_verified else None

    arsenal = starter_arsenal_from_frame(pitcher_frame)
    filtered_hitter, hand_info = filter_hitter_for_starter_hand(
        hitter_frame,
        foundation.get("starter_hand"),
    )

    rows: list[dict[str, Any]] = []
    weighted_component = 0.0
    weighted_denominator = 0.0
    for pitch in arsenal:
        perf = pitch_type_performance(filtered_hitter, str(pitch["code"]))
        component, signals = _standardized_component(perf)
        reliability = float(perf.get("reliability") or 0.0)
        usage = float(pitch.get("usage") or 0.0)
        effective_weight = usage * reliability if component is not None else 0.0
        row = {
            **pitch,
            **perf,
            "component": component,
            "signal_count": signals,
            "effective_weight": effective_weight,
        }
        rows.append(row)
        if component is not None and effective_weight > 0:
            weighted_component += component * effective_weight
            weighted_denominator += effective_weight

    combined = weighted_component / weighted_denominator if weighted_denominator > 0 else None
    score = int(round(_clamp(50.0 + 22.0 * combined, 25.0, 75.0))) if combined is not None else None
    coverage = _clamp(weighted_denominator, 0.0, 1.0)
    arsenal_coverage = _clamp(sum(float(x.get("usage") or 0.0) for x in arsenal), 0.0, 1.0)

    quality_score, components = _data_quality(
        arsenal,
        rows,
        pitcher_verified,
        hitter_verified,
        hand_info,
    )

    return {
        **foundation,
        "pitcher_statcast_status": pitcher_payload.get("status") or "PENDING",
        "hitter_statcast_status": hitter_payload.get("status") or "PENDING",
        "pitcher_statcast_rows": int(pitcher_payload.get("rows") or 0),
        "hitter_statcast_rows": int(hitter_payload.get("rows") or 0),
        "pitcher_statcast_error": pitcher_payload.get("error") or "",
        "hitter_statcast_error": hitter_payload.get("error") or "",
        "hand_filter": hand_info,
        "arsenal": arsenal,
        "pitch_rows": rows,
        "arsenal_coverage": arsenal_coverage,
        "pitch_mix_score": score,
        "pitch_mix_label": matchup_label(score),
        "pitch_mix_coverage": coverage,
        "weighted_xba": _weighted_metric(rows, "xba"),
        "weighted_contact_pct": _weighted_metric(rows, "contact_pct"),
        "weighted_whiff_pct": _weighted_metric(rows, "whiff_pct"),
        "weighted_avg_ev": _weighted_metric(rows, "avg_ev"),
        "weighted_hard_hit_pct": _weighted_metric(rows, "hard_hit_pct"),
        "pitch_mix_data_score": int(quality_score),
        "pitch_mix_data_label": quality_label(int(quality_score)),
        "pitch_mix_data_components": components,
    }


def fetch_pitch_mix_inputs(player_id: int, starter_id: int, season: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use the existing shared one-hour successful Statcast cache for both players."""
    pitcher = statcast_feed._statcast_rows(int(starter_id), int(season), "pitcher") if starter_id else {"status": "PENDING", "rows": 0, "frame": None, "error": "missing starter id"}
    hitter = statcast_feed._statcast_rows(int(player_id), int(season), "batter") if player_id else {"status": "PENDING", "rows": 0, "frame": None, "error": "missing hitter id"}
    return pitcher, hitter


__all__ = [
    "HAND_FILTER_MIN_PITCHES",
    "MAX_ARSENAL_PITCHES",
    "PITCH_FULL_SAMPLE",
    "PITCH_MIN_SAMPLE",
    "build_pitch_mix_profile",
    "fetch_pitch_mix_inputs",
    "filter_hitter_for_starter_hand",
    "matchup_label",
    "pitch_name",
    "pitch_type_performance",
    "quality_label",
    "sample_reliability",
    "starter_arsenal_from_frame",
]
