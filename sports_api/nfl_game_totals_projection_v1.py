"""NFL Game Totals Projection V1 — football-only scoring interaction model.

Consumes the certified Game Totals football feature payload and produces fair
away points, home points, and combined total without sportsbook input. The V1
engine is intentionally transparent: 75% season scoring interaction + 25%
recent-L6 scoring interaction. Market totals, prices, implied probabilities,
and wager data are forbidden inputs.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

MODEL_VERSION = "NFL GAME TOTALS PROJECTION V1 • FOOTBALL-ONLY SCORING INTERACTION"
SEASON_WEIGHT = 0.75
RECENT_WEIGHT = 0.25
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_INPUTS: tuple[str, ...] = ()
REQUIRED_FEATURES = (
    "away_offense_ppg",
    "away_defense_papg",
    "away_recent6_pf_pg",
    "away_recent6_pa_pg",
    "home_offense_ppg",
    "home_defense_papg",
    "home_recent6_pf_pg",
    "home_recent6_pa_pg",
)


class NFLGameTotalsProjectionError(RuntimeError):
    """The football-only Game Totals projection contract could not be proven."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _finite_stat(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise NFLGameTotalsProjectionError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsProjectionError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise NFLGameTotalsProjectionError(f"{field} must be finite")
    if number < 0.0 or number > 80.0:
        raise NFLGameTotalsProjectionError(f"{field} is outside the supported NFL scoring range")
    return number


def _validate_payload(payload: Mapping[str, Any]) -> tuple[str, str, str, dict[str, float]]:
    if not isinstance(payload, Mapping):
        raise NFLGameTotalsProjectionError("feature payload must be an object")
    if _text(payload.get("schema_version")) != "nfl_game_totals_features_v1":
        raise NFLGameTotalsProjectionError("feature schema contract mismatch")
    if payload.get("football_only") is not True:
        raise NFLGameTotalsProjectionError("feature payload is not certified football-only")
    if payload.get("sportsbook_projection_influence") != 0.0:
        raise NFLGameTotalsProjectionError("sportsbook projection influence must remain exactly 0.0")
    sportsbook_inputs = payload.get("sportsbook_inputs")
    if sportsbook_inputs not in ([], (), None):
        raise NFLGameTotalsProjectionError("sportsbook inputs are forbidden in the projection engine")

    event_id = _text(payload.get("official_event_id"))
    away_team_id = _text(payload.get("away_team_id"))
    home_team_id = _text(payload.get("home_team_id"))
    if not event_id.isdigit():
        raise NFLGameTotalsProjectionError("official event ID must be numeric")
    if not away_team_id.isdigit() or not home_team_id.isdigit() or away_team_id == home_team_id:
        raise NFLGameTotalsProjectionError("official away/home team identities are invalid")

    raw_features = payload.get("features")
    if not isinstance(raw_features, Mapping):
        raise NFLGameTotalsProjectionError("feature payload is missing features")
    values = {name: _finite_stat(raw_features.get(name), name) for name in REQUIRED_FEATURES}
    return event_id, away_team_id, home_team_id, values


def project_game_total(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project fair team points and combined total from football-only scoring data."""
    event_id, away_team_id, home_team_id, f = _validate_payload(payload)

    away_season = 0.5 * (f["away_offense_ppg"] + f["home_defense_papg"])
    away_recent = 0.5 * (f["away_recent6_pf_pg"] + f["home_recent6_pa_pg"])
    home_season = 0.5 * (f["home_offense_ppg"] + f["away_defense_papg"])
    home_recent = 0.5 * (f["home_recent6_pf_pg"] + f["away_recent6_pa_pg"])

    projected_away = SEASON_WEIGHT * away_season + RECENT_WEIGHT * away_recent
    projected_home = SEASON_WEIGHT * home_season + RECENT_WEIGHT * home_recent
    projected_total = projected_away + projected_home

    values = (
        away_season,
        away_recent,
        home_season,
        home_recent,
        projected_away,
        projected_home,
        projected_total,
    )
    if not all(math.isfinite(value) for value in values):
        raise NFLGameTotalsProjectionError("projection produced a non-finite value")

    return {
        "ready": True,
        "model_version": MODEL_VERSION,
        "official_event_id": event_id,
        "away_team_id": away_team_id,
        "home_team_id": home_team_id,
        "projected_away_points": float(projected_away),
        "projected_home_points": float(projected_home),
        "projected_total": float(projected_total),
        "components": {
            "away_season_interaction": float(away_season),
            "away_recent_interaction": float(away_recent),
            "home_season_interaction": float(home_season),
            "home_recent_interaction": float(home_recent),
            "season_weight": SEASON_WEIGHT,
            "recent_weight": RECENT_WEIGHT,
        },
        "projection_method": "season_scoring_interaction_plus_recent_l6",
        "football_only": True,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "sportsbook_inputs": list(SPORTSBOOK_INPUTS),
        "market_total_used": False,
        "probability_generated": False,
        "monte_carlo_generated": False,
    }


__all__ = [
    "MODEL_VERSION",
    "NFLGameTotalsProjectionError",
    "RECENT_WEIGHT",
    "REQUIRED_FEATURES",
    "SEASON_WEIGHT",
    "SPORTSBOOK_INPUTS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "project_game_total",
]
