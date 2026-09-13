"""NFL Rushing Yards Step 3 — transparent market-blind baseline projection.

This module is intentionally isolated from the certified Step 2 context client.
It consumes only already-validated ``nfl_rushing_yards_context_v1`` evidence and
builds the first Rushing Yards projection number.

Formula discipline:
1) expected carries come from the player's verified workload baseline;
2) expected yards per carry blends the player's verified rushing efficiency
   with the verified opponent yards-per-carry allowed;
3) baseline rushing yards = expected carries * expected yards per carry.

Opponent team rush attempts/yards/TDs allowed remain visible context only in
Step 3. They are not converted into unsupported player-share adjustments.
Sportsbook lines/prices, probability, Monte Carlo, fair-line, EV, ranking,
recommendation, stake sizing and wager actions are all OFF.
"""
from __future__ import annotations

import math
from typing import Any

MODEL_VERSION = "NFL RUSHING YARDS STEP 3 • BASELINE PROJECTION V1"
SCHEMA_VERSION = "nfl_rushing_yards_projection_v1"
CONTEXT_SCHEMA_VERSION = "nfl_rushing_yards_context_v1"

EFFICIENCY_WEIGHTS = {
    "player_yards_per_carry": 0.65,
    "opponent_yards_per_carry_allowed": 0.35,
}

MIN_READY_SAMPLE_GAMES = 1
GREEN_SAMPLE_GAMES = 5
MAX_REASONABLE_CARRIES_PER_GAME = 50.0
MAX_REASONABLE_YARDS_PER_CARRY = 20.0
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


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _positive(value: Any) -> bool:
    return _finite(value) and _num(value) > 0


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
        row["normalized_weight"] = float(row["intended_weight"]) / denominator if denominator > 0 else math.nan
    return {"value": result, "coverage": coverage, "used": used, "used_count": len(used)}


def _withheld(reason: str, *, event_id: str = "", team_id: str = "", opponent_id: str = "", player: dict | None = None) -> dict[str, Any]:
    player = player or {}
    return {
        "ready": False,
        "reason": _safe(reason, "projection evidence incomplete"),
        "official_event_id": _safe(event_id),
        "official_team_id": _safe(team_id),
        "opponent_official_team_id": _safe(opponent_id),
        "official_athlete_id": _safe(player.get("official_athlete_id")),
        "player_name": _safe(player.get("player_name"), "Unknown rusher"),
        "position": _safe(player.get("position"), "—"),
        "projection_yards": math.nan,
        "expected_carries": math.nan,
        "expected_yards_per_carry": math.nan,
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
    carries_per_game = _num(player.get("carries_per_game"))
    if 0 < carries_per_game <= MAX_REASONABLE_CARRIES_PER_GAME:
        return carries_per_game, "verified carries_per_game"

    carries = _num(player.get("carries"))
    games = _num(player.get("sample_games"))
    if carries > 0 and games > 0:
        derived = carries / games
        if 0 < derived <= MAX_REASONABLE_CARRIES_PER_GAME:
            return derived, "verified carries / sample_games"
    return math.nan, ""


def _validated_player_ypc(player: dict[str, Any]) -> tuple[float, str]:
    ypc = _num(player.get("yards_per_carry"))
    if 0 < ypc <= MAX_REASONABLE_YARDS_PER_CARRY:
        return ypc, "verified yards_per_carry"

    carries = _num(player.get("carries"))
    yards = _num(player.get("rushing_yards"))
    if carries > 0 and yards > 0:
        derived = yards / carries
        if 0 < derived <= MAX_REASONABLE_YARDS_PER_CARRY:
            return derived, "verified rushing_yards / carries"
    return math.nan, ""


def _sample_grade(sample_games: int) -> tuple[str, str]:
    if sample_games >= GREEN_SAMPLE_GAMES:
        return "GREEN", f"verified workload sample contains {sample_games} games"
    if sample_games >= MIN_READY_SAMPLE_GAMES:
        return "WATCH", f"projection is usable but workload sample contains only {sample_games} game(s)"
    return "CHECK", "verified workload sample is unavailable"


def _validate_context_safety(context: dict[str, Any]) -> str:
    if _safe(context.get("schema_version")) != CONTEXT_SCHEMA_VERSION:
        return "certified Rushing Yards context schema is required"
    if context.get("ready") is not True or context.get("data_available") is not True:
        return "certified Rushing Yards context must be ready with data available"
    if (
        context.get("model_enabled") is not False
        or context.get("projection_enabled") is not False
        or context.get("market_enabled") is not False
        or context.get("sportsbook_influence") != 0.0
        or context.get("stake_sizing_enabled") is not False
        or context.get("wager_actions") is not False
    ):
        return "Step 2 permanent safety contract failed closed"
    return ""


def build_player_projection(
    *,
    official_event_id: str,
    team: dict[str, Any],
    player: dict[str, Any],
) -> dict[str, Any]:
    """Build one exact-ID player baseline from verified workload + run-front evidence."""
    event_id = _safe(official_event_id)
    team_id = _safe(team.get("official_team_id"))
    opponent_id = _safe(team.get("opponent_official_team_id"))
    athlete_id = _safe(player.get("official_athlete_id"))
    player_team_id = _safe(player.get("official_team_id"))

    if not event_id.isdigit():
        return _withheld("official ESPN event ID is required", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        return _withheld("exact team/opponent identity is required", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)
    if not athlete_id.isdigit() or player_team_id != team_id:
        return _withheld("exact athlete/team identity failed", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    sample_games_num = _num(player.get("sample_games"))
    sample_games = int(sample_games_num) if math.isfinite(sample_games_num) and sample_games_num >= 0 else 0
    if sample_games < MIN_READY_SAMPLE_GAMES:
        return _withheld("verified workload sample is required", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    run_front = team.get("opponent_run_front") or {}
    if not isinstance(run_front, dict) or run_front.get("data_available") is not True:
        return _withheld("verified opponent run-front data is required", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)
    if _safe(run_front.get("official_team_id")) != opponent_id:
        return _withheld("opponent run-front identity mismatch", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    opponent_ypc = _num(run_front.get("yards_per_carry_allowed"))
    if not (0 < opponent_ypc <= MAX_REASONABLE_YARDS_PER_CARRY):
        return _withheld("verified opponent yards-per-carry allowed is invalid", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    expected_carries, workload_source = _validated_workload(player)
    player_ypc, player_ypc_source = _validated_player_ypc(player)
    if not math.isfinite(expected_carries):
        return _withheld("verified player carry workload is unavailable", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)
    if not math.isfinite(player_ypc):
        return _withheld("positive player rushing efficiency is unavailable; kneel-only/zero-efficiency rows are withheld", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    efficiency_inputs = {
        "player_yards_per_carry": player_ypc,
        "opponent_yards_per_carry_allowed": opponent_ypc,
    }
    efficiency = weighted_blend(efficiency_inputs, EFFICIENCY_WEIGHTS)
    expected_ypc = _num(efficiency.get("value"))
    coverage = _num(efficiency.get("coverage"))
    projection = expected_carries * expected_ypc if math.isfinite(expected_ypc) else math.nan

    if not math.isfinite(coverage) or coverage < 0.999999:
        return _withheld("complete player/opponent efficiency coverage is required", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)
    if not math.isfinite(projection) or projection <= 0 or projection > MAX_REASONABLE_PROJECTION_YARDS:
        return _withheld("baseline projection failed finite/sanity bounds", event_id=event_id, team_id=team_id, opponent_id=opponent_id, player=player)

    grade, grade_basis = _sample_grade(sample_games)
    return {
        "ready": True,
        "reason": "",
        "official_event_id": event_id,
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "official_athlete_id": athlete_id,
        "player_name": _safe(player.get("player_name"), "Unknown rusher"),
        "position": _safe(player.get("position"), "—"),
        "baseline_season": player.get("baseline_season"),
        "sample_games": sample_games,
        "projection_yards": projection,
        "expected_carries": expected_carries,
        "expected_yards_per_carry": expected_ypc,
        "workload_source": workload_source,
        "player_efficiency_source": player_ypc_source,
        "efficiency_inputs": efficiency_inputs,
        "efficiency_components": efficiency.get("used") or [],
        "efficiency_coverage": coverage,
        "coverage_grade": grade,
        "coverage_basis": grade_basis,
        "formula": "expected_carries × expected_yards_per_carry",
        "opponent_context": {
            "rush_attempts_allowed_per_game": run_front.get("rush_attempts_allowed_per_game"),
            "rush_yards_allowed_per_game": run_front.get("rush_yards_allowed_per_game"),
            "yards_per_carry_allowed": run_front.get("yards_per_carry_allowed"),
            "rushing_touchdowns_allowed_per_game": run_front.get("rushing_touchdowns_allowed_per_game"),
        },
        "context_state": "TEAM RUN-FRONT VOLUME/YARDS/TD CONTEXT DISPLAYED; ONLY YPC ALLOWED IS NUMERICALLY BLENDED IN STEP 3",
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
    """Build all usable exact-ID player projections from one validated event context."""
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

    team_ids = {_safe(team.get("official_team_id")) for team in teams if isinstance(team, dict)}
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
            result = build_player_projection(official_event_id=event_id, team=team, player=player)
            if result.get("ready"):
                projections.append(result)
            else:
                withheld.append(result)

    if not projections:
        base.update({"reason": "no player has sufficient verified workload/efficiency evidence", "withheld": withheld})
        return base

    base.update(
        {
            "ready": True,
            "reason": "",
            "projections": projections,
            "withheld": withheld,
            "projection_count": len(projections),
            "withheld_count": len(withheld),
            "formula": "expected_carries × blended(player_yards_per_carry, opponent_yards_per_carry_allowed)",
            "scope": "MARKET-INDEPENDENT BASELINE ONLY",
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
