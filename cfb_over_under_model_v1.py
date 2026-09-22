"""College Football Over/Under Model V1 — Step 8 raw total model.

Additive model above permanently frozen CFB Step 7.

Purpose
-------
Produce a transparent projected total and Over/Under probabilities for one
verified pregame College Football matchup.

Important market firewall
-------------------------
The user-entered analysis line is a comparison threshold only. It receives
exactly 0% weight in the projected score/total. No sportsbook feed, sportsbook
price, market-implied probability, edge/EV, slate ranking, final pick, or
Monte Carlo simulation is used in Step 8.

Verified inputs used when available
-----------------------------------
1. scoring offense vs opponent scoring defense,
2. recent scoring/allowance trend,
3. total-offense vs total-defense efficiency context,
4. completed-game sample and team-data quality.

The probability distribution uses a structural uncertainty width. It is not
claimed historical empirical calibration.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

MODEL_VERSION = "CFB OVER/UNDER MODEL V1 • STEP 8 RAW TOTAL MODEL"

BASE_OFFENSE_WEIGHT = 0.55
OPPONENT_DEFENSE_WEIGHT = 0.45

RECENT_WEIGHT = 0.20
MAX_RECENT_ADJUSTMENT = 4.0

EFFICIENCY_POINTS_PER_100_YARDS = 1.25
MAX_EFFICIENCY_ADJUSTMENT = 3.0

MIN_RELIABILITY = 0.60
MAX_RELIABILITY = 1.00
SAMPLE_GAMES_FULL_WEIGHT = 5

BASE_TOTAL_SIGMA = 13.5
LOW_RELIABILITY_SIGMA_PENALTY = 7.0

MIN_TEAM_POINTS = 3.0
MAX_TEAM_POINTS = 65.0
MIN_ANALYSIS_LINE = 1.0
MAX_ANALYSIS_LINE = 120.0

ANALYSIS_LINE_PROJECTION_WEIGHT = 0.0


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                try:
                    x = float(match.group(0))
                    return x if math.isfinite(x) else None
                except Exception:
                    return None
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _mean(values: list[float | None]) -> float | None:
    rows = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not rows:
        return None
    return sum(rows) / len(rows)


def _games(profile: Mapping[str, Any]) -> int:
    try:
        return max(0, int((profile.get("record") or {}).get("games") or 0))
    except Exception:
        return 0


def _quality_grade(profile: Mapping[str, Any]) -> str:
    return str((profile.get("data_quality") or {}).get("grade") or "CHECK").upper()


def _official_numeric(profile: Mapping[str, Any], key: str) -> float | None:
    item = (profile.get("official_stats") or {}).get(key) or {}
    value = _f(item.get("value_numeric"))
    if value is not None:
        return value
    return _f(item.get("value"))


def _offense_value(profile: Mapping[str, Any]) -> float | None:
    return _mean([
        _f(profile.get("ppg")),
        _official_numeric(profile, "scoring_offense"),
    ])


def _defense_allowed_value(profile: Mapping[str, Any]) -> float | None:
    return _mean([
        _f(profile.get("points_allowed_pg")),
        _official_numeric(profile, "scoring_defense"),
    ])


def _base_expected_points(
    offense: Mapping[str, Any],
    opponent: Mapping[str, Any],
) -> float | None:
    offense_points = _offense_value(offense)
    opponent_allowed = _defense_allowed_value(opponent)
    if offense_points is None or opponent_allowed is None:
        return None
    return (
        BASE_OFFENSE_WEIGHT * offense_points
        + OPPONENT_DEFENSE_WEIGHT * opponent_allowed
    )


def _recent_adjustment(
    offense: Mapping[str, Any],
    opponent: Mapping[str, Any],
) -> tuple[float, bool]:
    season_offense = _f(offense.get("ppg"))
    recent_offense = _f(offense.get("recent_ppg"))
    season_allowed = _f(opponent.get("points_allowed_pg"))
    recent_allowed = _f(opponent.get("recent_points_allowed_pg"))

    terms: list[float] = []
    if season_offense is not None and recent_offense is not None:
        terms.append(recent_offense - season_offense)
    if season_allowed is not None and recent_allowed is not None:
        terms.append(recent_allowed - season_allowed)

    if not terms:
        return 0.0, False

    adjustment = RECENT_WEIGHT * (sum(terms) / len(terms))
    return _clamp(adjustment, -MAX_RECENT_ADJUSTMENT, MAX_RECENT_ADJUSTMENT), True


def _efficiency_adjustment(
    offense: Mapping[str, Any],
    opponent: Mapping[str, Any],
) -> tuple[float, bool]:
    offense_yards = _official_numeric(offense, "total_offense")
    opponent_defense_yards = _official_numeric(opponent, "total_defense")
    if offense_yards is None or opponent_defense_yards is None:
        return 0.0, False

    raw = (
        (offense_yards - opponent_defense_yards)
        / 100.0
        * EFFICIENCY_POINTS_PER_100_YARDS
    )
    return _clamp(
        raw,
        -MAX_EFFICIENCY_ADJUSTMENT,
        MAX_EFFICIENCY_ADJUSTMENT,
    ), True


def _coverage(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    away_recent_ready: bool,
    home_recent_ready: bool,
    away_efficiency_ready: bool,
    home_efficiency_ready: bool,
) -> dict[str, Any]:
    scoring = (
        _base_expected_points(away, home) is not None
        and _base_expected_points(home, away) is not None
    )
    recent = away_recent_ready and home_recent_ready
    efficiency = away_efficiency_ready and home_efficiency_ready
    data_quality = (
        _quality_grade(away) != "CHECK"
        and _quality_grade(home) != "CHECK"
    )

    weights = {
        "scoring": 0.55,
        "recent": 0.20,
        "efficiency": 0.20,
        "data_quality": 0.05,
    }
    components = {
        "scoring": scoring,
        "recent": recent,
        "efficiency": efficiency,
        "data_quality": data_quality,
    }
    score = sum(weights[key] for key in weights if components[key])

    return {
        "score": float(score),
        "weights": weights,
        "components": components,
    }


def _reliability(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    coverage_score: float,
) -> tuple[float, float]:
    min_games = min(_games(away), _games(home))
    sample_factor = _clamp(
        min_games / SAMPLE_GAMES_FULL_WEIGHT,
        0.0,
        1.0,
    )
    value = (
        MIN_RELIABILITY
        + 0.25 * float(coverage_score)
        + 0.15 * sample_factor
    )
    return _clamp(value, MIN_RELIABILITY, MAX_RELIABILITY), sample_factor


def _pregame_status_ready(game: Mapping[str, Any]) -> bool:
    status = str(game.get("status") or "").strip().lower()
    if not status:
        return False

    blocked_tokens = (
        "final",
        "complete",
        "in progress",
        "live",
        "halftime",
        "cancel",
        "postpon",
        "suspend",
    )
    if any(token in status for token in blocked_tokens):
        return False

    allowed_tokens = (
        "scheduled",
        "pregame",
        "pre-game",
        "not started",
        "upcoming",
    )
    return any(token in status for token in allowed_tokens)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def _line_probabilities(
    projected_total: float,
    sigma: float,
    analysis_line: float,
) -> tuple[float, float, float]:
    """Return P(over), P(under), P(push) with integer-line continuity correction."""
    line = float(analysis_line)
    mu = float(projected_total)
    sd = max(1e-9, float(sigma))

    # Integer totals can push because football final totals are integer-valued.
    if abs(line - round(line)) < 1e-9:
        integer_line = float(round(line))
        under_cut = (integer_line - 0.5 - mu) / sd
        over_cut = (integer_line + 0.5 - mu) / sd
        p_under = _normal_cdf(under_cut)
        p_over = 1.0 - _normal_cdf(over_cut)
        p_push = max(0.0, 1.0 - p_under - p_over)
    else:
        cut = (line - mu) / sd
        p_under = _normal_cdf(cut)
        p_over = 1.0 - p_under
        p_push = 0.0

    total = p_over + p_under + p_push
    if total <= 0:
        return 0.5, 0.5, 0.0
    return (
        float(p_over / total),
        float(p_under / total),
        float(p_push / total),
    )


def project_matchup(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    analysis_line: float,
) -> dict[str, Any]:
    """Return Step-8 total projection/probabilities or fail closed."""
    reasons: list[str] = []

    identity_ready = bool(
        game.get("identity_verified")
        and game.get("date_matches_query")
    )
    if not identity_ready:
        reasons.append("game identity is not verified")

    if not _pregame_status_ready(game):
        reasons.append("game is not verified pregame")

    line = _f(analysis_line)
    if line is None or not (MIN_ANALYSIS_LINE <= line <= MAX_ANALYSIS_LINE):
        reasons.append("analysis total line is outside the supported range")

    away_base = _base_expected_points(away, home)
    home_base = _base_expected_points(home, away)
    if away_base is None or home_base is None:
        reasons.append("scoring offense/defense baseline is incomplete")

    if _games(away) <= 0 or _games(home) <= 0:
        reasons.append("completed-game sample is unavailable")

    if _quality_grade(away) == "CHECK" or _quality_grade(home) == "CHECK":
        reasons.append("team-data quality is CHECK")

    if reasons:
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "reasons": reasons,
            "projected_total_ready": False,
            "over_under_probability_ready": False,
            "analysis_line_used": line is not None,
            "analysis_line_projection_weight": ANALYSIS_LINE_PROJECTION_WEIGHT,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "empirical_calibration_claimed": False,
            "monte_carlo_used": False,
            "slate_ranking_ready": False,
            "final_pick_ready": False,
        }

    away_recent_adj, away_recent_ready = _recent_adjustment(away, home)
    home_recent_adj, home_recent_ready = _recent_adjustment(home, away)

    away_eff_adj, away_eff_ready = _efficiency_adjustment(away, home)
    home_eff_adj, home_eff_ready = _efficiency_adjustment(home, away)

    coverage = _coverage(
        away,
        home,
        away_recent_ready,
        home_recent_ready,
        away_eff_ready,
        home_eff_ready,
    )
    reliability, sample_factor = _reliability(
        away,
        home,
        float(coverage["score"]),
    )

    away_delta = away_recent_adj + away_eff_adj
    home_delta = home_recent_adj + home_eff_adj

    projected_away = _clamp(
        float(away_base) + reliability * away_delta,
        MIN_TEAM_POINTS,
        MAX_TEAM_POINTS,
    )
    projected_home = _clamp(
        float(home_base) + reliability * home_delta,
        MIN_TEAM_POINTS,
        MAX_TEAM_POINTS,
    )
    projected_total = projected_away + projected_home

    sigma = (
        BASE_TOTAL_SIGMA
        + (1.0 - reliability) * LOW_RELIABILITY_SIGMA_PENALTY
    )
    p_over, p_under, p_push = _line_probabilities(
        projected_total,
        sigma,
        float(line),
    )

    if reliability >= 0.88 and coverage["score"] >= 0.90:
        confidence = "HIGH"
    elif reliability >= 0.74 and coverage["score"] >= 0.70:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if p_push >= max(p_over, p_under):
        model_lean = "PASS"
    elif p_over > p_under:
        model_lean = "OVER"
    elif p_under > p_over:
        model_lean = "UNDER"
    else:
        model_lean = "PASS"

    interval_low = max(0.0, projected_total - 1.645 * sigma)
    interval_high = projected_total + 1.645 * sigma

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "projected_total_ready": True,
        "over_under_probability_ready": True,
        "analysis_line": float(line),
        "analysis_line_used": True,
        "analysis_line_projection_weight": ANALYSIS_LINE_PROJECTION_WEIGHT,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "empirical_calibration_claimed": False,
        "monte_carlo_used": False,
        "slate_ranking_ready": False,
        "final_pick_ready": False,
        "projected_away_points": float(projected_away),
        "projected_home_points": float(projected_home),
        "projected_total": float(projected_total),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": model_lean,
        "reliability": float(reliability),
        "sample_factor": float(sample_factor),
        "feature_coverage": coverage,
        "confidence": confidence,
        "structural_total_sigma": float(sigma),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": {
            "away_base_points": float(away_base),
            "home_base_points": float(home_base),
            "away_recent_adjustment": float(away_recent_adj),
            "home_recent_adjustment": float(home_recent_adj),
            "away_efficiency_adjustment": float(away_eff_adj),
            "home_efficiency_adjustment": float(home_eff_adj),
        },
    }


__all__ = [
    "ANALYSIS_LINE_PROJECTION_WEIGHT",
    "BASE_TOTAL_SIGMA",
    "EFFICIENCY_POINTS_PER_100_YARDS",
    "MODEL_VERSION",
    "RECENT_WEIGHT",
    "SAMPLE_GAMES_FULL_WEIGHT",
    "_line_probabilities",
    "_pregame_status_ready",
    "project_matchup",
]
