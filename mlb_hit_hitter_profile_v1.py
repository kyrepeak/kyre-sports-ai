"""MLB Hits Step 3 — player-only hitter true-talent + contact profile.

This helper is additive evidence only. It reads already-certified/frozen Hit
Model V13 data sources through engine.py and does not alter game-level
probability, Monte Carlo, candidate selection, Top-5 order, calibration, history
or sportsbook behavior.

The neutral skill blend is intentionally player-only:
- season AVG carries the large majority of weight,
- xBA enters only when Baseball Savant provides it and is reliability-shrunk,
- recent AVG receives a small reliability-shrunk weight,
- starter, bullpen, park, weather, lineup opportunity and market price are not
  inputs to this profile.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import streamlit as st
import engine as hit_engine

PROFILE_VERSION = "HIT-STEP3-HITTER-PROFILE-V1"

SEASON_WEIGHT = 0.65
XBA_WEIGHT_MAX = 0.25
RECENT_WEIGHT_MAX = 0.10


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _i(value: Any) -> int:
    x = _f(value)
    return int(x) if x is not None else 0


def _rate(value: Any) -> float | None:
    x = _f(value)
    if x is None:
        return None
    if abs(x) > 1:
        x /= 100.0
    return max(0.0, min(1.0, x))


def _blend_skill(
    season_avg: float | None,
    xba: float | None,
    recent_avg: float | None,
    savant_pa: int,
    recent_ab: int,
) -> dict[str, Any]:
    raw: list[tuple[str, float, float]] = []
    if season_avg is not None:
        raw.append(("season", season_avg, SEASON_WEIGHT))
    if xba is not None:
        rel = savant_pa / (savant_pa + 120.0) if savant_pa > 0 else 0.35
        raw.append(("xba", xba, XBA_WEIGHT_MAX * rel))
    if recent_avg is not None and recent_ab > 0:
        rel = recent_ab / (recent_ab + 80.0)
        raw.append(("recent", recent_avg, RECENT_WEIGHT_MAX * rel))

    total = sum(w for _, _, w in raw)
    if total <= 0:
        return {
            "neutral_hit_skill": None,
            "weights": {"season": 0.0, "xba": 0.0, "recent": 0.0},
        }

    weights = {"season": 0.0, "xba": 0.0, "recent": 0.0}
    value = 0.0
    for name, metric, raw_weight in raw:
        weight = raw_weight / total
        weights[name] = weight
        value += metric * weight

    return {
        "neutral_hit_skill": max(0.0, min(0.500, value)),
        "weights": weights,
    }


def _profile_quality(metrics: Mapping[str, Any]) -> int:
    score = 0
    score += 15 if metrics.get("season_avg") is not None else 0
    score += 10 if metrics.get("hit_per_pa") is not None else 0
    score += 10 if metrics.get("k_pct") is not None else 0
    score += 15 if metrics.get("xba") is not None else 0
    score += 10 if metrics.get("recent_avg") is not None else 0
    score += 10 if metrics.get("recent_hit_game_rate") is not None else 0
    score += 10 if metrics.get("avg_ev") is not None else 0
    score += 10 if metrics.get("hard_hit_pct") is not None else 0
    score += 10 if metrics.get("barrel_pct") is not None else 0
    return min(100, score)


def profile_data_label(score: int) -> str:
    if score >= 90:
        return "ELITE PROFILE DATA"
    if score >= 75:
        return "STRONG PROFILE DATA"
    if score >= 60:
        return "USABLE PROFILE DATA"
    if score >= 40:
        return "PARTIAL PROFILE DATA"
    return "LOW PROFILE DATA"


def skill_label(skill: Any) -> str:
    x = _f(skill)
    if x is None:
        return "DATA LIMITED"
    if x >= 0.300:
        return "ELITE HIT SKILL"
    if x >= 0.275:
        return "STRONG HIT SKILL"
    if x >= 0.250:
        return "SOLID HIT SKILL"
    if x < 0.225:
        return "WEAK HIT SKILL"
    return "AVERAGE HIT SKILL"


def _contact_grade(season_avg: float | None, statcast: Mapping[str, Any] | None) -> tuple[str, float | None]:
    if season_avg is None or not statcast:
        return "DATA LIMITED", None
    try:
        _, model = hit_engine.add_statcast(season_avg, dict(statcast))
    except Exception:
        return "DATA LIMITED", None
    return str(model.get("grade") or "DATA LIMITED"), _f(model.get("reliability"))


@st.cache_data(ttl=600, show_spinner=False)
def build_hitter_profile(player_id: int, fallback_season_avg: float | None = None) -> dict[str, Any]:
    """Build one player-only profile from frozen Hit Model source helpers."""
    pid = int(player_id)
    failures: list[str] = []

    try:
        stats = hit_engine.hitter_stats(pid) or {}
    except Exception:
        stats = {}
        failures.append("season_stats_unavailable")

    try:
        recent = hit_engine.recent_form(pid, 10) or {}
    except Exception:
        recent = {}
        failures.append("recent_form_unavailable")

    try:
        statcast = hit_engine.statcast(pid) or {}
    except Exception:
        statcast = {}
        failures.append("statcast_unavailable")

    season_avg = _rate(stats.get("avg"))
    if season_avg is None:
        season_avg = _rate(fallback_season_avg)
    pa = _i(stats.get("plate_appearances"))
    ab = _i(stats.get("at_bats"))
    hits = _i(stats.get("hits"))
    strikeouts = _i(stats.get("strikeouts"))
    hit_per_pa = hits / pa if pa > 0 else None
    k_pct = strikeouts / pa if pa > 0 else None

    recent_avg = _rate(recent.get("avg"))
    recent_ab = _i(recent.get("at_bats"))
    recent_games = _i(recent.get("games"))
    recent_hit_games = _i(recent.get("hit_games"))
    recent_hit_game_rate = (
        recent_hit_games / recent_games if recent_games > 0 else None
    )

    xba = _rate(statcast.get("xba"))
    avg_ev = _f(statcast.get("avg_ev"))
    hard_hit_pct = _rate(statcast.get("hard_hit_rate"))
    barrel_pct = _rate(statcast.get("barrel_rate"))
    savant_pa = _i(statcast.get("pa"))

    blend = _blend_skill(season_avg, xba, recent_avg, savant_pa, recent_ab)
    contact_grade, contact_reliability = _contact_grade(season_avg, statcast)

    metrics = {
        "season_avg": season_avg,
        "hit_per_pa": hit_per_pa,
        "k_pct": k_pct,
        "xba": xba,
        "recent_avg": recent_avg,
        "recent_hit_game_rate": recent_hit_game_rate,
        "avg_ev": avg_ev,
        "hard_hit_pct": hard_hit_pct,
        "barrel_pct": barrel_pct,
    }
    data_score = _profile_quality(metrics)

    if season_avg is None:
        failures.append("season_average_unavailable")
    if xba is None:
        failures.append("xba_unavailable")
    if recent_avg is None:
        failures.append("recent_average_unavailable")

    return {
        "version": PROFILE_VERSION,
        "player_id": pid,
        "season_avg": season_avg,
        "pa": pa,
        "ab": ab,
        "hits": hits,
        "hit_per_pa": hit_per_pa,
        "k_pct": k_pct,
        "xba": xba,
        "savant_pa": savant_pa,
        "recent_avg": recent_avg,
        "recent_ab": recent_ab,
        "recent_games": recent_games,
        "recent_hit_games": recent_hit_games,
        "recent_hit_game_rate": recent_hit_game_rate,
        "avg_ev": avg_ev,
        "hard_hit_pct": hard_hit_pct,
        "barrel_pct": barrel_pct,
        "neutral_hit_skill": blend["neutral_hit_skill"],
        "skill_weights": blend["weights"],
        "skill_label": skill_label(blend["neutral_hit_skill"]),
        "contact_grade": contact_grade,
        "contact_reliability": contact_reliability,
        "data_score": data_score,
        "data_label": profile_data_label(data_score),
        "failures": failures,
        "probability_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "simulation_impact": False,
        "calibration_impact": False,
        "starter_input": False,
        "bullpen_input": False,
        "park_weather_input": False,
        "market_input": False,
    }


__all__ = [
    "PROFILE_VERSION",
    "RECENT_WEIGHT_MAX",
    "SEASON_WEIGHT",
    "XBA_WEIGHT_MAX",
    "_blend_skill",
    "build_hitter_profile",
    "profile_data_label",
    "skill_label",
]
