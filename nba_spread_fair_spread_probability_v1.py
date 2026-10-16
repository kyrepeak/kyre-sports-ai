"""NBA Spread Step 9 — Kyre fair spread + cover probability.

This layer is intentionally sportsbook-independent on the projection side. It
reconciles score-derived team performance from NBA Official and ESPN NBA,
builds a projected home margin from verified recent team margins plus a
shrunken empirical home-court residual, and only then compares that projection
to the sportsbook spread to compute cover / push probabilities.

No edge, recommendation, ranking, featured-pick, or Step-10 logic lives here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from math import erf, isfinite, sqrt
from statistics import mean, stdev
from typing import Any, Iterable, Mapping, Sequence

MODEL_VERSION = "NBA_SPREAD_STEP9_FAIR_SPREAD_COVER_V1"
STEP9_STATE_KEY = "nba_spread_step9_model_history_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = True
MAY_MODIFY_PROJECTION = True
MAY_MODIFY_PROBABILITY = True
MAY_MODIFY_RANKING = False
MAY_ACTIVATE_EDGE = False
MAY_ACTIVATE_PICK = False
MIN_TEAM_GAMES = 3
NBA_MARGIN_SD_PRIOR = 12.0
NBA_HOME_COURT_PRIOR = 2.0
_PREGAME = {"UPCOMING", "DELAYED"}
_ORDER = {"UPCOMING": 0, "DELAYED": 0, "LIVE": 1, "FINAL": 2, "CANCELLED": 2}


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if isfinite(out) else None


def _tricode(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) in {2, 3, 4} and text.isalpha() else None


def _status(value: object) -> str:
    text = str(value or "").strip().upper()
    return text if text in _ORDER else "UPCOMING"


def _phase(status: str) -> str:
    if status in _PREGAME:
        return "PREGAME"
    if status == "LIVE":
        return "LIVE"
    return "FINAL"


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def cover_probabilities(projected_home_margin: float, margin_sd: float, market_home_spread: float) -> dict[str, float]:
    """Return home-cover / away-cover / push probability.

    Basketball scoring margin is integer-valued. Integer market lines therefore
    receive a continuity-corrected one-point push bucket around the exact push
    margin; half-point lines have no push mass.
    """
    mu = float(projected_home_margin)
    sigma = max(float(margin_sd), 1e-6)
    line = float(market_home_spread)
    threshold = -line

    if abs(threshold - round(threshold)) < 1e-9:
        lower = threshold - 0.5
        upper = threshold + 0.5
        cdf_lower = _normal_cdf((lower - mu) / sigma)
        cdf_upper = _normal_cdf((upper - mu) / sigma)
        away_cover = cdf_lower
        push = max(0.0, cdf_upper - cdf_lower)
        home_cover = max(0.0, 1.0 - cdf_upper)
    else:
        away_cover = _normal_cdf((threshold - mu) / sigma)
        push = 0.0
        home_cover = max(0.0, 1.0 - away_cover)

    total = home_cover + away_cover + push
    if total <= 0:
        return {"home_cover": 0.5, "away_cover": 0.5, "push": 0.0}
    return {
        "home_cover": home_cover / total,
        "away_cover": away_cover / total,
        "push": push / total,
    }


def _normalize_history(rows: Iterable[Mapping[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    out: dict[tuple[str, str], dict[str, object]] = {}
    for raw in rows:
        team = _tricode(raw.get("team_tricode"))
        game_id = str(raw.get("game_id") or "").strip()
        margin = _number(raw.get("margin"))
        game_date = str(raw.get("game_date") or "").strip()[:10]
        if not team or not game_id or margin is None or len(game_date) != 10:
            continue
        key = (game_id, team)
        row = {
            "game_id": game_id,
            "team_tricode": team,
            "margin": float(margin),
            "game_date": game_date,
            "is_home": bool(raw.get("is_home")),
        }
        previous = out.get(key)
        if previous is not None and previous != row:
            return {}
        out[key] = row
    return out


def reconcile_performance_sources(
    official_rows: Sequence[Mapping[str, object]],
    espn_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]] | None, str]:
    official = _normalize_history(official_rows)
    espn = _normalize_history(espn_rows)
    if not official or not espn:
        return None, "PERFORMANCE_SOURCE_UNAVAILABLE"
    if set(official) != set(espn):
        return None, "PERFORMANCE_SOURCE_CONFLICT"
    canonical: list[dict[str, object]] = []
    for key in sorted(official):
        left = official[key]
        right = espn[key]
        if (
            abs(float(left["margin"]) - float(right["margin"])) > 1e-9
            or left["game_date"] != right["game_date"]
            or bool(left["is_home"]) != bool(right["is_home"])
        ):
            return None, "PERFORMANCE_SOURCE_CONFLICT"
        canonical.append(dict(left))
    return canonical, "SOURCE_CONSENSUS"


def _target_date(game: Mapping[str, object]) -> str:
    value = str(game.get("game_date_phoenix") or game.get("tip_utc") or "")
    return value[:10]


def _team_rows(canonical: Sequence[Mapping[str, object]], team: str, before_date: str) -> list[dict[str, object]]:
    rows = [
        dict(row)
        for row in canonical
        if str(row.get("team_tricode") or "") == team and str(row.get("game_date") or "") < before_date
    ]
    return sorted(rows, key=lambda row: (str(row.get("game_date")), str(row.get("game_id"))))


def _recency_mean(rows: Sequence[Mapping[str, object]]) -> float:
    if not rows:
        return 0.0
    # Latest game receives roughly twice the weight of the oldest sample.
    count = len(rows)
    weights = [1.0 + (idx / max(count - 1, 1)) for idx in range(count)]
    numerator = sum(float(row["margin"]) * weight for row, weight in zip(rows, weights))
    return numerator / sum(weights)


def _empirical_home_court(canonical: Sequence[Mapping[str, object]], before_date: str) -> float:
    eligible = [dict(row) for row in canonical if str(row.get("game_date") or "") < before_date]
    by_team: dict[str, list[dict[str, object]]] = {}
    for row in eligible:
        by_team.setdefault(str(row["team_tricode"]), []).append(row)

    residuals: list[float] = []
    for rows in by_team.values():
        baseline = mean(float(row["margin"]) for row in rows)
        residuals.extend(float(row["margin"]) - baseline for row in rows if bool(row.get("is_home")))

    if not residuals:
        return NBA_HOME_COURT_PRIOR
    empirical = mean(residuals)
    weight = len(residuals) / (len(residuals) + 18.0)
    shrunk = NBA_HOME_COURT_PRIOR * (1.0 - weight) + empirical * weight
    return min(4.5, max(0.5, float(shrunk)))


def _margin_uncertainty(home_rows: Sequence[Mapping[str, object]], away_rows: Sequence[Mapping[str, object]]) -> float:
    samples = [float(row["margin"]) for row in [*home_rows, *away_rows]]
    empirical = stdev(samples) if len(samples) >= 2 else NBA_MARGIN_SD_PRIOR
    weight = len(samples) / (len(samples) + 20.0)
    variance = (weight * empirical * empirical) + ((1.0 - weight) * NBA_MARGIN_SD_PRIOR * NBA_MARGIN_SD_PRIOR)
    return min(18.0, max(7.0, sqrt(variance)))


def build_fair_spread_context(
    game: Mapping[str, object],
    official_history: Sequence[Mapping[str, object]],
    espn_history: Sequence[Mapping[str, object]],
    *,
    market_home_spread: float | None,
    availability_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a sportsbook-independent fair spread, then compare to market.

    Sportsbook spread is never an input to projected margin or fair spread.
    Availability is carried as verified context only; Step 9 assigns no ad-hoc
    injury point values.
    """
    status = _status(game.get("status"))
    if status not in _PREGAME:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "PREGAME_MODEL_ONLY"}

    canonical, diagnostic = reconcile_performance_sources(official_history, espn_history)
    if canonical is None:
        return {"verification": "UNAVAILABLE", "diagnostic_state": diagnostic}

    away = _tricode(game.get("away_tricode"))
    home = _tricode(game.get("home_tricode"))
    target_date = _target_date(game)
    if not away or not home or len(target_date) != 10:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "GAME_IDENTITY_UNAVAILABLE"}

    away_rows = _team_rows(canonical, away, target_date)
    home_rows = _team_rows(canonical, home, target_date)
    if len(away_rows) < MIN_TEAM_GAMES or len(home_rows) < MIN_TEAM_GAMES:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "INSUFFICIENT_VERIFIED_HISTORY"}

    away_strength = _recency_mean(away_rows)
    home_strength = _recency_mean(home_rows)
    home_court = _empirical_home_court(canonical, target_date)
    projected_home_margin = home_strength - away_strength + home_court
    margin_sd = _margin_uncertainty(home_rows, away_rows)
    fair_home_spread = -projected_home_margin

    availability = dict(availability_context or {})
    availability_verification = str(availability.get("verification") or "NOT_SUPPLIED")
    result: dict[str, object] = {
        "verification": "VERIFIED",
        "diagnostic_state": "SOURCE_CONSENSUS_MODEL_READY",
        "game_key": str(game.get("game_key") or ""),
        "away_tricode": away,
        "home_tricode": home,
        "projected_home_margin": float(projected_home_margin),
        "fair_home_spread": float(fair_home_spread),
        "fair_away_spread": float(-fair_home_spread),
        "margin_sd": float(margin_sd),
        "away_history_games": len(away_rows),
        "home_history_games": len(home_rows),
        "away_recent_margin": float(away_strength),
        "home_recent_margin": float(home_strength),
        "home_court_points": float(home_court),
        "performance_sources": ["NBA Official", "ESPN NBA"],
        "performance_source_count": 2,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "availability_verification": availability_verification,
        "availability_adjustment_points": 0.0,
        "availability_adjustment_policy": "NO_UNCALIBRATED_PLAYER_POINT_VALUES",
        "ranking_activated": False,
        "edge_activated": False,
        "pick_activated": False,
    }

    line = _number(market_home_spread)
    if line is None:
        result.update({
            "market_home_spread": None,
            "cover_verification": "UNAVAILABLE",
            "cover_diagnostic_state": "VERIFIED_MARKET_LINE_UNAVAILABLE",
        })
        return result

    probabilities = cover_probabilities(projected_home_margin, margin_sd, line)
    result.update({
        "market_home_spread": float(line),
        "market_away_spread": float(-line),
        "home_cover_probability": probabilities["home_cover"],
        "away_cover_probability": probabilities["away_cover"],
        "push_probability": probabilities["push"],
        "cover_verification": "VERIFIED",
    })
    return result


def _missing_history_record(game: Mapping[str, object], status: str) -> dict[str, object]:
    return {
        "game_key": str(game.get("game_key") or ""),
        "verification": "UNAVAILABLE",
        "diagnostic_state": "PREGAME_MODEL_MISSING",
        "phase": _phase(status),
        "current_status": status,
        "snapshot_frozen": False,
        "pregame_model": None,
        "state_history": [status],
    }


def reconcile_step9_history(
    games: Sequence[Mapping[str, object]],
    history: Mapping[str, Mapping[str, object]] | None,
    *,
    model_by_game: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    updated: dict[str, dict[str, object]] = {
        str(key): deepcopy(dict(value))
        for key, value in dict(history or {}).items()
        if str(key).strip() and isinstance(value, Mapping)
    }
    models = dict(model_by_game or {})
    decorated: list[dict[str, object]] = []

    for raw in games:
        game = deepcopy(dict(raw))
        key = str(game.get("game_key") or "").strip()
        status = _status(game.get("status"))
        previous = updated.get(key) if key else None
        model = deepcopy(dict(models.get(key) or {})) if key and key in models else None

        if not key:
            record = _missing_history_record(game, status)
            record["diagnostic_state"] = "GAME_IDENTITY_MISSING"
        elif previous is None:
            if status in _PREGAME and model and str(model.get("verification")) == "VERIFIED":
                record = {
                    "game_key": key,
                    "verification": "VERIFIED",
                    "diagnostic_state": "PREGAME_MODEL_CAPTURED",
                    "phase": "PREGAME",
                    "current_status": status,
                    "snapshot_frozen": False,
                    "pregame_model": model,
                    "state_history": [status],
                }
            else:
                record = _missing_history_record(game, status)
        else:
            record = deepcopy(previous)
            prior_status = _status(record.get("current_status"))
            if _ORDER[status] < _ORDER[prior_status]:
                record["diagnostic_state"] = "STALE_STATE_IGNORED"
            else:
                history_states = list(record.get("state_history") or [prior_status])
                if status != prior_status and status not in history_states:
                    history_states.append(status)
                record["state_history"] = history_states
                record["current_status"] = status
                record["phase"] = _phase(status)

                if record.get("pregame_model") is None:
                    record["verification"] = "UNAVAILABLE"
                    record["diagnostic_state"] = "PREGAME_MODEL_MISSING"
                    record["snapshot_frozen"] = False
                elif status in _PREGAME and record.get("snapshot_frozen") is not True:
                    if model and str(model.get("verification")) == "VERIFIED":
                        record["pregame_model"] = model
                        record["verification"] = "VERIFIED"
                        record["diagnostic_state"] = "PREGAME_MODEL_REFRESHED"
                else:
                    record["snapshot_frozen"] = True
                    record["verification"] = "VERIFIED"
                    record["diagnostic_state"] = (
                        "PREGAME_MODEL_FROZEN_LIVE" if status == "LIVE" else "PREGAME_MODEL_RETAINED_FINAL"
                    )

        if key:
            updated[key] = record
        game["step9_fair_spread"] = deepcopy(record)
        decorated.append(game)

    return {
        "version": MODEL_VERSION,
        "verification": "VERIFIED",
        "history": updated,
        "games": decorated,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "MODEL_VERSION",
    "STEP9_STATE_KEY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_ACTIVATE_EDGE",
    "MAY_ACTIVATE_PICK",
    "build_fair_spread_context",
    "cover_probabilities",
    "reconcile_performance_sources",
    "reconcile_step9_history",
]
