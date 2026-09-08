"""College Football Moneyline Model V1 — raw pre-calibration model.

Additive Step 5 model built only from permanently frozen CFB Step 2/3 inputs.

Purpose
-------
Produce a transparent RAW winner probability and expected score for the
selected College Football Moneyline matchup.

The model intentionally remains pre-calibration:
- sportsbook prices are never inputs,
- no market edge/EV is computed,
- no Monte Carlo is run,
- no final betting pick is issued,
- fair moneyline is reserved for Step 6 final synthesis/calibration.

Verified inputs used when available
-----------------------------------
1. scoring offense / opponent scoring defense,
2. recent scoring trend,
3. total-offense vs total-defense efficiency context,
4. turnover margin per game,
5. opponent-win-pct schedule strength,
6. home-field advantage (disabled at neutral sites),
7. optional verified QB point adjustments ONLY if supplied by an upstream
   verified source. Missing QB data always has exactly zero model impact.

Small-sample/data-coverage reliability shrinks the raw margin toward zero
before converting it to P(win). This avoids fabricating confidence early in
the season.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

MODEL_VERSION = "CFB MONEYLINE MODEL V1 • RAW PRE-CALIBRATION"

HOME_FIELD_POINTS = 2.5
MARGIN_LOGISTIC_SCALE = 10.5

RECENT_WEIGHT = 0.18
MAX_RECENT_ADJUSTMENT = 4.0

EFFICIENCY_POINTS_PER_100_YARDS = 1.5
MAX_EFFICIENCY_ADJUSTMENT = 3.0

TURNOVER_POINTS_PER_MARGIN_PER_GAME = 1.5
MAX_TURNOVER_EDGE_POINTS = 3.0

SOS_EDGE_POINTS = 5.0
MAX_SOS_EDGE_POINTS = 2.5

MIN_RELIABILITY = 0.55
MAX_RELIABILITY = 1.00
SAMPLE_GAMES_FULL_WEIGHT = 5

_MIN_PROBABILITY = 0.03
_MAX_PROBABILITY = 0.97


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
    off = _offense_value(offense)
    opp_allowed = _defense_allowed_value(opponent)
    if off is None or opp_allowed is None:
        return None
    return 0.55 * off + 0.45 * opp_allowed


def _recent_adjustment(
    offense: Mapping[str, Any],
    opponent: Mapping[str, Any],
) -> tuple[float, bool]:
    season_off = _f(offense.get("ppg"))
    recent_off = _f(offense.get("recent_ppg"))
    season_opp_allowed = _f(opponent.get("points_allowed_pg"))
    recent_opp_allowed = _f(opponent.get("recent_points_allowed_pg"))

    terms = []
    if season_off is not None and recent_off is not None:
        terms.append(recent_off - season_off)
    if season_opp_allowed is not None and recent_opp_allowed is not None:
        terms.append(recent_opp_allowed - season_opp_allowed)

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
    return _clamp(raw, -MAX_EFFICIENCY_ADJUSTMENT, MAX_EFFICIENCY_ADJUSTMENT), True


def _turnover_margin_per_game(profile: Mapping[str, Any]) -> float | None:
    total = _official_numeric(profile, "turnover_margin")
    games = _games(profile)
    if total is None or games <= 0:
        return None
    return total / games


def _turnover_edge(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[float, bool]:
    away_tom = _turnover_margin_per_game(away)
    home_tom = _turnover_margin_per_game(home)
    if away_tom is None or home_tom is None:
        return 0.0, False

    edge = (home_tom - away_tom) * TURNOVER_POINTS_PER_MARGIN_PER_GAME
    return _clamp(edge, -MAX_TURNOVER_EDGE_POINTS, MAX_TURNOVER_EDGE_POINTS), True


def _sos_edge(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[float, bool]:
    away_sos = _f(away.get("sos_opponent_win_pct"))
    home_sos = _f(home.get("sos_opponent_win_pct"))
    away_cov = _f(away.get("sos_coverage")) or 0.0
    home_cov = _f(home.get("sos_coverage")) or 0.0
    if away_sos is None or home_sos is None or min(away_cov, home_cov) < 0.50:
        return 0.0, False

    edge = (home_sos - away_sos) * SOS_EDGE_POINTS
    return _clamp(edge, -MAX_SOS_EDGE_POINTS, MAX_SOS_EDGE_POINTS), True


def _verified_qb_adjustment(
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> tuple[float, str, bool]:
    """Use only an explicitly verified upstream QB points adjustment.

    The frozen Step-3 provider does not currently populate this field, so the
    normal Step-5 state is UNVERIFIED / ZERO IMPACT. This is intentional.
    """
    candidates = [
        game.get(f"{side}_qb_adjustment_points"),
        profile.get("qb_adjustment_points"),
    ]
    verified = bool(
        game.get(f"{side}_qb_verified")
        or profile.get("qb_verified")
    )
    value = next((_f(x) for x in candidates if _f(x) is not None), None)
    if not verified or value is None:
        return 0.0, "UNVERIFIED • ZERO IMPACT", False
    return _clamp(value, -7.0, 7.0), "VERIFIED", True


def _coverage(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    recent_away: bool,
    recent_home: bool,
    efficiency_away: bool,
    efficiency_home: bool,
    turnover_ready: bool,
    sos_ready: bool,
    qb_away_ready: bool,
    qb_home_ready: bool,
) -> dict[str, Any]:
    scoring = (
        _base_expected_points(away, home) is not None
        and _base_expected_points(home, away) is not None
    )
    recent = recent_away and recent_home
    efficiency = efficiency_away and efficiency_home
    data_quality = _quality_grade(away) != "CHECK" and _quality_grade(home) != "CHECK"

    # QB is intentionally optional: lack of verified QB data never creates a
    # phantom negative. It is reported separately and has no coverage penalty
    # in V1 because Step 3 has no certified QB provider yet.
    weights = {
        "scoring": 0.45,
        "recent": 0.15,
        "efficiency": 0.15,
        "turnovers": 0.10,
        "sos": 0.10,
        "data_quality": 0.05,
    }
    components = {
        "scoring": scoring,
        "recent": recent,
        "efficiency": efficiency,
        "turnovers": turnover_ready,
        "sos": sos_ready,
        "data_quality": data_quality,
        "qb_away_verified": qb_away_ready,
        "qb_home_verified": qb_home_ready,
    }
    score = sum(weights[k] for k in weights if components[k])
    return {
        "score": float(score),
        "components": components,
        "weights": weights,
    }


def _reliability(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    coverage_score: float,
) -> tuple[float, float]:
    min_games = min(_games(away), _games(home))
    sample_factor = _clamp(min_games / SAMPLE_GAMES_FULL_WEIGHT, 0.0, 1.0)
    value = MIN_RELIABILITY + 0.25 * float(coverage_score) + 0.20 * sample_factor
    return _clamp(value, MIN_RELIABILITY, MAX_RELIABILITY), sample_factor


def _sigmoid_probability(margin: float) -> float:
    x = _clamp(float(margin) / MARGIN_LOGISTIC_SCALE, -12.0, 12.0)
    p = 1.0 / (1.0 + math.exp(-x))
    return _clamp(p, _MIN_PROBABILITY, _MAX_PROBABILITY)


def project_matchup(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a transparent raw Step-5 model output or fail closed."""
    reasons = []

    identity_ready = bool(
        game.get("identity_verified")
        and game.get("date_matches_query")
    )
    if not identity_ready:
        reasons.append("game identity is not verified")

    away_base = _base_expected_points(away, home)
    home_base = _base_expected_points(home, away)
    if away_base is None or home_base is None:
        reasons.append("scoring offense/defense baseline is incomplete")

    if _games(away) <= 0 or _games(home) <= 0:
        reasons.append("completed-game sample is unavailable")

    if _quality_grade(away) == "CHECK" or _quality_grade(home) == "CHECK":
        reasons.append("Step 3 team-data quality is CHECK")

    if reasons:
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "reasons": reasons,
            "raw_probability_ready": False,
            "calibrated": False,
            "sportsbook_input_used": False,
            "monte_carlo_used": False,
            "fair_moneyline_ready": False,
            "final_pick_ready": False,
        }

    away_recent_adj, away_recent_ready = _recent_adjustment(away, home)
    home_recent_adj, home_recent_ready = _recent_adjustment(home, away)
    away_eff_adj, away_eff_ready = _efficiency_adjustment(away, home)
    home_eff_adj, home_eff_ready = _efficiency_adjustment(home, away)
    turnover_edge, turnover_ready = _turnover_edge(away, home)
    sos_edge, sos_ready = _sos_edge(away, home)

    away_qb_adj, away_qb_state, away_qb_ready = _verified_qb_adjustment(
        game, away, "away"
    )
    home_qb_adj, home_qb_state, home_qb_ready = _verified_qb_adjustment(
        game, home, "home"
    )

    neutral = bool(game.get("neutral_site"))
    home_field = 0.0 if neutral else HOME_FIELD_POINTS

    away_points_raw = (
        float(away_base)
        + away_recent_adj
        + away_eff_adj
        - 0.5 * turnover_edge
        - 0.5 * sos_edge
        + away_qb_adj
    )
    home_points_raw = (
        float(home_base)
        + home_recent_adj
        + home_eff_adj
        + 0.5 * turnover_edge
        + 0.5 * sos_edge
        + home_field
        + home_qb_adj
    )

    coverage = _coverage(
        away,
        home,
        away_recent_ready,
        home_recent_ready,
        away_eff_ready,
        home_eff_ready,
        turnover_ready,
        sos_ready,
        away_qb_ready,
        home_qb_ready,
    )
    reliability, sample_factor = _reliability(
        away, home, float(coverage["score"])
    )

    raw_margin = home_points_raw - away_points_raw
    midpoint = 0.5 * (home_points_raw + away_points_raw)
    reliable_margin = raw_margin * reliability
    projected_home = midpoint + 0.5 * reliable_margin
    projected_away = midpoint - 0.5 * reliable_margin

    home_probability = _sigmoid_probability(reliable_margin)
    away_probability = 1.0 - home_probability

    if reliability >= 0.88 and coverage["score"] >= 0.85:
        confidence = "HIGH"
    elif reliability >= 0.72 and coverage["score"] >= 0.65:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    leader_side = "home" if home_probability >= 0.50 else "away"
    leader_team = (
        home.get("team") or game.get("home_team")
        if leader_side == "home"
        else away.get("team") or game.get("away_team")
    )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "raw_probability_ready": True,
        "calibrated": False,
        "sportsbook_input_used": False,
        "monte_carlo_used": False,
        "fair_moneyline_ready": False,
        "final_pick_ready": False,
        "home_win_probability_raw": float(home_probability),
        "away_win_probability_raw": float(away_probability),
        "raw_model_leader_side": leader_side,
        "raw_model_leader_team": str(leader_team or "Team"),
        "projected_home_points_raw": float(projected_home),
        "projected_away_points_raw": float(projected_away),
        "projected_margin_home_raw": float(reliable_margin),
        "projected_total_raw": float(projected_home + projected_away),
        "pre_shrink_margin": float(raw_margin),
        "reliability": float(reliability),
        "sample_factor": float(sample_factor),
        "feature_coverage": coverage,
        "confidence": confidence,
        "neutral_site": neutral,
        "components": {
            "away_base_points": float(away_base),
            "home_base_points": float(home_base),
            "away_recent_adjustment": float(away_recent_adj),
            "home_recent_adjustment": float(home_recent_adj),
            "away_efficiency_adjustment": float(away_eff_adj),
            "home_efficiency_adjustment": float(home_eff_adj),
            "turnover_edge_home_points": float(turnover_edge),
            "sos_edge_home_points": float(sos_edge),
            "home_field_points": float(home_field),
            "away_qb_adjustment_points": float(away_qb_adj),
            "home_qb_adjustment_points": float(home_qb_adj),
            "away_qb_state": away_qb_state,
            "home_qb_state": home_qb_state,
        },
    }


__all__ = [
    "EFFICIENCY_POINTS_PER_100_YARDS",
    "HOME_FIELD_POINTS",
    "MARGIN_LOGISTIC_SCALE",
    "MODEL_VERSION",
    "RECENT_WEIGHT",
    "SAMPLE_GAMES_FULL_WEIGHT",
    "SOS_EDGE_POINTS",
    "TURNOVER_POINTS_PER_MARGIN_PER_GAME",
    "_official_numeric",
    "_sigmoid_probability",
    "project_matchup",
]
