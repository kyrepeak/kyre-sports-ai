"""NFL Receiving Yards Page Step 6 — transparent market-blind baseline projection.

Consumes only already-validated ``nfl_receiving_yards_context_v1`` evidence.
The projection is intentionally isolated from sportsbook markets and prices.

Formula discipline:
1) expected receptions come from verified player receiving workload;
2) expected yards per reception blends verified player efficiency with verified
   opponent yards-per-reception allowed;
3) baseline receiving yards = expected receptions * expected yards per reception.

Explicit target data remains context-only and is never required or inferred.
Sportsbook lines/prices, probability, Monte Carlo, fair line, EV, ranking,
recommendation, stake sizing and wager actions are OFF.
"""
from __future__ import annotations

import math
from typing import Any

MODEL_VERSION = "NFL RECEIVING YARDS STEP 6 • BASELINE PROJECTION V1"
SCHEMA_VERSION = "nfl_receiving_yards_projection_v1"
CONTEXT_SCHEMA_VERSION = "nfl_receiving_yards_context_v1"

EFFICIENCY_WEIGHTS = {
    "player_yards_per_reception": 0.65,
    "opponent_yards_per_reception_allowed": 0.35,
}

MIN_READY_SAMPLE_GAMES = 1
GREEN_SAMPLE_GAMES = 5
MAX_REASONABLE_RECEPTIONS_PER_GAME = 25.0
MAX_REASONABLE_YARDS_PER_RECEPTION = 50.0
MAX_REASONABLE_PROJECTION_YARDS = 500.0


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def weighted_blend(values: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    """Blend only finite positive inputs and report intended-weight coverage."""
    used: list[dict[str, float | str]] = []
    numerator = 0.0
    denominator = 0.0
    coverage = 0.0
    for key, raw_weight in weights.items():
        value = _num(values.get(key))
        weight = float(raw_weight)
        if not math.isfinite(value) or value <= 0 or weight <= 0:
            continue
        numerator += value * weight
        denominator += weight
        coverage += weight
        used.append({"key": key, "value": value, "intended_weight": weight})
    result = numerator / denominator if denominator > 0 else math.nan
    for row in used:
        row["normalized_weight"] = (
            float(row["intended_weight"]) / denominator if denominator > 0 else math.nan
        )
    return {
        "value": result,
        "coverage": coverage,
        "used": used,
        "used_count": len(used),
    }


def _withheld(
    reason: str,
    *,
    event_id: str = "",
    team_id: str = "",
    opponent_id: str = "",
    player: dict[str, Any] | None = None,
) -> dict[str, Any]:
    player = player or {}
    return {
        "ready": False,
        "reason": _safe(reason, "projection evidence incomplete"),
        "official_event_id": _safe(event_id),
        "official_team_id": _safe(team_id),
        "opponent_official_team_id": _safe(opponent_id),
        "official_athlete_id": _safe(player.get("official_athlete_id")),
        "player_name": _safe(player.get("player_name"), "Unknown receiver"),
        "position": _safe(player.get("position"), "—"),
        "projection_yards": math.nan,
        "expected_receptions": math.nan,
        "expected_yards_per_reception": math.nan,
        "efficiency_coverage": 0.0,
        "coverage_grade": "CHECK",
        "sportsbook_influence": 0.0,
        "probability_enabled": False,
        "monte_carlo_enabled": False,
        "market_enabled": False,
        "fair_line_enabled": False,
        "ev_enabled": False,
        "ranking_enabled": False,
        "recommendation_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def _validated_workload(player: dict[str, Any]) -> tuple[float, str]:
    receptions_per_game = _num(player.get("receptions_per_game"))
    if 0 < receptions_per_game <= MAX_REASONABLE_RECEPTIONS_PER_GAME:
        return receptions_per_game, "verified receptions_per_game"

    receptions = _num(player.get("receptions"))
    games = _num(player.get("sample_games"))
    if receptions > 0 and games > 0:
        derived = receptions / games
        if 0 < derived <= MAX_REASONABLE_RECEPTIONS_PER_GAME:
            return derived, "verified receptions / sample_games"
    return math.nan, ""


def _validated_player_ypr(player: dict[str, Any]) -> tuple[float, str]:
    ypr = _num(player.get("yards_per_reception"))
    if 0 < ypr <= MAX_REASONABLE_YARDS_PER_RECEPTION:
        return ypr, "verified yards_per_reception"

    receptions = _num(player.get("receptions"))
    yards = _num(player.get("receiving_yards"))
    if receptions > 0 and yards > 0:
        derived = yards / receptions
        if 0 < derived <= MAX_REASONABLE_YARDS_PER_RECEPTION:
            return derived, "verified receiving_yards / receptions"
    return math.nan, ""


def _sample_grade(sample_games: int) -> tuple[str, str]:
    if sample_games >= GREEN_SAMPLE_GAMES:
        return "GREEN", f"verified workload sample contains {sample_games} games"
    if sample_games >= MIN_READY_SAMPLE_GAMES:
        return "WATCH", (
            f"projection is usable but workload sample contains only {sample_games} game(s)"
        )
    return "CHECK", "verified workload sample is unavailable"


def _validate_context_safety(context: dict[str, Any]) -> str:
    if _safe(context.get("schema_version")) != CONTEXT_SCHEMA_VERSION:
        return "certified Receiving Yards context schema is required"
    if context.get("ready") is not True or context.get("data_available") is not True:
        return "certified Receiving Yards context must be ready with data available"
    if (
        context.get("model_enabled") is not False
        or context.get("projection_enabled") is not False
        or context.get("market_enabled") is not False
        or context.get("sportsbook_influence") != 0.0
        or context.get("targets_inferred") is not False
        or context.get("stake_sizing_enabled") is not False
        or context.get("wager_actions") is not False
    ):
        return "Receiving context permanent safety contract failed closed"
    return ""


def build_player_projection(
    *,
    official_event_id: str,
    team: dict[str, Any],
    player: dict[str, Any],
) -> dict[str, Any]:
    """Build one exact-ID receiver baseline from verified workload + pass defense."""
    event_id = _safe(official_event_id)
    team_id = _safe(team.get("official_team_id"))
    opponent_id = _safe(team.get("opponent_official_team_id"))
    athlete_id = _safe(player.get("official_athlete_id"))
    player_team_id = _safe(player.get("official_team_id"))

    if not event_id.isdigit():
        return _withheld(
            "official ESPN event ID is required",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        return _withheld(
            "exact team/opponent identity is required",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )
    if not athlete_id.isdigit() or player_team_id != team_id:
        return _withheld(
            "exact athlete/team identity failed",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    sample_games_num = _num(player.get("sample_games"))
    sample_games = (
        int(sample_games_num)
        if math.isfinite(sample_games_num) and sample_games_num >= 0
        else 0
    )
    if sample_games < MIN_READY_SAMPLE_GAMES:
        return _withheld(
            "verified workload sample is required",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    pass_defense = team.get("opponent_pass_defense") or {}
    if not isinstance(pass_defense, dict) or pass_defense.get("data_available") is not True:
        return _withheld(
            "verified opponent pass-defense data is required",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )
    if _safe(pass_defense.get("official_team_id")) != opponent_id:
        return _withheld(
            "opponent pass-defense identity mismatch",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    opponent_ypr = _num(pass_defense.get("yards_per_reception_allowed"))
    if not (0 < opponent_ypr <= MAX_REASONABLE_YARDS_PER_RECEPTION):
        return _withheld(
            "verified opponent yards-per-reception allowed is invalid",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    expected_receptions, workload_source = _validated_workload(player)
    player_ypr, player_ypr_source = _validated_player_ypr(player)
    if not math.isfinite(expected_receptions):
        return _withheld(
            "verified player reception workload is unavailable",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )
    if not math.isfinite(player_ypr):
        return _withheld(
            "positive player receiving efficiency is unavailable",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    efficiency_inputs = {
        "player_yards_per_reception": player_ypr,
        "opponent_yards_per_reception_allowed": opponent_ypr,
    }
    efficiency = weighted_blend(efficiency_inputs, EFFICIENCY_WEIGHTS)
    expected_ypr = _num(efficiency.get("value"))
    coverage = _num(efficiency.get("coverage"))
    projection = (
        expected_receptions * expected_ypr if math.isfinite(expected_ypr) else math.nan
    )

    if not math.isfinite(coverage) or coverage < 0.999999:
        return _withheld(
            "complete player/opponent efficiency coverage is required",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )
    if (
        not math.isfinite(projection)
        or projection <= 0
        or projection > MAX_REASONABLE_PROJECTION_YARDS
    ):
        return _withheld(
            "baseline projection failed finite/sanity bounds",
            event_id=event_id,
            team_id=team_id,
            opponent_id=opponent_id,
            player=player,
        )

    grade, grade_basis = _sample_grade(sample_games)
    return {
        "ready": True,
        "reason": "",
        "official_event_id": event_id,
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "official_athlete_id": athlete_id,
        "player_name": _safe(player.get("player_name"), "Unknown receiver"),
        "position": _safe(player.get("position"), "—"),
        "baseline_season": player.get("baseline_season"),
        "sample_games": sample_games,
        "projection_yards": projection,
        "expected_receptions": expected_receptions,
        "expected_yards_per_reception": expected_ypr,
        "workload_source": workload_source,
        "player_efficiency_source": player_ypr_source,
        "efficiency_inputs": efficiency_inputs,
        "efficiency_components": efficiency.get("used") or [],
        "efficiency_coverage": coverage,
        "coverage_grade": grade,
        "coverage_basis": grade_basis,
        "formula": "expected_receptions × expected_yards_per_reception",
        "opponent_context": {
            "receptions_allowed_per_game": pass_defense.get(
                "receptions_allowed_per_game"
            ),
            "receiving_yards_allowed_per_game": pass_defense.get(
                "receiving_yards_allowed_per_game"
            ),
            "yards_per_reception_allowed": pass_defense.get(
                "yards_per_reception_allowed"
            ),
            "receiving_touchdowns_allowed_per_game": pass_defense.get(
                "receiving_touchdowns_allowed_per_game"
            ),
        },
        "context_state": (
            "TEAM PASS-DEFENSE VOLUME/YARDS/TD CONTEXT DISPLAYED; "
            "ONLY YPR ALLOWED IS NUMERICALLY BLENDED IN STEP 6"
        ),
        "targets_used": False,
        "sportsbook_influence": 0.0,
        "probability_enabled": False,
        "monte_carlo_enabled": False,
        "market_enabled": False,
        "fair_line_enabled": False,
        "ev_enabled": False,
        "ranking_enabled": False,
        "recommendation_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def build_event_projections(context: dict[str, Any]) -> dict[str, Any]:
    """Build all usable exact-ID receiver projections from one validated event context."""
    if not isinstance(context, dict):
        context = {}
    event_id = _safe(context.get("official_event_id"))
    base: dict[str, Any] = {
        "ready": False,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "official_event_id": event_id,
        "projections": [],
        "withheld": [],
        "model_enabled": True,
        "projection_enabled": True,
        "sportsbook_influence": 0.0,
        "probability_enabled": False,
        "monte_carlo_enabled": False,
        "market_enabled": False,
        "fair_line_enabled": False,
        "ev_enabled": False,
        "ranking_enabled": False,
        "recommendation_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }

    safety_reason = _validate_context_safety(context)
    if safety_reason:
        base["reason"] = safety_reason
        return base
    if not event_id.isdigit():
        base["reason"] = "official ESPN event ID is required"
        return base

    teams = context.get("teams")
    if not isinstance(teams, list) or len(teams) != 2:
        base["reason"] = "exactly two verified teams are required"
        return base

    team_ids = {
        _safe(team.get("official_team_id")) for team in teams if isinstance(team, dict)
    }
    if len(team_ids) != 2 or any(not team_id.isdigit() for team_id in team_ids):
        base["reason"] = "exact team identity failed"
        return base
    if {_safe(team.get("opponent_official_team_id")) for team in teams} != team_ids:
        base["reason"] = "reciprocal opponent identity failed"
        return base

    athlete_ids: set[str] = set()
    projections: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    for team in teams:
        players = team.get("players") or []
        if not isinstance(players, list):
            base["reason"] = "verified player list is invalid"
            return base
        for player in players:
            if not isinstance(player, dict):
                base["reason"] = "verified player row is invalid"
                return base
            athlete_id = _safe(player.get("official_athlete_id"))
            if not athlete_id.isdigit() or athlete_id in athlete_ids:
                base["reason"] = "duplicate or invalid exact athlete identity"
                return base
            athlete_ids.add(athlete_id)
            result = build_player_projection(
                official_event_id=event_id,
                team=team,
                player=player,
            )
            if result.get("ready"):
                projections.append(result)
            else:
                withheld.append(result)

    if not projections:
        base.update(
            {
                "reason": "no receiver has sufficient verified workload/efficiency evidence",
                "withheld": withheld,
            }
        )
        return base

    base.update(
        {
            "ready": True,
            "reason": "",
            "projections": projections,
            "withheld": withheld,
            "projection_count": len(projections),
            "withheld_count": len(withheld),
            "formula": (
                "expected_receptions × blended(player_yards_per_reception, "
                "opponent_yards_per_reception_allowed)"
            ),
            "scope": "MARKET-INDEPENDENT BASELINE ONLY",
            "targets_used": False,
        }
    )
    return base


__all__ = [
    "CONTEXT_SCHEMA_VERSION",
    "EFFICIENCY_WEIGHTS",
    "GREEN_SAMPLE_GAMES",
    "MIN_READY_SAMPLE_GAMES",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "build_event_projections",
    "build_player_projection",
    "weighted_blend",
]
