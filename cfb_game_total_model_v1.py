"""College Football Game Total Model V1 — Step 11 distribution model.

Additive model above permanently frozen CFB Step 10.

Purpose
-------
Produce an independent projected combined score and discrete integer total
distribution for one verified pregame College Football matchup.

This is deliberately not an Over/Under model:
- no user-entered total line,
- no sportsbook total,
- no sportsbook price,
- no market-implied probability,
- no edge/EV,
- no final pick,
- no slate ranking.

Step 11 uses an analytic structural distribution (discretized normal), not
Monte Carlo. The uncertainty width is structural and is NOT claimed as
historical empirical calibration. Step 12 owns final Game Total synthesis and
ranking.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL MODEL V1 • STEP 11 DISTRIBUTION"

OFFENSE_WEIGHT = 0.55
OPPONENT_DEFENSE_WEIGHT = 0.45

RECENT_WEIGHT = 0.20
MAX_RECENT_TOTAL_ADJUSTMENT = 6.0

EFFICIENCY_POINTS_PER_100_YARDS = 1.10
MAX_EFFICIENCY_TOTAL_ADJUSTMENT = 5.0

MIN_RELIABILITY = 0.60
MAX_RELIABILITY = 1.00
SAMPLE_GAMES_FULL_WEIGHT = 5

BASE_TOTAL_SIGMA = 13.0
LOW_RELIABILITY_SIGMA_PENALTY = 8.0

MIN_PROJECTED_TOTAL = 6.0
MAX_PROJECTED_TOTAL = 120.0
MAX_DISTRIBUTION_TOTAL = 140

STANDARD_BANDS = (
    ("0-39", 0, 39),
    ("40-49", 40, 49),
    ("50-59", 50, 59),
    ("60-69", 60, 69),
    ("70+", 70, MAX_DISTRIBUTION_TOTAL),
)


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


def _base_team_points(
    offense: Mapping[str, Any],
    opponent: Mapping[str, Any],
) -> float | None:
    offense_points = _offense_value(offense)
    opponent_allowed = _defense_allowed_value(opponent)
    if offense_points is None or opponent_allowed is None:
        return None
    return (
        OFFENSE_WEIGHT * offense_points
        + OPPONENT_DEFENSE_WEIGHT * opponent_allowed
    )


def _recent_total_adjustment(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[float, bool]:
    season_offense = _mean([_f(away.get("ppg")), _f(home.get("ppg"))])
    recent_offense = _mean([_f(away.get("recent_ppg")), _f(home.get("recent_ppg"))])
    season_allowed = _mean([
        _f(away.get("points_allowed_pg")),
        _f(home.get("points_allowed_pg")),
    ])
    recent_allowed = _mean([
        _f(away.get("recent_points_allowed_pg")),
        _f(home.get("recent_points_allowed_pg")),
    ])

    terms: list[float] = []
    if season_offense is not None and recent_offense is not None:
        terms.append(2.0 * (recent_offense - season_offense))
    if season_allowed is not None and recent_allowed is not None:
        terms.append(2.0 * (recent_allowed - season_allowed))

    if not terms:
        return 0.0, False

    adjustment = RECENT_WEIGHT * (sum(terms) / len(terms))
    return _clamp(
        adjustment,
        -MAX_RECENT_TOTAL_ADJUSTMENT,
        MAX_RECENT_TOTAL_ADJUSTMENT,
    ), True


def _efficiency_side_adjustment(
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
    return _clamp(raw, -3.0, 3.0), True


def _efficiency_total_adjustment(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[float, bool]:
    away_adj, away_ready = _efficiency_side_adjustment(away, home)
    home_adj, home_ready = _efficiency_side_adjustment(home, away)
    if not (away_ready and home_ready):
        return 0.0, False
    return _clamp(
        away_adj + home_adj,
        -MAX_EFFICIENCY_TOTAL_ADJUSTMENT,
        MAX_EFFICIENCY_TOTAL_ADJUSTMENT,
    ), True


def _coverage(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    recent_ready: bool,
    efficiency_ready: bool,
) -> dict[str, Any]:
    scoring = (
        _base_team_points(away, home) is not None
        and _base_team_points(home, away) is not None
    )
    data_quality = (
        _quality_grade(away) != "CHECK"
        and _quality_grade(home) != "CHECK"
    )

    weights = {
        "scoring": 0.60,
        "recent": 0.20,
        "efficiency": 0.15,
        "data_quality": 0.05,
    }
    components = {
        "scoring": scoring,
        "recent": recent_ready,
        "efficiency": efficiency_ready,
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


def _discrete_distribution(
    mean: float,
    sigma: float,
    max_total: int = MAX_DISTRIBUTION_TOTAL,
) -> list[dict[str, float | int]]:
    mu = float(mean)
    sd = max(1e-9, float(sigma))
    max_k = max(1, int(max_total))

    rows: list[dict[str, float | int]] = []
    for total in range(0, max_k + 1):
        low = -math.inf if total == 0 else (total - 0.5 - mu) / sd
        high = math.inf if total == max_k else (total + 0.5 - mu) / sd

        p_low = 0.0 if math.isinf(low) and low < 0 else _normal_cdf(low)
        p_high = 1.0 if math.isinf(high) and high > 0 else _normal_cdf(high)
        probability = max(0.0, p_high - p_low)
        rows.append({"total": int(total), "probability": float(probability)})

    mass = sum(float(row["probability"]) for row in rows)
    if mass <= 0:
        return [{"total": int(round(mu)), "probability": 1.0}]

    for row in rows:
        row["probability"] = float(row["probability"]) / mass
    return rows


def _distribution_percentile(
    distribution: list[Mapping[str, Any]],
    q: float,
) -> int:
    target = _clamp(float(q), 0.0, 1.0)
    cumulative = 0.0
    for row in distribution:
        cumulative += float(row.get("probability") or 0.0)
        if cumulative + 1e-15 >= target:
            return int(row.get("total") or 0)
    return int((distribution[-1] or {}).get("total") or 0)


def _range_probability(
    distribution: list[Mapping[str, Any]],
    low: int,
    high: int,
) -> float:
    lo = int(min(low, high))
    hi = int(max(low, high))
    return float(sum(
        float(row.get("probability") or 0.0)
        for row in distribution
        if lo <= int(row.get("total") or 0) <= hi
    ))


def _standard_band_probabilities(
    distribution: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for label, low, high in STANDARD_BANDS:
        rows.append({
            "label": label,
            "low": int(low),
            "high": int(high),
            "probability": _range_probability(distribution, low, high),
        })
    return rows


def project_distribution(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    """Return Step-11 Game Total distribution or fail closed."""
    reasons: list[str] = []

    identity_ready = bool(
        game.get("identity_verified")
        and game.get("date_matches_query")
    )
    if not identity_ready:
        reasons.append("game identity is not verified")

    if not _pregame_status_ready(game):
        reasons.append("game is not verified pregame")

    away_base = _base_team_points(away, home)
    home_base = _base_team_points(home, away)
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
            "projected_combined_total_ready": False,
            "distribution_ready": False,
            "median_or_mode_ready": False,
            "exact_total_probability_ready": False,
            "total_band_probability_ready": False,
            "percentile_distribution_ready": False,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "final_pick_ready": False,
            "slate_ranking_ready": False,
            "monte_carlo_used": False,
            "empirical_calibration_claimed": False,
        }

    recent_adj, recent_ready = _recent_total_adjustment(away, home)
    efficiency_adj, efficiency_ready = _efficiency_total_adjustment(away, home)

    coverage = _coverage(
        away,
        home,
        recent_ready,
        efficiency_ready,
    )
    reliability, sample_factor = _reliability(
        away,
        home,
        float(coverage["score"]),
    )

    base_total = float(away_base) + float(home_base)
    projected_total = _clamp(
        base_total + reliability * (recent_adj + efficiency_adj),
        MIN_PROJECTED_TOTAL,
        MAX_PROJECTED_TOTAL,
    )

    sigma = (
        BASE_TOTAL_SIGMA
        + (1.0 - reliability) * LOW_RELIABILITY_SIGMA_PENALTY
    )
    distribution = _discrete_distribution(projected_total, sigma)

    mode_row = max(
        distribution,
        key=lambda row: (
            float(row.get("probability") or 0.0),
            -abs(float(row.get("total") or 0.0) - projected_total),
        ),
    )
    mode_total = int(mode_row["total"])
    median_total = _distribution_percentile(distribution, 0.50)

    percentiles = {
        "p10": _distribution_percentile(distribution, 0.10),
        "p25": _distribution_percentile(distribution, 0.25),
        "p50": median_total,
        "p75": _distribution_percentile(distribution, 0.75),
        "p90": _distribution_percentile(distribution, 0.90),
    }

    center = int(round(projected_total))
    around_projection = {
        "within_3": {
            "low": max(0, center - 3),
            "high": min(MAX_DISTRIBUTION_TOTAL, center + 3),
        },
        "within_7": {
            "low": max(0, center - 7),
            "high": min(MAX_DISTRIBUTION_TOTAL, center + 7),
        },
        "within_10": {
            "low": max(0, center - 10),
            "high": min(MAX_DISTRIBUTION_TOTAL, center + 10),
        },
    }
    for item in around_projection.values():
        item["probability"] = _range_probability(
            distribution,
            int(item["low"]),
            int(item["high"]),
        )

    top_exact = sorted(
        distribution,
        key=lambda row: (
            -float(row.get("probability") or 0.0),
            abs(float(row.get("total") or 0.0) - projected_total),
        ),
    )[:7]

    interval_80 = {
        "low": _distribution_percentile(distribution, 0.10),
        "high": _distribution_percentile(distribution, 0.90),
    }
    interval_90 = {
        "low": _distribution_percentile(distribution, 0.05),
        "high": _distribution_percentile(distribution, 0.95),
    }

    if reliability >= 0.88 and coverage["score"] >= 0.90:
        confidence = "HIGH"
    elif reliability >= 0.74 and coverage["score"] >= 0.70:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "projected_combined_total_ready": True,
        "distribution_ready": True,
        "median_or_mode_ready": True,
        "exact_total_probability_ready": True,
        "total_band_probability_ready": True,
        "percentile_distribution_ready": True,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "final_pick_ready": False,
        "slate_ranking_ready": False,
        "monte_carlo_used": False,
        "empirical_calibration_claimed": False,
        "projected_combined_total": float(projected_total),
        "distribution_mean": float(projected_total),
        "median_total": int(median_total),
        "mode_total": int(mode_total),
        "mode_probability": float(mode_row["probability"]),
        "structural_total_sigma": float(sigma),
        "reliability": float(reliability),
        "sample_factor": float(sample_factor),
        "feature_coverage": coverage,
        "confidence": confidence,
        "percentiles": percentiles,
        "structural_interval_80": interval_80,
        "structural_interval_90": interval_90,
        "standard_bands": _standard_band_probabilities(distribution),
        "around_projection": around_projection,
        "top_exact_totals": [
            {
                "total": int(row["total"]),
                "probability": float(row["probability"]),
            }
            for row in top_exact
        ],
        "distribution": [
            {
                "total": int(row["total"]),
                "probability": float(row["probability"]),
            }
            for row in distribution
        ],
        "components": {
            "away_base_points": float(away_base),
            "home_base_points": float(home_base),
            "base_combined_total": float(base_total),
            "recent_total_adjustment": float(recent_adj),
            "efficiency_total_adjustment": float(efficiency_adj),
        },
    }


__all__ = [
    "BASE_TOTAL_SIGMA",
    "EFFICIENCY_POINTS_PER_100_YARDS",
    "MAX_DISTRIBUTION_TOTAL",
    "MODEL_VERSION",
    "RECENT_WEIGHT",
    "SAMPLE_GAMES_FULL_WEIGHT",
    "STANDARD_BANDS",
    "_discrete_distribution",
    "_distribution_percentile",
    "_pregame_status_ready",
    "_range_probability",
    "project_distribution",
]
