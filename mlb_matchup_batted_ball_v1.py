"""Batted-ball quality helpers for MLB Matchup Intelligence V2 Step 6.

Step 6 describes what happens when the selected hitter puts the ball in play:
exit velocity, hard-hit rate, barrels, launch profile, batted-ball distribution,
spray tendencies and Statcast expected batting average on contact. Outputs are
context-only and do not calculate game-level hit probability, fair odds, Monte
Carlo outcomes, calibration or rankings.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

import mlb_matchup_rankings_v17 as statcast_feed

BBE_MIN_SAMPLE = 20
BBE_FULL_SAMPLE = 160
HARD_HIT_MPH = 95.0
SWEET_SPOT_LOW = 8.0
SWEET_SPOT_HIGH = 32.0
SPRAY_CENTER_X = 125.42
SPRAY_HOME_Y = 198.27
SPRAY_CENTER_DEGREES = 15.0


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def sample_reliability(bbe: int) -> float:
    """No contact-quality score below 20 BBE; full reliability at 160 BBE."""
    count = max(0, int(bbe or 0))
    if count < BBE_MIN_SAMPLE:
        return 0.0
    return _clamp(count / float(BBE_FULL_SAMPLE), 0.0, 1.0)


def _batted_ball_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    mask = pd.Series(False, index=frame.index)
    for column in ("launch_speed", "launch_angle", "bb_type", "estimated_ba_using_speedangle"):
        if column in frame.columns:
            mask = mask | frame[column].notna()
    return frame.loc[mask].copy()


def _distribution(frame: pd.DataFrame, column: str) -> tuple[dict[str, int], int]:
    if frame is None or frame.empty or column not in frame.columns:
        return {}, 0
    values = frame[column].fillna("").astype(str).str.lower()
    keys = ("ground_ball", "line_drive", "fly_ball", "popup")
    counts = {key: int((values == key).sum()) for key in keys}
    total = sum(counts.values())
    return counts, total


def _launch_profile_label(gb: float | None, ld: float | None, fb: float | None, popup: float | None) -> str:
    if gb is None or ld is None or fb is None or popup is None:
        return "PENDING"
    if ld >= 0.25:
        return "LINE-DRIVE HEAVY"
    if gb >= 0.48:
        return "GROUND-BALL HEAVY"
    if fb + popup >= 0.47:
        return "AIR-BALL HEAVY"
    return "BALANCED LAUNCH PROFILE"


def _spray_profile(frame: pd.DataFrame) -> dict[str, Any]:
    required = {"hc_x", "hc_y", "stand"}
    if frame is None or frame.empty or not required.issubset(frame.columns):
        return {
            "spray_bip": 0,
            "left_pct": None,
            "center_pct": None,
            "right_pct": None,
            "pull_pct": None,
            "oppo_pct": None,
            "spray_label": "PENDING",
        }

    hx = pd.to_numeric(frame["hc_x"], errors="coerce")
    hy = pd.to_numeric(frame["hc_y"], errors="coerce")
    stand = frame["stand"].fillna("").astype(str).str.upper().str[:1]
    valid = hx.notna() & hy.notna() & stand.isin(["L", "R"])
    if not valid.any():
        return {
            "spray_bip": 0,
            "left_pct": None,
            "center_pct": None,
            "right_pct": None,
            "pull_pct": None,
            "oppo_pct": None,
            "spray_label": "PENDING",
        }

    dx = hx.loc[valid] - SPRAY_CENTER_X
    dy = SPRAY_HOME_Y - hy.loc[valid]
    angles = pd.Series(
        [math.degrees(math.atan2(float(x), float(y))) for x, y in zip(dx, dy)],
        index=dx.index,
        dtype=float,
    )
    left = angles < -SPRAY_CENTER_DEGREES
    right = angles > SPRAY_CENTER_DEGREES
    center = ~(left | right)
    total = len(angles)

    stands = stand.loc[valid]
    pull = ((stands == "R") & left) | ((stands == "L") & right)
    oppo = ((stands == "R") & right) | ((stands == "L") & left)
    pull_pct = float(pull.mean()) if total else None
    oppo_pct = float(oppo.mean()) if total else None
    if pull_pct is None or oppo_pct is None:
        label = "PENDING"
    elif pull_pct >= 0.46:
        label = "PULL HEAVY"
    elif oppo_pct >= 0.31:
        label = "OPPOSITE-FIELD HEAVY"
    else:
        label = "BALANCED SPRAY"

    return {
        "spray_bip": total,
        "left_pct": float(left.mean()),
        "center_pct": float(center.mean()),
        "right_pct": float(right.mean()),
        "pull_pct": pull_pct,
        "oppo_pct": oppo_pct,
        "spray_label": label,
    }


def _quality_component(metrics: dict[str, Any]) -> tuple[float | None, int]:
    """Return hitter-friendly contact-quality component in [-1, 1]."""
    signals: list[float] = []
    avg_ev = _finite(metrics.get("avg_ev"))
    hard = _finite(metrics.get("hard_hit_pct"))
    barrel = _finite(metrics.get("barrel_pct"))
    xba_contact = _finite(metrics.get("xba_contact"))
    sweet = _finite(metrics.get("sweet_spot_pct"))
    ld = _finite(metrics.get("line_drive_pct"))
    popup = _finite(metrics.get("popup_pct"))

    if avg_ev is not None:
        signals.append(_clamp((avg_ev - 89.0) / 6.0, -1.0, 1.0))
    if hard is not None:
        signals.append(_clamp((hard - 0.40) / 0.22, -1.0, 1.0))
    if barrel is not None:
        signals.append(_clamp((barrel - 0.08) / 0.10, -1.0, 1.0))
    if xba_contact is not None:
        signals.append(_clamp((xba_contact - 0.310) / 0.140, -1.0, 1.0))
    if sweet is not None:
        signals.append(_clamp((sweet - 0.33) / 0.18, -1.0, 1.0))
    if ld is not None:
        signals.append(_clamp((ld - 0.21) / 0.12, -1.0, 1.0) * 0.75)
    if popup is not None:
        signals.append(_clamp((0.08 - popup) / 0.10, -1.0, 1.0) * 0.50)

    if not signals:
        return None, 0
    return sum(signals) / len(signals), len(signals)


def batted_ball_label(score: int | None) -> str:
    if score is None:
        return "PENDING"
    if score >= 65:
        return "ELITE CONTACT QUALITY"
    if score >= 58:
        return "STRONG CONTACT QUALITY"
    if score >= 44:
        return "AVERAGE CONTACT QUALITY"
    if score >= 36:
        return "WEAK CONTACT QUALITY"
    return "VERY WEAK CONTACT QUALITY"


def _data_quality(metrics: dict[str, Any], verified: bool) -> tuple[int, dict[str, tuple[int, int]]]:
    feed = 20 if verified else 0
    ev = 20 if metrics.get("ev_bbe", 0) >= BBE_MIN_SAMPLE else 10 if metrics.get("ev_bbe", 0) > 0 else 0
    launch = 15 if metrics.get("launch_bbe", 0) >= BBE_MIN_SAMPLE else 7 if metrics.get("launch_bbe", 0) > 0 else 0
    barrel = 15 if metrics.get("barrel_bbe", 0) >= BBE_MIN_SAMPLE else 7 if metrics.get("barrel_bbe", 0) > 0 else 0
    bbt = 10 if metrics.get("bb_type_bbe", 0) >= BBE_MIN_SAMPLE else 5 if metrics.get("bb_type_bbe", 0) > 0 else 0
    xba = 10 if metrics.get("xba_bbe", 0) >= BBE_MIN_SAMPLE else 5 if metrics.get("xba_bbe", 0) > 0 else 0
    spray = 10 if metrics.get("spray_bip", 0) >= BBE_MIN_SAMPLE else 5 if metrics.get("spray_bip", 0) > 0 else 0
    components = {
        "Verified Statcast feed": (feed, 20),
        "Exit-velocity sample": (ev, 20),
        "Launch-angle sample": (launch, 15),
        "Barrel classification": (barrel, 15),
        "Batted-ball types": (bbt, 10),
        "Expected BA on contact": (xba, 10),
        "Spray sample": (spray, 10),
    }
    return sum(v[0] for v in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE BATTED-BALL DATA"
    if score >= 75:
        return "STRONG BATTED-BALL DATA"
    if score >= 60:
        return "USABLE BATTED-BALL DATA"
    if score >= 40:
        return "PARTIAL BATTED-BALL DATA"
    return "LOW BATTED-BALL DATA"


def batted_ball_metrics(frame: pd.DataFrame | None) -> dict[str, Any]:
    bbe_frame = _batted_ball_frame(frame)
    if bbe_frame.empty:
        return {
            "bbe": 0,
            "ev_bbe": 0,
            "launch_bbe": 0,
            "barrel_bbe": 0,
            "bb_type_bbe": 0,
            "xba_bbe": 0,
            "avg_ev": None,
            "max_ev": None,
            "hard_hit_pct": None,
            "barrel_pct": None,
            "avg_launch_angle": None,
            "sweet_spot_pct": None,
            "xba_contact": None,
            "ground_ball_pct": None,
            "line_drive_pct": None,
            "fly_ball_pct": None,
            "popup_pct": None,
            "launch_profile_label": "PENDING",
            **_spray_profile(pd.DataFrame()),
        }

    ev = _numeric(bbe_frame, "launch_speed").dropna()
    la = _numeric(bbe_frame, "launch_angle").dropna()
    xba = _numeric(bbe_frame, "estimated_ba_using_speedangle").dropna()
    lsa = _numeric(bbe_frame, "launch_speed_angle").dropna()
    dist, dist_total = _distribution(bbe_frame, "bb_type")

    gb = dist.get("ground_ball", 0) / dist_total if dist_total else None
    ld = dist.get("line_drive", 0) / dist_total if dist_total else None
    fb = dist.get("fly_ball", 0) / dist_total if dist_total else None
    popup = dist.get("popup", 0) / dist_total if dist_total else None
    spray = _spray_profile(bbe_frame)

    return {
        "bbe": len(bbe_frame),
        "ev_bbe": len(ev),
        "launch_bbe": len(la),
        "barrel_bbe": len(lsa),
        "bb_type_bbe": dist_total,
        "xba_bbe": len(xba),
        "avg_ev": float(ev.mean()) if len(ev) else None,
        "max_ev": float(ev.max()) if len(ev) else None,
        "hard_hit_pct": float((ev >= HARD_HIT_MPH).mean()) if len(ev) else None,
        "barrel_pct": float((lsa == 6).mean()) if len(lsa) else None,
        "avg_launch_angle": float(la.mean()) if len(la) else None,
        "sweet_spot_pct": float(((la >= SWEET_SPOT_LOW) & (la <= SWEET_SPOT_HIGH)).mean()) if len(la) else None,
        "xba_contact": float(xba.mean()) if len(xba) else None,
        "ground_ball_pct": gb,
        "line_drive_pct": ld,
        "fly_ball_pct": fb,
        "popup_pct": popup,
        "launch_profile_label": _launch_profile_label(gb, ld, fb, popup),
        **spray,
    }


def build_batted_ball_profile(
    foundation: dict[str, Any],
    hitter_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    hitter_payload = hitter_payload or {}
    verified = hitter_payload.get("status") == "VERIFIED"
    frame = hitter_payload.get("frame") if verified else None
    metrics = batted_ball_metrics(frame)
    reliability = sample_reliability(metrics.get("ev_bbe") or metrics.get("bbe") or 0)
    raw_component, signal_count = _quality_component(metrics)
    raw_score = int(round(_clamp(50.0 + 24.0 * raw_component, 25.0, 75.0))) if raw_component is not None else None
    score = None
    if raw_score is not None and reliability > 0:
        score = int(round(50.0 + (raw_score - 50.0) * reliability))

    quality_score, components = _data_quality(metrics, verified)
    return {
        **foundation,
        **metrics,
        "hitter_statcast_status": hitter_payload.get("status") or "PENDING",
        "hitter_statcast_rows": int(hitter_payload.get("rows") or 0),
        "hitter_statcast_error": hitter_payload.get("error") or "",
        "batted_ball_reliability": reliability,
        "batted_ball_raw_score": raw_score,
        "batted_ball_score": score,
        "batted_ball_label": batted_ball_label(score),
        "batted_ball_signal_count": signal_count,
        "batted_ball_data_score": int(quality_score),
        "batted_ball_data_label": quality_label(int(quality_score)),
        "batted_ball_data_components": components,
    }


def fetch_batted_ball_input(player_id: int, season: int) -> dict[str, Any]:
    """Reuse the shared one-hour successful Statcast batter cache from Step 5."""
    if not player_id:
        return {"status": "PENDING", "rows": 0, "frame": None, "error": "missing hitter id"}
    return statcast_feed._statcast_rows(int(player_id), int(season), "batter")


__all__ = [
    "BBE_FULL_SAMPLE",
    "BBE_MIN_SAMPLE",
    "HARD_HIT_MPH",
    "SWEET_SPOT_HIGH",
    "SWEET_SPOT_LOW",
    "batted_ball_metrics",
    "build_batted_ball_profile",
    "fetch_batted_ball_input",
    "sample_reliability",
]
