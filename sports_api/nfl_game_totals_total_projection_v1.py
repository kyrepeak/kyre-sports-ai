"""Sportsbook-free NFL Game Totals projection for Page Step 8.

Consumes only the source-certified Step 3-7 contexts. The public projection API
intentionally has no market-line, odds, snapshot, or sportsbook parameter, so
FanDuel remains presentation context only and has exactly 0.0% model influence.
"""
from __future__ import annotations

import math
from typing import Any

SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MARKET_COMPARISON_ENABLED = False
FORMULA_VERSION = "NFL_GAME_TOTALS_TOTAL_PROJECTION_V1"

PACE_REFERENCE = 64.0
EXPLOSIVE_REFERENCE = 3.0
RED_ZONE_REFERENCE = 52.5
THIRD_DOWN_REFERENCE = 40.0
FIRST_DOWNS_REFERENCE = 21.0
PROJECTION_RANGE_POINTS = 6.5


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "ready": False,
        "formula_version": FORMULA_VERSION,
        "baseline_total": None,
        "away_baseline": None,
        "home_baseline": None,
        "adjustments": {},
        "projected_total": None,
        "range_low": None,
        "range_high": None,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "market_comparison_enabled": MARKET_COMPARISON_ENABLED,
        "diagnostics": [reason],
    }


def build_total_projection(
    scoring_context: dict[str, Any] | None,
    pace_context: dict[str, Any] | None,
    explosive_context: dict[str, Any] | None,
    red_zone_drive_context: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one deterministic total from certified non-market context only."""
    contexts = (
        scoring_context,
        pace_context,
        explosive_context,
        red_zone_drive_context,
        environment_context,
    )
    if not all(isinstance(context, dict) and context.get("ready") is True for context in contexts):
        return _unavailable("one or more certified Step 3-7 contexts were unavailable")

    scoring = scoring_context or {}
    pace = pace_context or {}
    explosive = explosive_context or {}
    sustainability = red_zone_drive_context or {}
    environment = environment_context or {}

    away = scoring.get("away") if isinstance(scoring.get("away"), dict) else {}
    home = scoring.get("home") if isinstance(scoring.get("home"), dict) else {}
    pace_matchup = pace.get("matchup") if isinstance(pace.get("matchup"), dict) else {}
    explosive_matchup = explosive.get("matchup") if isinstance(explosive.get("matchup"), dict) else {}
    sustainability_matchup = (
        sustainability.get("matchup") if isinstance(sustainability.get("matchup"), dict) else {}
    )

    away_offense = _num(away.get("offense_ppg"))
    away_opp_defense = _num(away.get("opponent_defense_papg"))
    home_offense = _num(home.get("offense_ppg"))
    home_opp_defense = _num(home.get("opponent_defense_papg"))
    plays = _num(pace_matchup.get("average_plays_per_game"))
    explosive_rate = _num(explosive_matchup.get("average_explosive_plays_per_game"))
    red_zone = _num(sustainability_matchup.get("average_red_zone_td_pct"))
    third_down = _num(sustainability_matchup.get("average_third_down_conv_pct"))
    first_downs = _num(sustainability_matchup.get("average_first_downs_per_game"))

    required = (
        away_offense,
        away_opp_defense,
        home_offense,
        home_opp_defense,
        plays,
        explosive_rate,
        red_zone,
        third_down,
        first_downs,
    )
    if not all(math.isfinite(value) for value in required):
        return _unavailable("one or more required certified projection inputs were non-numeric")

    away_baseline = (away_offense + away_opp_defense) / 2.0
    home_baseline = (home_offense + home_opp_defense) / 2.0
    baseline_total = away_baseline + home_baseline

    pace_adjustment = _clamp((plays - PACE_REFERENCE) * 0.35, -2.0, 2.0)
    explosive_adjustment = _clamp((explosive_rate - EXPLOSIVE_REFERENCE) * 0.75, -1.5, 1.5)
    sustainability_adjustment = _clamp(
        (red_zone - RED_ZONE_REFERENCE) * 0.05
        + (third_down - THIRD_DOWN_REFERENCE) * 0.08
        + (first_downs - FIRST_DOWNS_REFERENCE) * 0.25,
        -2.0,
        2.0,
    )

    if environment.get("indoor") is True:
        environment_adjustment = 0.0
        environment_signal = "INDOOR"
    else:
        environment_signal = str(environment.get("weather_pressure") or "").strip().upper()
        environment_adjustments = {"LOW": 0.0, "WATCH": -1.0, "HIGH": -2.5}
        if environment_signal not in environment_adjustments:
            return _unavailable("certified outdoor weather pressure was unavailable")
        environment_adjustment = environment_adjustments[environment_signal]

    adjustments = {
        "pace": pace_adjustment,
        "explosive": explosive_adjustment,
        "sustainability": sustainability_adjustment,
        "environment": environment_adjustment,
    }
    projected_total = round(baseline_total + sum(adjustments.values()), 1)

    return {
        "ready": True,
        "formula_version": FORMULA_VERSION,
        "baseline_total": baseline_total,
        "away_baseline": away_baseline,
        "home_baseline": home_baseline,
        "adjustments": adjustments,
        "projected_total": projected_total,
        "range_low": round(projected_total - PROJECTION_RANGE_POINTS, 1),
        "range_high": round(projected_total + PROJECTION_RANGE_POINTS, 1),
        "environment_signal": environment_signal,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "market_comparison_enabled": MARKET_COMPARISON_ENABLED,
        "diagnostics": [],
    }


__all__ = [
    "FORMULA_VERSION",
    "MARKET_COMPARISON_ENABLED",
    "PROJECTION_RANGE_POINTS",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_total_projection",
]
