"""Step 5B: transparent game-specific WNBA matchup adjustment engine.

Consumes one Step 4X readiness report with its frozen Step 4W snapshot, builds
Step 5A from that exact same evidence package, then applies small versioned and
capped game-context adjustments. Every adjustment is exposed independently.

Step 5B intentionally does not change projected minutes and does not use
sportsbook data, betting probabilities, Monte Carlo, named defender assignments,
or automatic teammate-opportunity redistribution.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.wnba_baseline_projection import (
    MODEL_VERSION as BASELINE_MODEL_VERSION,
    WNBABaselineProjectionModelInputError,
    WNBABaselineProjectionNotReadyError,
    WNBABaselineProjectionUpstreamError,
    project_from_readiness_report,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5B matchup-adjusted projection engine"
MODEL_VERSION = "wnba_step_5b_matchup_v1"
MODEL_FAMILY = "transparent_capped_game_context_adjustment"
MAX_RECENT_GAMES = 20

PACE_CAP = 0.04
DEFENSE_CAP = 0.04
REBOUND_ENVIRONMENT_CAP = 0.03
SHOT_ZONE_CAP = 0.04
SHOT_ZONE_SHRINKAGE = 0.50
REST_TRAVEL_CAP = 0.015
TOTAL_STAT_ADJUSTMENT_CAP = 0.08
ASSIST_DEFENSE_RESPONSE = 0.50
MIN_PLAYER_SHOT_ATTEMPTS = 10
MIN_MATCHED_SHOT_SHARE = 0.50
MIN_MATCHED_OPPONENT_ZONE_ATTEMPTS = 20.0
REST_DAY_RELATIVE_EFFECT_PER_DAY = 0.0025
SECOND_NIGHT_B2B_PENALTY = -0.010
TRAVEL_1500_MILE_PENALTY = -0.0025
TRAVEL_2500_MILE_PENALTY = -0.0050
TIMEZONE_2H_PENALTY = -0.0020
ROAD_TRIP_GAME_4_PLUS_PENALTY = -0.0020

STAT_KEYS = ("points", "rebounds", "assists")


class WNBAMatchupAdjustedProjectionNotReadyError(RuntimeError):
    pass


class WNBAMatchupAdjustedProjectionNotFoundError(LookupError):
    pass


class WNBAMatchupAdjustedProjectionUpstreamError(RuntimeError):
    pass


class WNBAMatchupAdjustedProjectionModelInputError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot(readiness: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(readiness, dict):
        raise ValueError("WNBA Step 5B readiness report must be an object.")
    state = _clean(readiness.get("readiness"))
    if state == "NOT_READY" or readiness.get("can_start_projection") is False:
        blockers = _dig(readiness, "summary", "blocker_ids")
        detail = ", ".join(str(item) for item in blockers) if isinstance(blockers, list) else ""
        raise WNBAMatchupAdjustedProjectionNotReadyError(
            "Step 4X marked the player/game input package NOT_READY"
            + (f"; blockers: {detail}" if detail else "")
            + "."
        )
    if state not in {"READY", "READY_WITH_WARNINGS"} or readiness.get("can_start_projection") is not True:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4X readiness state is invalid.")
    snap = readiness.get("snapshot")
    if readiness.get("snapshot_included") is not True or not isinstance(snap, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            "Step 5B requires Step 4X to include the frozen Step 4W snapshot."
        )
    reference = readiness.get("snapshot_reference")
    if not isinstance(reference, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4X snapshot reference is missing.")
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if reference.get(key) != snap.get(key):
            raise WNBAMatchupAdjustedProjectionUpstreamError(
                f"Step 4X snapshot reference disagrees with included snapshot for {key}."
            )
    return snap


def _identity(snapshot: dict[str, Any]) -> tuple[int, str, str, str, str]:
    player_id = _to_int(snapshot.get("player_id"))
    game_id = _clean(snapshot.get("game_id"))
    focal = snapshot.get("focal_identity")
    if player_id is None or player_id <= 0 or game_id is None:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4W player/game identity is invalid.")
    if not isinstance(focal, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4W focal identity is missing.")
    team_key = _clean(focal.get("team_key"))
    opponent_key = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    if _to_int(focal.get("player_id")) != player_id:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4W focal player identity is inconsistent.")
    if not team_key or not opponent_key or team_key == opponent_key or side not in {"away", "home"}:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4W focal team/opponent identity is invalid.")
    return player_id, game_id, team_key, opponent_key, side


def _status(snapshot: dict[str, Any], name: str) -> dict[str, Any] | None:
    row = _dig(snapshot, "component_status", name)
    return row if isinstance(row, dict) else None


def _component_payload(snapshot: dict[str, Any], name: str) -> dict[str, Any] | None:
    status = _status(snapshot, name)
    payload = _dig(snapshot, "inputs", name)
    if status is None:
        return payload if isinstance(payload, dict) else None
    available = status.get("available") is True
    if available and not isinstance(payload, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            f"Step 4W marks component {name} available but its payload is missing."
        )
    if not available:
        return None
    return payload


def _single_team_advanced(
    snapshot: dict[str, Any],
    component_name: str,
    expected_team_key: str,
) -> dict[str, Any] | None:
    dataset = _component_payload(snapshot, component_name)
    if dataset is None:
        return None
    filters = dataset.get("filters")
    if isinstance(filters, dict):
        filtered_key = _clean(filters.get("team_key"))
        if filtered_key is not None and filtered_key != expected_team_key:
            raise WNBAMatchupAdjustedProjectionUpstreamError(
                f"{component_name} has a conflicting team filter."
            )
    rows = dataset.get("teams")
    if not isinstance(rows, list):
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            f"{component_name} has malformed team rows."
        )
    matches = [row for row in rows if isinstance(row, dict) and _clean(row.get("team_key")) == expected_team_key]
    if len(matches) != 1:
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            f"{component_name} returned {len(matches)} rows for {expected_team_key}."
        )
    advanced = matches[0].get("advanced")
    if not isinstance(advanced, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            f"{component_name} is missing advanced metrics."
        )
    return matches[0]


def _metric(row: dict[str, Any] | None, primary: str, fallback: str | None = None) -> float | None:
    if row is None:
        return None
    advanced = row.get("advanced")
    if not isinstance(advanced, dict):
        return None
    value = _to_float(advanced.get(primary))
    if value is None and fallback:
        value = _to_float(advanced.get(fallback))
    return value


def _pace_adjustment(team_row: dict[str, Any] | None, opponent_row: dict[str, Any] | None) -> dict[str, Any]:
    team_pace = _metric(team_row, "pace", "estimated_pace")
    opponent_pace = _metric(opponent_row, "pace", "estimated_pace")
    if team_pace is None or opponent_pace is None or team_pace <= 0 or opponent_pace <= 0:
        return {
            "available": False,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "team_or_opponent_pace_unavailable",
        }
    target = (team_pace + opponent_pace) / 2.0
    raw = target / team_pace - 1.0
    applied = _clamp(raw, -PACE_CAP, PACE_CAP)
    return {
        "available": True,
        "applied": True,
        "team_recent_pace": round(team_pace, 6),
        "opponent_recent_pace": round(opponent_pace, 6),
        "target_matchup_pace": round(target, 6),
        "raw_relative_pace_change": round(raw, 8),
        "capped_adjustment_pct": round(applied, 8),
        "stat_adjustment_pct": {key: round(applied, 8) for key in STAT_KEYS},
        "cap": PACE_CAP,
        "method": "average focal/opponent recent official pace divided by focal recent pace",
        "semantics": "5A rates already contain the focal team's recent pace; 5B changes them only for the relative target-game pace shift.",
    }


def _defense_adjustment(team_row: dict[str, Any] | None, opponent_row: dict[str, Any] | None) -> dict[str, Any]:
    team_off = _metric(team_row, "offensive_rating", "estimated_offensive_rating")
    opponent_def = _metric(opponent_row, "defensive_rating", "estimated_defensive_rating")
    if team_off is None or opponent_def is None or team_off <= 0 or opponent_def <= 0:
        return {
            "available": False,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "team_offensive_or_opponent_defensive_rating_unavailable",
        }
    midpoint_efficiency = (team_off + opponent_def) / 2.0
    raw = midpoint_efficiency / team_off - 1.0
    points = _clamp(raw, -DEFENSE_CAP, DEFENSE_CAP)
    assists = points * ASSIST_DEFENSE_RESPONSE
    return {
        "available": True,
        "applied": True,
        "focal_team_recent_offensive_rating": round(team_off, 6),
        "opponent_recent_defensive_rating": round(opponent_def, 6),
        "midpoint_matchup_efficiency": round(midpoint_efficiency, 6),
        "raw_relative_efficiency_change": round(raw, 8),
        "points_adjustment_pct": round(points, 8),
        "assist_response_fraction": ASSIST_DEFENSE_RESPONSE,
        "stat_adjustment_pct": {
            "points": round(points, 8),
            "rebounds": 0.0,
            "assists": round(assists, 8),
        },
        "cap": DEFENSE_CAP,
        "method": "50/50 focal recent offensive rating and opponent recent defensive rating, relative to focal offense",
        "semantics": "This is a transparent efficiency matchup heuristic, not a causal defender effect and not league-average calibrated.",
    }


def _rebound_environment_adjustment(
    team_row: dict[str, Any] | None,
    opponent_row: dict[str, Any] | None,
) -> dict[str, Any]:
    team_reb = _metric(team_row, "rebound_percentage", "estimated_rebound_percentage")
    opponent_reb = _metric(opponent_row, "rebound_percentage", "estimated_rebound_percentage")
    if (
        team_reb is None
        or opponent_reb is None
        or not 0 < team_reb < 1
        or not 0 < opponent_reb < 1
    ):
        return {
            "available": False,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "team_or_opponent_rebound_percentage_unavailable",
        }
    opponent_conceded_share = 1.0 - opponent_reb
    midpoint_share = (team_reb + opponent_conceded_share) / 2.0
    raw = midpoint_share / team_reb - 1.0
    rebounds = _clamp(raw, -REBOUND_ENVIRONMENT_CAP, REBOUND_ENVIRONMENT_CAP)
    return {
        "available": True,
        "applied": True,
        "focal_team_recent_rebound_percentage": round(team_reb, 8),
        "opponent_recent_rebound_percentage": round(opponent_reb, 8),
        "opponent_complement_rebound_share": round(opponent_conceded_share, 8),
        "midpoint_matchup_rebound_share": round(midpoint_share, 8),
        "raw_relative_rebound_environment_change": round(raw, 8),
        "stat_adjustment_pct": {
            "points": 0.0,
            "rebounds": round(rebounds, 8),
            "assists": 0.0,
        },
        "cap": REBOUND_ENVIRONMENT_CAP,
        "method": "50/50 focal team rebound share and complement of opponent rebound share",
        "semantics": "Team rebound environment adjusts only the rebound component; it does not infer individual rebound chances or box-outs.",
    }


def _aggregate_league_zones(rows: list[Any]) -> dict[str, dict[str, float]]:
    groups: dict[str, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        zone = _clean(row.get("canonical_zone"))
        fga = _to_float(row.get("field_goals_attempted"))
        fgm = _to_float(row.get("field_goals_made"))
        pct = _to_float(row.get("field_goal_percentage"))
        if not zone:
            continue
        item = groups.setdefault(zone, {"fgm": 0.0, "fga": 0.0, "pct_fallback_sum": 0.0, "pct_fallback_n": 0.0})
        if fga is not None and fga > 0 and fgm is not None and fgm >= 0:
            item["fgm"] += fgm
            item["fga"] += fga
        elif pct is not None and 0 <= pct <= 1:
            item["pct_fallback_sum"] += pct
            item["pct_fallback_n"] += 1.0
    out: dict[str, dict[str, float]] = {}
    for zone, item in groups.items():
        if item["fga"] > 0:
            pct = item["fgm"] / item["fga"]
        elif item["pct_fallback_n"] > 0:
            pct = item["pct_fallback_sum"] / item["pct_fallback_n"]
        else:
            continue
        out[zone] = {"field_goal_percentage": pct, "field_goals_attempted": item["fga"]}
    return out


def _shot_value(zone: str) -> int:
    text = zone.casefold()
    if "3" in text or text == "backcourt":
        return 3
    return 2


def _validate_player_shot_dataset(dataset: dict[str, Any], player_id: int, opponent_key: str | None) -> None:
    if _to_int(dataset.get("player_id")) != player_id:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Shot-chart component returned the wrong player ID.")
    filters = dataset.get("filters")
    if isinstance(filters, dict) and opponent_key is not None:
        observed = _clean(filters.get("opponent_team_key"))
        if observed != opponent_key:
            raise WNBAMatchupAdjustedProjectionUpstreamError("Opponent shot-chart filter disagrees with requested opponent.")


def _shot_zone_adjustment(snapshot: dict[str, Any], player_id: int, opponent_key: str) -> dict[str, Any]:
    recent = _component_payload(snapshot, "player_recent_shot_chart")
    opponent_defense = _component_payload(snapshot, "opponent_defense_by_shot_zone")
    versus = _component_payload(snapshot, "player_vs_opponent_shot_chart")
    if recent is None or opponent_defense is None:
        return {
            "available": False,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "recent_player_shot_chart_or_opponent_zone_defense_unavailable",
            "historical_vs_opponent": deepcopy(versus) if isinstance(versus, dict) else None,
        }
    _validate_player_shot_dataset(recent, player_id, None)
    if versus is not None:
        _validate_player_shot_dataset(versus, player_id, opponent_key)
    defending = _clean(opponent_defense.get("defending_team_key"))
    if defending is not None and defending != opponent_key:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Opponent shot-zone defense has the wrong defending team.")

    player_attempts = _to_int(recent.get("attempt_count")) or 0
    player_zones = recent.get("zone_summary")
    opponent_zones = opponent_defense.get("zones_allowed")
    league_rows = recent.get("league_average_rows")
    if not isinstance(player_zones, list) or not isinstance(opponent_zones, list) or not isinstance(league_rows, list):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Shot-zone component schema is malformed.")

    league = _aggregate_league_zones(league_rows)
    opponent_by_zone = {
        _clean(row.get("canonical_zone")): row
        for row in opponent_zones
        if isinstance(row, dict) and _clean(row.get("canonical_zone"))
    }
    matched_rows = []
    matched_share = 0.0
    matched_opponent_attempts = 0.0
    ppa_delta = 0.0
    observed_points = 0.0
    observed_attempts = 0.0
    for row in player_zones:
        if not isinstance(row, dict):
            continue
        zone = _clean(row.get("canonical_zone"))
        attempts = _to_float(row.get("field_goals_attempted")) or 0.0
        points = _to_float(row.get("points_scored"))
        if points is None:
            ppa = _to_float(row.get("observed_points_per_attempt"))
            points = (ppa or 0.0) * attempts
        observed_points += max(points, 0.0)
        observed_attempts += max(attempts, 0.0)
        share = _to_float(row.get("attempt_share"))
        if not zone or share is None or share <= 0:
            continue
        opp = opponent_by_zone.get(zone)
        lg = league.get(zone)
        if not isinstance(opp, dict) or lg is None:
            continue
        opp_pct = _to_float(opp.get("field_goal_percentage_allowed"))
        lg_pct = _to_float(lg.get("field_goal_percentage"))
        opp_attempts = _to_float(opp.get("field_goals_attempted_allowed")) or 0.0
        if opp_pct is None or lg_pct is None or not 0 <= opp_pct <= 1 or not 0 <= lg_pct <= 1:
            continue
        value = _shot_value(zone)
        zone_delta = share * value * (opp_pct - lg_pct)
        ppa_delta += zone_delta
        matched_share += share
        matched_opponent_attempts += max(opp_attempts, 0.0)
        matched_rows.append(
            {
                "canonical_zone": zone,
                "player_attempt_share": round(share, 8),
                "shot_value": value,
                "opponent_fg_pct_allowed": round(opp_pct, 8),
                "league_fg_pct": round(lg_pct, 8),
                "weighted_points_per_attempt_delta": round(zone_delta, 8),
                "opponent_attempts_allowed_in_zone": round(opp_attempts, 4),
            }
        )

    player_ppa = observed_points / observed_attempts if observed_attempts > 0 else None
    sufficient = (
        player_attempts >= MIN_PLAYER_SHOT_ATTEMPTS
        and matched_share >= MIN_MATCHED_SHOT_SHARE
        and matched_opponent_attempts >= MIN_MATCHED_OPPONENT_ZONE_ATTEMPTS
        and player_ppa is not None
        and player_ppa > 0
    )
    if not sufficient:
        return {
            "available": True,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "shot_zone_sample_or_match_coverage_below_step_5b_threshold",
            "player_recent_attempts": player_attempts,
            "matched_player_attempt_share": round(matched_share, 8),
            "matched_opponent_zone_attempts": round(matched_opponent_attempts, 4),
            "player_observed_points_per_attempt": round(player_ppa, 8) if player_ppa is not None else None,
            "thresholds": {
                "minimum_player_attempts": MIN_PLAYER_SHOT_ATTEMPTS,
                "minimum_matched_attempt_share": MIN_MATCHED_SHOT_SHARE,
                "minimum_matched_opponent_zone_attempts": MIN_MATCHED_OPPONENT_ZONE_ATTEMPTS,
            },
            "matched_zones": matched_rows,
            "historical_vs_opponent": {
                "available": versus is not None,
                "attempt_count": versus.get("attempt_count") if isinstance(versus, dict) else None,
                "field_goal_percentage": versus.get("field_goal_percentage") if isinstance(versus, dict) else None,
                "usage_in_step_5b": "diagnostic_only_not_a_directional_adjustment",
            },
        }

    raw_relative = ppa_delta / max(player_ppa, 0.75)
    shrunk = raw_relative * SHOT_ZONE_SHRINKAGE
    points = _clamp(shrunk, -SHOT_ZONE_CAP, SHOT_ZONE_CAP)
    return {
        "available": True,
        "applied": True,
        "player_recent_attempts": player_attempts,
        "player_observed_points_per_attempt": round(player_ppa, 8),
        "matched_player_attempt_share": round(matched_share, 8),
        "matched_opponent_zone_attempts": round(matched_opponent_attempts, 4),
        "weighted_points_per_attempt_delta_vs_league": round(ppa_delta, 8),
        "raw_relative_points_efficiency_change": round(raw_relative, 8),
        "shrinkage": SHOT_ZONE_SHRINKAGE,
        "capped_points_adjustment_pct": round(points, 8),
        "stat_adjustment_pct": {
            "points": round(points, 8),
            "rebounds": 0.0,
            "assists": 0.0,
        },
        "cap": SHOT_ZONE_CAP,
        "matched_zones": matched_rows,
        "historical_vs_opponent": {
            "available": versus is not None,
            "attempt_count": versus.get("attempt_count") if isinstance(versus, dict) else None,
            "field_goal_percentage": versus.get("field_goal_percentage") if isinstance(versus, dict) else None,
            "usage_in_step_5b": "diagnostic_only_not_a_directional_adjustment",
        },
        "method": "player recent shot-zone attempt shares × (opponent FG% allowed - official league FG%) × shot value, then 50% shrinkage",
        "semantics": "Observed zone defense is contextual and not treated as an individual defender causal effect.",
    }


def _rest_team_penalty(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"available": False, "penalty": 0.0, "effects": []}
    effects = []
    total = 0.0
    rest = context.get("rest")
    if isinstance(rest, dict) and rest.get("is_second_night_of_back_to_back") is True:
        total += SECOND_NIGHT_B2B_PENALTY
        effects.append({"type": "second_night_back_to_back", "effect": SECOND_NIGHT_B2B_PENALTY})
    travel = context.get("travel_to_target_or_next_game")
    if isinstance(travel, dict):
        miles = _to_float(travel.get("great_circle_miles"))
        if miles is not None and miles >= 2500:
            total += TRAVEL_2500_MILE_PENALTY
            effects.append({"type": "travel_2500_plus_great_circle_miles", "effect": TRAVEL_2500_MILE_PENALTY})
        elif miles is not None and miles >= 1500:
            total += TRAVEL_1500_MILE_PENALTY
            effects.append({"type": "travel_1500_plus_great_circle_miles", "effect": TRAVEL_1500_MILE_PENALTY})
        tz = _to_float(travel.get("timezone_offset_change_hours"))
        if tz is not None and abs(tz) >= 2.0:
            total += TIMEZONE_2H_PENALTY
            effects.append({"type": "timezone_shift_2h_plus", "effect": TIMEZONE_2H_PENALTY})
    road = context.get("road_trip")
    game_number = _to_int(road.get("road_trip_game_number")) if isinstance(road, dict) else None
    if game_number is not None and game_number >= 4:
        total += ROAD_TRIP_GAME_4_PLUS_PENALTY
        effects.append({"type": "road_trip_game_4_plus", "effect": ROAD_TRIP_GAME_4_PLUS_PENALTY})
    return {"available": True, "penalty": round(total, 8), "effects": effects}


def _rest_travel_adjustment(
    snapshot: dict[str, Any],
    team_key: str,
    opponent_key: str,
    side: str,
) -> dict[str, Any]:
    dataset = _dig(snapshot, "inputs", "game_rest_travel_context")
    if not isinstance(dataset, dict):
        return {
            "available": False,
            "applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "game_rest_travel_context_unavailable",
        }
    if _clean(dataset.get("away_team_key")) == team_key:
        focal_context = dataset.get("away_context")
        opponent_context = dataset.get("home_context")
    elif _clean(dataset.get("home_team_key")) == team_key:
        focal_context = dataset.get("home_context")
        opponent_context = dataset.get("away_context")
    else:
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            "Step 4N rest/travel context does not contain the focal team."
        )
    expected_opponent = _clean(dataset.get("home_team_key")) if side == "away" else _clean(dataset.get("away_team_key"))
    if expected_opponent != opponent_key:
        raise WNBAMatchupAdjustedProjectionUpstreamError(
            "Step 4N rest/travel opponent identity disagrees with Step 4W."
        )

    focal_penalty = _rest_team_penalty(focal_context if isinstance(focal_context, dict) else None)
    opponent_penalty = _rest_team_penalty(opponent_context if isinstance(opponent_context, dict) else None)
    focal_rest = _to_int(_dig(focal_context, "rest", "full_rest_days_before_date")) if isinstance(focal_context, dict) else None
    opponent_rest = _to_int(_dig(opponent_context, "rest", "full_rest_days_before_date")) if isinstance(opponent_context, dict) else None
    rest_effect = 0.0
    if focal_rest is not None and opponent_rest is not None:
        rest_difference = _clamp(float(focal_rest - opponent_rest), -3.0, 3.0)
        rest_effect = rest_difference * REST_DAY_RELATIVE_EFFECT_PER_DAY
    else:
        rest_difference = None
    raw = focal_penalty["penalty"] - opponent_penalty["penalty"] + rest_effect
    applied = _clamp(raw, -REST_TRAVEL_CAP, REST_TRAVEL_CAP)
    return {
        "available": True,
        "applied": True,
        "focal_team_key": team_key,
        "opponent_team_key": opponent_key,
        "focal_full_rest_days": focal_rest,
        "opponent_full_rest_days": opponent_rest,
        "rest_day_difference_capped": rest_difference,
        "rest_difference_effect": round(rest_effect, 8),
        "focal_schedule_travel_penalty": focal_penalty,
        "opponent_schedule_travel_penalty": opponent_penalty,
        "raw_relative_adjustment_pct": round(raw, 8),
        "capped_adjustment_pct": round(applied, 8),
        "stat_adjustment_pct": {key: round(applied, 8) for key in STAT_KEYS},
        "cap": REST_TRAVEL_CAP,
        "method": "relative rest days plus small versioned B2B/travel/timezone/road-trip penalties",
        "semantics": "Travel distances are descriptive great-circle miles from Step 4N, not route miles; this is a small heuristic adjustment, not a fatigue diagnosis.",
    }


def _lineup_continuity_context(
    snapshot: dict[str, Any],
    player_id: int,
    side: str,
) -> dict[str, Any]:
    opportunity = _dig(snapshot, "inputs", "player_opportunity_context")
    lineup_context = _dig(opportunity, "observed_five_player_lineup_context")
    if not isinstance(lineup_context, dict) or lineup_context.get("available") is not True:
        return {
            "available": False,
            "central_projection_adjustment_applied": False,
            "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
            "reason": "five_player_lineup_context_unavailable",
        }
    lineups = lineup_context.get("top_five_player_lineups")
    if not isinstance(lineups, list):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 4V lineup context is malformed.")
    availability = _dig(snapshot, "inputs", "game_availability")
    team_availability = availability.get(side) if isinstance(availability, dict) else None
    players = team_availability.get("players") if isinstance(team_availability, dict) else None
    status_by_id = {
        _to_int(row.get("player_id")): row
        for row in players
        if isinstance(row, dict) and _to_int(row.get("player_id")) is not None
    } if isinstance(players, list) else {}

    total_minutes = 0.0
    blocking_minutes = 0.0
    uncertain_minutes = 0.0
    blocking_teammates: dict[int, dict[str, Any]] = {}
    uncertain_teammates: dict[int, dict[str, Any]] = {}
    for lineup in lineups:
        if not isinstance(lineup, dict):
            continue
        minutes = _to_float(lineup.get("minutes")) or 0.0
        ids = lineup.get("player_ids")
        if not isinstance(ids, list):
            continue
        total_minutes += max(minutes, 0.0)
        lineup_blocking = False
        lineup_uncertain = False
        for pid in ids:
            parsed = _to_int(pid)
            if parsed is None or parsed == player_id:
                continue
            status = status_by_id.get(parsed)
            if not isinstance(status, dict):
                continue
            blocking = status.get("availability_blocking") is True or (_clean(status.get("injury_report_status")) or "").casefold() == "out"
            uncertain = status.get("availability_uncertain") is True or (_clean(status.get("injury_report_status")) or "").casefold() in {"questionable", "doubtful", "probable"}
            if blocking:
                lineup_blocking = True
                blocking_teammates[parsed] = {
                    "player_id": parsed,
                    "player_name": status.get("player_name"),
                    "injury_report_status": status.get("injury_report_status"),
                }
            elif uncertain:
                lineup_uncertain = True
                uncertain_teammates[parsed] = {
                    "player_id": parsed,
                    "player_name": status.get("player_name"),
                    "injury_report_status": status.get("injury_report_status"),
                }
        if lineup_blocking:
            blocking_minutes += max(minutes, 0.0)
        elif lineup_uncertain:
            uncertain_minutes += max(minutes, 0.0)

    blocking_share = blocking_minutes / total_minutes if total_minutes > 0 else None
    uncertain_share = uncertain_minutes / total_minutes if total_minutes > 0 else None
    return {
        "available": True,
        "central_projection_adjustment_applied": False,
        "stat_adjustment_pct": {key: 0.0 for key in STAT_KEYS},
        "top_returned_lineup_count": len(lineups),
        "top_returned_lineup_minutes_sum": round(total_minutes, 4),
        "lineup_minutes_with_blocking_teammate": round(blocking_minutes, 4),
        "lineup_minutes_with_uncertain_teammate": round(uncertain_minutes, 4),
        "blocking_lineup_share_of_returned_minutes": round(blocking_share, 6) if blocking_share is not None else None,
        "uncertain_lineup_share_of_returned_minutes": round(uncertain_share, 6) if uncertain_share is not None else None,
        "blocking_teammates": list(blocking_teammates.values()),
        "uncertain_teammates": list(uncertain_teammates.values()),
        "uncertainty_flag": bool(blocking_teammates or uncertain_teammates),
        "reason_no_directional_adjustment": (
            "Pregame teammate absence can raise opportunity while lowering efficiency or changing role. Step 5B surfaces continuity disruption but does not invent a directional redistribution effect."
        ),
    }


def _combine_adjustments(
    baseline: dict[str, Any],
    components: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_projection = baseline.get("projection")
    if not isinstance(baseline_projection, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 5A baseline projection is malformed.")
    stats: dict[str, Any] = {}
    receipts: dict[str, Any] = {}
    for stat in STAT_KEYS:
        base = baseline_projection.get(stat)
        if not isinstance(base, dict):
            raise WNBAMatchupAdjustedProjectionUpstreamError(f"Step 5A baseline is missing {stat}.")
        expected = _to_float(base.get("expected"))
        low = _to_float(base.get("minutes_sensitivity_low"))
        high = _to_float(base.get("minutes_sensitivity_high"))
        if expected is None or low is None or high is None or min(expected, low, high) < 0:
            raise WNBAMatchupAdjustedProjectionUpstreamError(f"Step 5A baseline {stat} values are invalid.")
        entries = []
        raw_total = 0.0
        for name, component in components.items():
            pct = _to_float(_dig(component, "stat_adjustment_pct", stat)) or 0.0
            raw_total += pct
            entries.append({"component": name, "adjustment_pct": round(pct, 8), "applied": component.get("applied", component.get("central_projection_adjustment_applied", False))})
        total = _clamp(raw_total, -TOTAL_STAT_ADJUSTMENT_CAP, TOTAL_STAT_ADJUSTMENT_CAP)
        multiplier = 1.0 + total
        stats[stat] = {
            "baseline_expected": round(expected, 4),
            "expected": round(expected * multiplier, 4),
            "absolute_adjustment": round(expected * multiplier - expected, 4),
            "raw_total_adjustment_pct_before_cap": round(raw_total, 8),
            "total_adjustment_pct": round(total, 8),
            "multiplier": round(multiplier, 8),
            "minutes_sensitivity_low": round(low * multiplier, 4),
            "minutes_sensitivity_high": round(high * multiplier, 4),
            "component_receipts": entries,
        }
        receipts[stat] = entries

    pra_expected = sum(stats[key]["expected"] for key in STAT_KEYS)
    pra_baseline = sum(stats[key]["baseline_expected"] for key in STAT_KEYS)
    pra_low = sum(stats[key]["minutes_sensitivity_low"] for key in STAT_KEYS)
    pra_high = sum(stats[key]["minutes_sensitivity_high"] for key in STAT_KEYS)
    stats["pra"] = {
        "baseline_expected": round(pra_baseline, 4),
        "expected": round(pra_expected, 4),
        "absolute_adjustment": round(pra_expected - pra_baseline, 4),
        "minutes_sensitivity_low": round(pra_low, 4),
        "minutes_sensitivity_high": round(pra_high, 4),
        "composition": "adjusted points + adjusted rebounds + adjusted assists",
    }
    return stats, receipts


def project_matchup_adjusted_from_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot(readiness)
    player_id, game_id, team_key, opponent_key, side = _identity(snapshot)
    try:
        baseline = project_from_readiness_report(readiness)
    except WNBABaselineProjectionNotReadyError as exc:
        raise WNBAMatchupAdjustedProjectionNotReadyError(str(exc)) from exc
    except WNBABaselineProjectionModelInputError as exc:
        raise WNBAMatchupAdjustedProjectionModelInputError(str(exc)) from exc
    except WNBABaselineProjectionUpstreamError as exc:
        raise WNBAMatchupAdjustedProjectionUpstreamError(str(exc)) from exc
    if baseline.get("model_version") != BASELINE_MODEL_VERSION:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 5B received an unexpected Step 5A model version.")
    if baseline.get("player_id") != player_id or baseline.get("game_id") != game_id:
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 5A baseline identity disagrees with Step 4W snapshot.")

    team_advanced = _single_team_advanced(snapshot, "team_advanced", team_key)
    opponent_advanced = _single_team_advanced(snapshot, "opponent_advanced", opponent_key)
    components = {
        "pace": _pace_adjustment(team_advanced, opponent_advanced),
        "opponent_defensive_environment": _defense_adjustment(team_advanced, opponent_advanced),
        "rebound_environment": _rebound_environment_adjustment(team_advanced, opponent_advanced),
        "shot_zone_fit": _shot_zone_adjustment(snapshot, player_id, opponent_key),
        "rest_travel": _rest_travel_adjustment(snapshot, team_key, opponent_key, side),
        "lineup_continuity": _lineup_continuity_context(snapshot, player_id, side),
    }
    adjusted_stats, receipts = _combine_adjustments(baseline, components)

    baseline_minutes = _dig(baseline, "projection", "minutes")
    if not isinstance(baseline_minutes, dict):
        raise WNBAMatchupAdjustedProjectionUpstreamError("Step 5A minutes projection is missing.")

    applied = [
        name
        for name, component in components.items()
        if component.get("applied") is True or component.get("central_projection_adjustment_applied") is True
    ]
    unavailable = [name for name, component in components.items() if component.get("available") is False]
    available_not_applied = [
        name
        for name, component in components.items()
        if component.get("available") is True and name not in applied
    ]
    context_level = "full" if not unavailable else "partial"

    model_config = {
        "model_version": MODEL_VERSION,
        "baseline_model_version": BASELINE_MODEL_VERSION,
        "pace_cap": PACE_CAP,
        "defense_cap": DEFENSE_CAP,
        "rebound_environment_cap": REBOUND_ENVIRONMENT_CAP,
        "shot_zone_cap": SHOT_ZONE_CAP,
        "shot_zone_shrinkage": SHOT_ZONE_SHRINKAGE,
        "rest_travel_cap": REST_TRAVEL_CAP,
        "total_stat_adjustment_cap": TOTAL_STAT_ADJUSTMENT_CAP,
        "assist_defense_response": ASSIST_DEFENSE_RESPONSE,
        "minimum_player_shot_attempts": MIN_PLAYER_SHOT_ATTEMPTS,
        "minimum_matched_shot_share": MIN_MATCHED_SHOT_SHARE,
        "minimum_matched_opponent_zone_attempts": MIN_MATCHED_OPPONENT_ZONE_ATTEMPTS,
        "minutes_adjustment": False,
        "teammate_opportunity_redistribution": False,
    }
    fingerprint_payload = {
        "snapshot_content_sha256": snapshot.get("content_sha256"),
        "baseline_projection_fingerprint_sha256": baseline.get("projection_fingerprint_sha256"),
        "model_config": model_config,
        "adjustments": components,
        "adjusted_projection": adjusted_stats,
    }
    projection_hash = _canonical_hash(fingerprint_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_transparent_matchup_adjusted_player_stat_projection",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "projection_id": f"wnba-5b-{game_id}-{player_id}-{projection_hash[:16]}",
        "projection_fingerprint_sha256": projection_hash,
        "season": snapshot.get("season"),
        "season_type": snapshot.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "side": side,
        "readiness": deepcopy(baseline.get("readiness")),
        "snapshot_reference": deepcopy(baseline.get("snapshot_reference")),
        "baseline_projection_reference": {
            "model_version": baseline.get("model_version"),
            "projection_id": baseline.get("projection_id"),
            "projection_fingerprint_sha256": baseline.get("projection_fingerprint_sha256"),
        },
        "baseline_projection": deepcopy(baseline.get("projection")),
        "adjustment_context": {
            "context_level": context_level,
            "applied_components": applied,
            "available_not_applied_components": available_not_applied,
            "unavailable_components": unavailable,
            "central_adjustment_component_count": len(applied),
            "unavailable_component_count": len(unavailable),
        },
        "adjustments": components,
        "adjustment_receipts_by_stat": receipts,
        "projection": {
            "minutes": {
                "expected": baseline_minutes.get("expected"),
                "sensitivity_low": baseline_minutes.get("sensitivity_low"),
                "sensitivity_high": baseline_minutes.get("sensitivity_high"),
                "adjusted_in_step_5b": False,
            },
            **adjusted_stats,
        },
        "model_config": model_config,
        "projection_semantics": {
            "conditional_on_player_active": True,
            "independent_of_sportsbook_market": True,
            "game_context_adjusted": True,
            "minutes_remain_step_5a_baseline": True,
            "all_central_adjustments_are_exposed_and_capped": True,
            "lineup_disruption_changes_uncertainty_context_not_central_mean": True,
            "minutes_sensitivity_is_not_probability_interval": True,
            "pra_is_sum_of_adjusted_components": True,
        },
        "guardrails": {
            "step_4x_not_ready_blocks_projection": True,
            "step_5a_baseline_uses_same_step_4w_snapshot": True,
            "no_hidden_adjustment_created": True,
            "no_matchup_component_can_change_minutes": True,
            "no_automatic_teammate_opportunity_redistribution": True,
            "historical_vs_opponent_shooting_is_diagnostic_not_directly_applied": True,
            "shot_zone_defense_is_not_individual_defender_assignment": True,
            "lineup_continuity_is_not_projected_starting_lineup": True,
            "no_sportsbook_data_used": True,
            "no_betting_probability_created": True,
            "no_monte_carlo_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "step_5a_baseline_version_checked": True,
            "step_5a_player_game_identity_checked": True,
            "team_and_opponent_advanced_identity_checked": True,
            "opponent_shot_zone_identity_checked": True,
            "rest_travel_team_opponent_identity_checked": True,
            "each_stat_total_adjustment_capped": True,
            "projection_fingerprint_created": True,
        },
    }


def get_player_game_matchup_adjusted_projection(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    require_current_availability = _bool(require_current_availability, "require_current_availability")
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)
    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBAMatchupAdjustedProjectionNotFoundError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBAMatchupAdjustedProjectionUpstreamError(str(exc)) from exc
    return project_matchup_adjusted_from_readiness(readiness)
